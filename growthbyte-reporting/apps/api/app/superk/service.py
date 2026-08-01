"""One-click orchestration for the SuperK Franchise monthly report."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

from app.agent.superk_glm import SuperKAgentError, SuperKGLMClient
from app.core.config import Settings
from app.integrations.google.search_console.repository import SearchConsoleRepository
from app.integrations.google.search_console.service import SearchConsoleService
from app.integrations.meta.client import MetaGraphClient
from app.integrations.meta.models import MetaAdAccountSummary, MetaInsightRow
from app.superk.domain import (
    FORMULA_VERSION,
    VERTICAL,
    GscTotals,
    LeadAggregate,
    LeadSourceInspection,
    PaidAggregate,
    ReportValidationError,
    SuperKReportOutput,
    build_evidence_bundle,
    calculate_monthly_metrics,
    canonical_json_sha256,
    inspect_lead_source,
    latest_completed_report_month,
    validate_report_output,
)
from app.superk.errors import SuperKClientNotFoundError, SuperKConfigurationError
from app.superk.models import (
    MonthlySnapshotResponse,
    ReportWarning,
    SourceState,
    SuperKGenerateResponse,
    SuperKStatusResponse,
    public_knowledge,
    source_state,
    warning,
)
from app.superk.repository import SuperKRepository

logger = logging.getLogger(__name__)

MetaClientFactory = Callable[[str, str], MetaGraphClient]
GLMClientFactory = Callable[[], SuperKGLMClient]


class SuperKReportingService:
    def __init__(
        self,
        *,
        repository: SuperKRepository,
        settings: Settings,
        gsc_repository: SearchConsoleRepository | None = None,
        gsc_service: SearchConsoleService | None = None,
        meta_client_factory: MetaClientFactory | None = None,
        glm_client_factory: GLMClientFactory | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._gsc_repository = gsc_repository
        self._gsc_service = gsc_service
        self._meta_client_factory = meta_client_factory or (
            lambda token, version: MetaGraphClient(access_token=token, api_version=version)
        )
        self._glm_client_factory = glm_client_factory or self._default_glm_client
        self._clock = clock

    async def get_status(self, *, client_id: UUID) -> SuperKStatusResponse:
        client = await self._require_client(client_id)
        report_month = latest_completed_report_month(
            str(client.get("reporting_timezone") or "Asia/Kolkata"),
            clock=self._clock,
        )
        inspection = inspect_lead_source(self._settings.superk.lead_json_path)
        knowledge = await self._repository.list_approved_knowledge(client_id=client_id)
        kpis = await self._repository.list_effective_kpis(
            client_id=client_id,
            report_month=_month_start(report_month),
        )
        sources, warnings = await self._status_sources(
            client_id=client_id,
            client=client,
            inspection=inspection,
            knowledge_count=len(knowledge),
            kpi_count=len(kpis),
        )
        snapshot = await self._repository.find_snapshot(
            client_id=client_id,
            report_month=_month_start(report_month),
            vertical=VERTICAL,
            formula_version=FORMULA_VERSION,
        )
        return SuperKStatusResponse(
            client_id=client_id,
            vertical=VERTICAL,
            report_month=report_month,
            ready_to_generate=True,
            snapshot_id=UUID(str(snapshot["id"])) if snapshot else None,
            sources=sources,
            warnings=tuple(warnings),
        )

    async def generate(self, *, client_id: UUID) -> SuperKGenerateResponse:
        client = await self._require_client(client_id)
        report_month = latest_completed_report_month(
            str(client.get("reporting_timezone") or "Asia/Kolkata"),
            clock=self._clock,
        )
        current_start, current_end = _month_bounds(report_month)
        previous_month = (current_start - timedelta(days=1)).strftime("%Y-%m")
        previous_start, previous_end = _month_bounds(previous_month)

        warnings: list[ReportWarning] = []
        sources: dict[str, SourceState] = {}
        inspection = inspect_lead_source(self._settings.superk.lead_json_path)
        current_leads, previous_leads, lead_import_id = await self._prepare_leads(
            client_id=client_id,
            inspection=inspection,
            report_month=report_month,
            previous_month=previous_month,
            warnings=warnings,
            sources=sources,
        )

        knowledge = await self._repository.list_approved_knowledge(client_id=client_id)
        kpis = await self._repository.list_effective_kpis(
            client_id=client_id,
            report_month=current_start,
        )
        sources["knowledge"] = source_state(
            "succeeded" if knowledge else "partial",
            f"{len(knowledge)} approved knowledge records loaded",
        )
        if not knowledge:
            warnings.append(warning("approved_knowledge_unavailable"))
        sources["kpis"] = source_state(
            "succeeded" if kpis else "partial",
            f"{len(kpis)} effective KPI targets loaded",
        )
        if not kpis:
            warnings.append(warning("effective_kpis_unavailable"))

        current_paid: PaidAggregate | None = None
        previous_paid: PaidAggregate | None = None
        meta_sync_run_id: UUID | None = None
        try:
            current_paid, previous_paid, meta_sync_run_id, synced_at = await self._sync_meta(
                client_id=client_id,
                client=client,
                current_start=current_start,
                current_end=current_end,
                previous_start=previous_start,
                previous_end=previous_end,
            )
            meta_status = "succeeded" if current_paid is not None else "partial"
            sources["meta"] = source_state(
                meta_status,
                "Exact Franchise Meta account synchronized"
                if current_paid is not None
                else "Meta returned no account-level period totals",
                synced_at=synced_at,
            )
            if current_paid is None:
                warnings.append(warning("meta_period_totals_unavailable"))
        except Exception as error:
            logger.warning(
                "SuperK Meta source unavailable",
                extra={"client_id": str(client_id), "error_type": type(error).__name__},
            )
            detail = _safe_source_error(error, "Meta source unavailable")
            status = (
                "not_configured" if isinstance(error, SuperKConfigurationError) else "unavailable"
            )
            sources["meta"] = source_state(status, detail)
            warnings.append(warning(_safe_error_code(error, "meta_source_unavailable"), detail))

        current_gsc: GscTotals | None = None
        previous_gsc: GscTotals | None = None
        gsc_sync_run_id: UUID | None = None
        try:
            current_gsc, previous_gsc, gsc_sync_run_id, synced_at = await self._sync_gsc(
                client_id=client_id,
                current_start=current_start,
                current_end=current_end,
                previous_start=previous_start,
                previous_end=previous_end,
            )
            gsc_status = "succeeded" if current_gsc is not None else "partial"
            sources["gsc"] = source_state(
                gsc_status,
                "Exact Search Console property synchronized"
                if current_gsc is not None
                else "Search Console returned no period totals",
                synced_at=synced_at,
            )
            if current_gsc is None:
                warnings.append(warning("gsc_period_totals_unavailable"))
        except Exception as error:
            logger.warning(
                "SuperK GSC source unavailable",
                extra={"client_id": str(client_id), "error_type": type(error).__name__},
            )
            detail = _safe_source_error(error, "Search Console source unavailable")
            status = (
                "not_configured" if isinstance(error, SuperKConfigurationError) else "unavailable"
            )
            sources["gsc"] = source_state(status, detail)
            warnings.append(warning(_safe_error_code(error, "gsc_source_unavailable"), detail))

        kpi_targets = {
            str(row["metric_key"]): row.get("target_value")
            for row in kpis
            if row.get("target_value") is not None
        }
        previous_values = await self._previous_values(
            client_id=client_id,
            previous_month=previous_month,
            paid=previous_paid,
            leads=previous_leads,
            gsc=previous_gsc,
        )
        result = calculate_monthly_metrics(
            client_id=client_id,
            report_month=report_month,
            paid=current_paid,
            leads=current_leads,
            gsc=current_gsc,
            previous_values=previous_values,
            kpi_targets=kpi_targets,
        )
        warnings.extend(warning(code) for code in result.warnings)

        knowledge_hash = canonical_json_sha256(_knowledge_lineage(knowledge))
        kpi_hash = canonical_json_sha256(_kpi_lineage(kpis))
        existing = await self._repository.find_snapshot(
            client_id=client_id,
            report_month=current_start,
            vertical=VERTICAL,
            formula_version=result.formula_version,
            input_hash=result.input_hash,
        )
        snapshot, inserted_metrics = await self._repository.create_snapshot(
            result=result,
            meta_sync_run_id=meta_sync_run_id,
            gsc_sync_run_id=gsc_sync_run_id,
            lead_json_import_id=lead_import_id,
            knowledge_rows=knowledge,
            knowledge_hash=knowledge_hash,
            kpi_rows=kpis,
            kpi_hash=kpi_hash,
            period_start=datetime.combine(current_start, datetime.min.time(), tzinfo=UTC),
            period_end=datetime.combine(
                current_end + timedelta(days=1),
                datetime.min.time(),
                tzinfo=UTC,
            ),
        )
        snapshot_id = UUID(str(snapshot["id"]))
        snapshot_reused = existing is not None

        evidence_bundle = build_evidence_bundle(result)
        sections, narrative_warnings = await self._generate_sections(
            evidence_bundle=evidence_bundle,
            knowledge=knowledge,
        )
        warnings.extend(narrative_warnings)
        content = {
            "client_id": str(client_id),
            "vertical": VERTICAL,
            "report_month": report_month,
            "quality_status": result.quality_status,
            "input_hash": result.input_hash,
            "sections": sections.model_dump(mode="json"),
            "warnings": [item.model_dump(mode="json") for item in _dedupe_warnings(warnings)],
        }
        metric_ids = tuple(UUID(str(row["id"])) for row in inserted_metrics if row.get("id"))
        if not metric_ids:
            metric_ids = await self._repository.list_snapshot_metric_ids(
                client_id=client_id,
                snapshot_id=snapshot_id,
            )
        report = await self._repository.create_or_reuse_draft_report(
            client_id=client_id,
            vertical=VERTICAL,
            snapshot_id=snapshot_id,
            period_start=datetime.combine(current_start, datetime.min.time(), tzinfo=UTC),
            period_end=datetime.combine(
                current_end + timedelta(days=1),
                datetime.min.time(),
                tzinfo=UTC,
            ),
            content=content,
            content_hash=canonical_json_sha256(content),
            metric_snapshot_ids=metric_ids,
        )

        final_warnings = _dedupe_warnings(warnings)
        return SuperKGenerateResponse(
            client_id=client_id,
            vertical=VERTICAL,
            report_month=report_month,
            quality_status=result.quality_status,
            snapshot_id=snapshot_id,
            snapshot_reused=snapshot_reused,
            report_id=UUID(str(report["id"])) if report else None,
            report_status="draft" if report else "not_created",
            sources=sources,
            monthly_snapshot=MonthlySnapshotResponse(
                id=snapshot_id,
                formula_version=result.formula_version,
                input_hash=result.input_hash,
                quality_status=result.quality_status,
                metrics=result.metrics,
            ),
            sections=sections,
            warnings=tuple(final_warnings),
        )

    async def _require_client(self, client_id: UUID) -> dict[str, Any]:
        configured_id = self._settings.superk.client_id
        if configured_id is None:
            raise SuperKConfigurationError
        if client_id != configured_id:
            raise SuperKClientNotFoundError
        client = await self._repository.get_client(client_id=client_id)
        if client is None or client.get("status") != "active":
            raise SuperKClientNotFoundError
        return client

    async def _status_sources(
        self,
        *,
        client_id: UUID,
        client: dict[str, Any],
        inspection: LeadSourceInspection,
        knowledge_count: int,
        kpi_count: int,
    ) -> tuple[dict[str, SourceState], list[ReportWarning]]:
        warnings: list[ReportWarning] = []
        token = self._meta_access_token(str(client.get("slug") or ""))
        if self._settings.superk.franchise_meta_account_id and token:
            meta = source_state("ready", "Exact Franchise Meta account is configured")
        else:
            meta = source_state("not_configured", "Franchise Meta source is not configured")
            warnings.append(warning("meta_source_not_configured"))
        gsc = source_state("not_configured", "Search Console source is not configured")
        if self._settings.superk.gsc_site_url and self._gsc_service:
            try:
                status = await self._gsc_service.get_status(
                    client_id=client_id,
                    vertical=VERTICAL,
                    expected_site_url=self._settings.superk.gsc_site_url,
                )
                ready = status.get("status") == "ready"
                gsc = source_state(
                    "ready" if ready else "partial",
                    str(status.get("status") or "property_verification_required"),
                )
                if not ready:
                    warnings.append(warning(str(status.get("status") or "gsc_not_ready")))
            except Exception as error:
                gsc = source_state(
                    "unavailable",
                    _safe_source_error(error, "GSC status unavailable"),
                )
                warnings.append(warning(_safe_error_code(error, "gsc_status_unavailable")))
        lead_status = "succeeded" if inspection.classification == "valid_aggregate" else "rejected"
        lead = source_state(lead_status, inspection.classification)
        if lead_status == "rejected":
            warnings.append(warning(inspection.classification))
        knowledge = source_state(
            "ready" if knowledge_count else "partial",
            f"{knowledge_count} approved knowledge records available",
        )
        kpis = source_state(
            "ready" if kpi_count else "partial",
            f"{kpi_count} effective KPI targets available",
        )
        return {
            "meta": meta,
            "gsc": gsc,
            "lead_json": lead,
            "knowledge": knowledge,
            "kpis": kpis,
        }, warnings

    async def _prepare_leads(
        self,
        *,
        client_id: UUID,
        inspection: LeadSourceInspection,
        report_month: str,
        previous_month: str,
        warnings: list[ReportWarning],
        sources: dict[str, SourceState],
    ) -> tuple[LeadAggregate | None, LeadAggregate | None, UUID | None]:
        if inspection.classification != "valid_aggregate" or inspection.aggregate is None:
            sources["lead_json"] = source_state("rejected", inspection.classification)
            warnings.append(warning(inspection.classification))
            return None, None, None
        aggregate = inspection.aggregate
        if inspection.payload_hash is None:
            sources["lead_json"] = source_state("rejected", "invalid_aggregate")
            warnings.append(warning("invalid_aggregate"))
            return None, None, None
        imported = await self._repository.save_lead_import(
            client_id=client_id,
            aggregate=aggregate,
            source_identifier=Path(self._settings.superk.lead_json_path).name,
            payload_hash=inspection.payload_hash,
        )
        sources["lead_json"] = source_state("succeeded", "Aggregate lead source accepted")
        current = aggregate if aggregate.report_month == report_month else None
        previous = aggregate if aggregate.report_month == previous_month else None
        if current is None:
            warnings.append(warning("lead_report_month_mismatch"))
        return current, previous, UUID(str(imported["id"]))

    async def _sync_meta(
        self,
        *,
        client_id: UUID,
        client: dict[str, Any],
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date,
    ) -> tuple[PaidAggregate | None, PaidAggregate | None, UUID | None, str | None]:
        account_id = self._settings.superk.franchise_meta_account_id
        token = self._meta_access_token(str(client.get("slug") or ""))
        if not account_id or not token:
            raise SuperKConfigurationError
        meta_client = self._meta_client_factory(token, self._settings.meta.graph_api_version)
        try:
            accounts = await meta_client.discover_ad_accounts()
            account = next(
                (item for item in accounts if item.external_account_id == account_id),
                None,
            )
            if account is None:
                raise SuperKConfigurationError
            connection, account_row = await self._repository.save_meta_source(
                client_id=client_id,
                vertical=VERTICAL,
                account=account,
            )
            current, current_sync = await self._sync_meta_period(
                client_id=client_id,
                meta_client=meta_client,
                account=account,
                connection_id=UUID(str(connection["id"])),
                meta_account_id=UUID(str(account_row["id"])),
                period_start=current_start,
                period_end=current_end,
            )
            previous, _ = await self._sync_meta_period(
                client_id=client_id,
                meta_client=meta_client,
                account=account,
                connection_id=UUID(str(connection["id"])),
                meta_account_id=UUID(str(account_row["id"])),
                period_start=previous_start,
                period_end=previous_end,
            )
            return current, previous, current_sync, _utc_now()
        finally:
            await meta_client.close()

    async def _sync_meta_period(
        self,
        *,
        client_id: UUID,
        meta_client: MetaGraphClient,
        account: MetaAdAccountSummary,
        connection_id: UUID,
        meta_account_id: UUID,
        period_start: date,
        period_end: date,
    ) -> tuple[PaidAggregate | None, UUID]:
        sync = await self._repository.create_source_sync_run(
            client_id=client_id,
            connection_id=connection_id,
            source_type="meta",
            vertical=VERTICAL,
            source_identifier=account.external_account_id,
            period_start=period_start,
            period_end=period_end,
        )
        sync_id = UUID(str(sync["id"]))
        rows_read = 0
        rows_written = 0
        hashes: list[str] = []
        account_rows: list[MetaInsightRow] = []
        try:
            for stored_level, api_level in (
                ("account", "account"),
                ("campaign", "campaign"),
                ("ad_set", "adset"),
                ("ad", "ad"),
            ):
                insights = await meta_client.get_period_insights(
                    external_account_id=account.external_account_id,
                    date_from=period_start.isoformat(),
                    date_to=period_end.isoformat(),
                    level=api_level,
                )
                if stored_level == "account":
                    account_rows = insights
                stored, row_hashes = await self._repository.save_meta_period_insights(
                    client_id=client_id,
                    vertical=VERTICAL,
                    meta_account_id=meta_account_id,
                    sync_run_id=sync_id,
                    period_start=period_start,
                    period_end=period_end,
                    currency=(account.currency or "INR").upper(),
                    entity_level=stored_level,
                    insights=insights,
                )
                rows_read += len(insights)
                rows_written += stored
                hashes.extend(row_hashes)
            source_hash = canonical_json_sha256(sorted(hashes)) if hashes else None
            status = "succeeded" if account_rows else "partial"
            source_warnings = () if account_rows else ("meta_period_totals_unavailable",)
            await self._repository.complete_source_sync_run(
                client_id=client_id,
                sync_run_id=sync_id,
                status=status,
                rows_read=rows_read,
                rows_written=rows_written,
                source_hash=source_hash,
                warnings=source_warnings,
            )
            paid = (
                _paid_aggregate(account_rows[0], account.currency or "INR")
                if account_rows
                else None
            )
            return paid, sync_id
        except Exception:
            try:
                await self._repository.complete_source_sync_run(
                    client_id=client_id,
                    sync_run_id=sync_id,
                    status="failed",
                    rows_read=rows_read,
                    rows_written=rows_written,
                    source_hash=None,
                    error_summary="Meta period synchronization failed safely",
                )
            except Exception:
                logger.error("Could not mark failed Meta sync", extra={"sync_run_id": str(sync_id)})
            raise

    async def _sync_gsc(
        self,
        *,
        client_id: UUID,
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date,
    ) -> tuple[GscTotals | None, GscTotals | None, UUID | None, str | None]:
        site_url = self._settings.superk.gsc_site_url
        if not site_url or not self._gsc_service or not self._gsc_repository:
            raise SuperKConfigurationError
        current_sync = await self._gsc_service.sync_period(
            client_id=client_id,
            vertical=VERTICAL,
            expected_site_url=site_url,
            period_start=current_start,
            period_end=current_end,
        )
        await self._gsc_service.sync_period(
            client_id=client_id,
            vertical=VERTICAL,
            expected_site_url=site_url,
            period_start=previous_start,
            period_end=previous_end,
        )
        current_row = await self._gsc_repository.get_period_totals(
            client_id=client_id,
            vertical=VERTICAL,
            period_start=current_start,
            period_end=current_end,
        )
        previous_row = await self._gsc_repository.get_period_totals(
            client_id=client_id,
            vertical=VERTICAL,
            period_start=previous_start,
            period_end=previous_end,
        )
        return (
            _gsc_totals(current_row),
            _gsc_totals(previous_row),
            UUID(current_sync.sync_run_id),
            str(current_row.get("synced_at")) if current_row else _utc_now(),
        )

    async def _previous_values(
        self,
        *,
        client_id: UUID,
        previous_month: str,
        paid: PaidAggregate | None,
        leads: LeadAggregate | None,
        gsc: GscTotals | None,
    ) -> dict[str, Decimal | None]:
        snapshot = await self._repository.find_snapshot(
            client_id=client_id,
            report_month=_month_start(previous_month),
            vertical=VERTICAL,
            formula_version=FORMULA_VERSION,
        )
        if snapshot is not None:
            return await self._repository.load_snapshot_metric_values(
                client_id=client_id,
                snapshot_id=UUID(str(snapshot["id"])),
            )
        previous_result = calculate_monthly_metrics(
            client_id=client_id,
            report_month=previous_month,
            paid=paid,
            leads=leads,
            gsc=gsc,
        )
        return {metric.metric_key: metric.value for metric in previous_result.metrics}

    async def _generate_sections(
        self,
        *,
        evidence_bundle: Any,
        knowledge: list[dict[str, Any]],
    ) -> tuple[SuperKReportOutput, list[ReportWarning]]:
        if self._settings.glm.configured:
            client = self._glm_client_factory()
            try:
                output, _metadata = await client.generate_report(
                    evidence_bundle=evidence_bundle.model_dump(mode="json"),
                    approved_knowledge=public_knowledge(knowledge),
                )
                return validate_report_output(output, evidence_bundle=evidence_bundle), []
            except (SuperKAgentError, ReportValidationError) as error:
                code = getattr(error, "code", "report_validation_failed")
                logger.warning("SuperK narrative fallback used", extra={"error_code": code})
                fallback = _fallback_report(evidence_bundle)
                return fallback, [warning(str(code), "Deterministic narrative fallback used")]
            finally:
                await client.close()
        fallback = _fallback_report(evidence_bundle)
        return fallback, [warning("glm_not_configured", "Deterministic narrative fallback used")]

    def _meta_access_token(self, client_slug: str) -> str | None:
        secret = (
            self._settings.meta.franchise_ads_access_token
            or self._settings.meta.access_token_for_client(client_slug)
        )
        return secret.get_secret_value() if secret else None

    def _default_glm_client(self) -> SuperKGLMClient:
        settings = self._settings.glm
        if not settings.configured or settings.base_url is None or settings.auth_token is None:
            raise SuperKConfigurationError
        return SuperKGLMClient(
            base_url=settings.base_url,
            auth_token=settings.auth_token,
            model=settings.default_sonnet_model,
            timeout_seconds=settings.timeout_seconds,
        )


def _month_start(report_month: str) -> date:
    return date.fromisoformat(f"{report_month}-01")


def _month_bounds(report_month: str) -> tuple[date, date]:
    start = _month_start(report_month)
    if start.month == 12:
        following = date(start.year + 1, 1, 1)
    else:
        following = date(start.year, start.month + 1, 1)
    return start, following - timedelta(days=1)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return parsed if parsed.is_finite() else None


def _nonnegative_int(value: Any) -> int | None:
    parsed = _decimal(value)
    if parsed is None or parsed < 0:
        return None
    return int(parsed)


def _meta_leads(insight: MetaInsightRow) -> int:
    accepted = {
        "lead",
        "omni_lead",
        "onsite_conversion.lead_grouped",
        "offsite_conversion.fb_pixel_lead",
    }
    total = 0
    for action in insight.actions:
        if str(action.get("action_type") or "") in accepted:
            total += _nonnegative_int(action.get("value")) or 0
    return total


def _paid_aggregate(insight: MetaInsightRow, currency: str) -> PaidAggregate:
    return PaidAggregate(
        spend=_decimal(insight.spend),
        link_clicks=_nonnegative_int(insight.inline_link_clicks),
        impressions=_nonnegative_int(insight.impressions),
        period_reach=_nonnegative_int(insight.reach),
        meta_reported_leads=_meta_leads(insight),
        currency=currency.upper() if len(currency) == 3 else "INR",
    )


def _gsc_totals(row: dict[str, Any] | None) -> GscTotals | None:
    if row is None:
        return None
    ctr = _decimal(row.get("ctr"))
    return GscTotals(
        clicks=_decimal(row.get("clicks")),
        impressions=_decimal(row.get("impressions")),
        ctr_percent=ctr * Decimal("100") if ctr is not None else None,
        average_position=_decimal(row.get("average_position")),
    )


def _fallback_report(evidence_bundle: Any) -> SuperKReportOutput:
    evidence = {item.metric_key: item.evidence_id for item in evidence_bundle.evidence}

    def claim(statement: str, *keys: str, confidence: str = "low") -> list[dict[str, Any]]:
        ids = [evidence[key] for key in keys if key in evidence]
        if not ids:
            ids = [evidence_bundle.evidence[0].evidence_id]
        return [
            {
                "statement": statement,
                "evidence_ids": ids,
                "confidence": confidence,
                "limitation": "The statement is limited to available aggregate evidence.",
            }
        ]

    output = {
        "executive_summary": claim(
            "The monthly report is grounded in the available aggregate evidence.",
            "spend",
            "operational_leads",
            "organic_clicks",
        ),
        "paid_performance_summary": claim(
            "Paid performance is presented only where Meta period evidence is available.",
            "spend",
            "link_clicks",
            "period_reach",
        ),
        "lead_and_rtm_funnel": claim(
            "RTM funnel conclusions are limited by operational source coverage.",
            "operational_leads",
            "rtm_leads",
            "rtm_conversion_rate",
        ),
        "search_console_seo_summary": claim(
            "Organic search performance is presented only where final Search Console "
            "evidence is available.",
            "organic_clicks",
            "organic_impressions",
            "organic_ctr",
        ),
        "campaign_and_creative_observations": claim(
            "Campaign and creative conclusions require verified entity-level context.",
            "spend",
            "link_clicks",
        ),
        "search_query_and_page_movements": claim(
            "Search query and page movement conclusions require comparable dimension evidence.",
            "organic_clicks",
            "organic_average_position",
        ),
        "important_wins": claim(
            "No performance win is asserted without adequate comparative evidence.",
            "spend",
            "operational_leads",
        ),
        "important_problems": claim(
            "Incomplete source coverage is an important reporting limitation.",
            "operational_leads",
            "organic_clicks",
        ),
        "recommended_actions": claim(
            "Review connector and operational source coverage before making "
            "optimization decisions.",
            "meta_operational_lead_difference",
            "organic_clicks",
        ),
        "data_reconciliation_and_limitations": claim(
            "Meta and operational totals should be reconciled before interpreting the funnel.",
            "meta_reported_leads",
            "operational_leads",
            "meta_operational_lead_difference",
        ),
    }
    return validate_report_output(output, evidence_bundle=evidence_bundle)


def _knowledge_lineage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(row["id"]),
            "version": row.get("version"),
            "source_hash": row.get("source_hash"),
        }
        for row in rows
    ]


def _kpi_lineage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(row["id"]),
            "metric_key": row.get("metric_key"),
            "target_value": row.get("target_value"),
        }
        for row in rows
    ]


def _safe_error_code(error: Exception, fallback: str) -> str:
    code = getattr(error, "code", None)
    return str(code) if isinstance(code, str) and code else fallback


def _safe_source_error(error: Exception, fallback: str) -> str:
    message = getattr(error, "safe_message", None)
    return str(message) if isinstance(message, str) and message else fallback


def _dedupe_warnings(items: list[ReportWarning]) -> list[ReportWarning]:
    result: list[ReportWarning] = []
    seen: set[str] = set()
    for item in items:
        if item.code in seen:
            continue
        seen.add(item.code)
        result.append(item)
    return result


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
