"""Client-scoped persistence for immutable SuperK monthly snapshots."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.data.supabase import ReportingSupabaseClientProtocol
from app.integrations.meta.models import MetaAdAccountSummary, MetaInsightRow
from app.superk.domain import LeadAggregate, MonthlyMetricResult, canonical_json_sha256
from app.superk.errors import SuperKPersistenceError


class SuperKRepository:
    def __init__(self, client: ReportingSupabaseClientProtocol) -> None:
        self._client = client

    async def get_client(self, *, client_id: UUID) -> dict[str, Any] | None:
        rows = await self._client.select(
            table="clients",
            columns=(
                "id",
                "name",
                "slug",
                "reporting_timezone",
                "default_currency",
                "status",
            ),
            filters={"id": str(client_id)},
            limit=1,
        )
        return rows[0] if rows else None

    async def list_approved_knowledge(self, *, client_id: UUID) -> list[dict[str, Any]]:
        return await self._client.select(
            table="client_knowledge",
            columns=(
                "id",
                "client_id",
                "category",
                "knowledge_key",
                "value",
                "status",
                "source_type",
                "source_identifier",
                "source_version",
                "source_hash",
                "version",
                "approved_at",
            ),
            filters={"client_id": str(client_id), "status": "approved"},
            limit=1000,
        )

    async def list_effective_kpis(
        self,
        *,
        client_id: UUID,
        report_month: date,
    ) -> list[dict[str, Any]]:
        rows = await self._client.select(
            table="client_kpis",
            columns=(
                "id",
                "client_id",
                "metric_key",
                "label",
                "target_value",
                "unit",
                "direction",
                "attribution_level",
                "active_from",
                "active_to",
            ),
            filters={"client_id": str(client_id)},
            limit=1000,
        )
        return [row for row in rows if _kpi_is_effective(row, report_month)]

    async def get_meta_connection(
        self,
        *,
        client_id: UUID,
        external_account_id: str,
    ) -> dict[str, Any] | None:
        rows = await self._client.select(
            table="integration_connections",
            columns=(
                "id",
                "client_id",
                "provider",
                "source_identifier",
                "display_name",
                "status",
            ),
            filters={
                "client_id": str(client_id),
                "provider": "meta",
                "source_identifier": external_account_id,
            },
            limit=1,
        )
        return rows[0] if rows else None

    async def save_meta_source(
        self,
        *,
        client_id: UUID,
        vertical: str,
        account: MetaAdAccountSummary,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        connection = await self.get_meta_connection(
            client_id=client_id,
            external_account_id=account.external_account_id,
        )
        if connection is None:
            connection = await self._client.insert(
                table="integration_connections",
                row={
                    "client_id": str(client_id),
                    "provider": "meta",
                    "source_identifier": account.external_account_id,
                    "display_name": account.name,
                    "status": "active",
                    "last_connected_at": _utc_now(),
                },
            )
        elif connection.get("status") != "active":
            updated = await self._client.update(
                table="integration_connections",
                values={"status": "active", "last_connected_at": _utc_now()},
                filters={"client_id": str(client_id), "id": str(connection["id"])},
            )
            if len(updated) != 1:
                raise SuperKPersistenceError
            connection = updated[0]

        accounts = await self._client.upsert(
            table="meta_accounts",
            rows=(
                {
                    "client_id": str(client_id),
                    "vertical": vertical,
                    "integration_connection_id": str(connection["id"]),
                    "external_account_id": account.external_account_id,
                    "name": account.name,
                    "currency": account.currency or "INR",
                    "account_timezone": account.account_timezone or "Asia/Kolkata",
                    "status": account.account_status or "active",
                    "last_seen_at": _utc_now(),
                },
            ),
            on_conflict=("client_id", "vertical"),
        )
        if len(accounts) != 1:
            raise SuperKPersistenceError
        return connection, accounts[0]

    async def create_source_sync_run(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
        source_type: str,
        vertical: str,
        source_identifier: str,
        period_start: date,
        period_end: date,
    ) -> dict[str, Any]:
        return await self._client.insert(
            table="sync_runs",
            row={
                "client_id": str(client_id),
                "integration_connection_id": str(connection_id),
                "source_type": source_type,
                "vertical": vertical,
                "source_identifier": source_identifier,
                "status": "running",
                "started_at": _utc_now(),
                "watermark_from": f"{period_start.isoformat()}T00:00:00+00:00",
                "watermark_to": f"{period_end.isoformat()}T23:59:59.999999+00:00",
                "initiated_by_label": "superk_monthly_report",
            },
        )

    async def save_meta_period_insights(
        self,
        *,
        client_id: UUID,
        vertical: str,
        meta_account_id: UUID,
        sync_run_id: UUID,
        period_start: date,
        period_end: date,
        currency: str,
        entity_level: str,
        insights: list[MetaInsightRow],
    ) -> tuple[int, tuple[str, ...]]:
        rows_to_store: list[dict[str, Any]] = []
        hashes: list[str] = []
        for insight in insights:
            external_id = _meta_external_id(insight, entity_level)
            if not external_id:
                continue
            raw_metrics = insight.model_dump(mode="json")
            values = {
                "spend": _decimal_string(insight.spend),
                "currency": currency,
                "impressions": _integer_or_none(insight.impressions),
                "reach": _integer_or_none(insight.reach),
                "link_clicks": _integer_or_none(insight.inline_link_clicks),
                "meta_reported_leads": _meta_leads(insight),
            }
            source_hash = canonical_json_sha256(
                {
                    "period_start": period_start,
                    "period_end": period_end,
                    "entity_level": entity_level,
                    "external_entity_id": external_id,
                    **values,
                }
            )
            hashes.append(source_hash)
            rows_to_store.append(
                {
                    "client_id": str(client_id),
                    "vertical": vertical,
                    "meta_account_id": str(meta_account_id),
                    "sync_run_id": str(sync_run_id),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "entity_level": entity_level,
                    "external_entity_id": external_id,
                    "entity_display_name": _meta_display_name(insight, entity_level),
                    **values,
                    "raw_metrics": raw_metrics,
                    "source_hash": source_hash,
                    "synced_at": _utc_now(),
                }
            )
        if not rows_to_store:
            return 0, ()
        stored = await self._client.upsert(
            table="meta_period_insights",
            rows=rows_to_store,
            on_conflict=(
                "client_id",
                "vertical",
                "meta_account_id",
                "period_start",
                "period_end",
                "entity_level",
                "external_entity_id",
                "source_hash",
            ),
        )
        return len(stored), tuple(hashes)

    async def complete_source_sync_run(
        self,
        *,
        client_id: UUID,
        sync_run_id: UUID,
        status: str,
        rows_read: int,
        rows_written: int,
        source_hash: str | None,
        warnings: tuple[str, ...] = (),
        error_summary: str | None = None,
    ) -> None:
        updated = await self._client.update(
            table="sync_runs",
            values={
                "status": status,
                "finished_at": _utc_now(),
                "rows_read": rows_read,
                "rows_written": rows_written,
                "rows_rejected": len(warnings),
                "source_hash": source_hash,
                "warnings": list(warnings),
                "error_summary": error_summary,
            },
            filters={"client_id": str(client_id), "id": str(sync_run_id)},
        )
        if len(updated) != 1:
            raise SuperKPersistenceError

    async def save_lead_import(
        self,
        *,
        client_id: UUID,
        aggregate: LeadAggregate,
        source_identifier: str,
        payload_hash: str,
    ) -> dict[str, Any]:
        existing = await self._client.select(
            table="lead_json_imports",
            columns=(
                "id",
                "client_id",
                "vertical",
                "source_identifier",
                "source_version",
                "report_month",
                "payload_hash",
                "import_status",
            ),
            filters={
                "client_id": str(client_id),
                "vertical": aggregate.vertical,
                "source_identifier": source_identifier,
                "payload_hash": payload_hash,
            },
            limit=1,
        )
        if existing:
            return existing[0]
        versions = await self._client.select(
            table="lead_json_imports",
            columns=("source_version",),
            filters={
                "client_id": str(client_id),
                "vertical": aggregate.vertical,
                "source_identifier": source_identifier,
            },
            limit=1000,
        )
        source_version = (
            max(
                (int(row.get("source_version") or 0) for row in versions),
                default=0,
            )
            + 1
        )
        return await self._client.insert(
            table="lead_json_imports",
            row={
                "client_id": str(client_id),
                "vertical": aggregate.vertical,
                "source_identifier": source_identifier,
                "source_version": source_version,
                "report_month": f"{aggregate.report_month}-01",
                "payload_hash": payload_hash,
                "schema_version": "superk-lead-aggregate-v1",
                "total_leads": aggregate.total_leads,
                "rtm_leads": aggregate.rtm_leads,
                "comment": aggregate.comment,
                "mapping_preview": {
                    "source_id": "source_id",
                    "report_month": "report_month",
                    "total_leads": "total_leads",
                    "rtm_leads": "rtm_leads",
                },
                "import_status": "accepted",
                "imported_at": _utc_now(),
            },
        )

    async def find_snapshot(
        self,
        *,
        client_id: UUID,
        report_month: date,
        vertical: str,
        formula_version: str,
        input_hash: str | None = None,
    ) -> dict[str, Any] | None:
        filters = {
            "client_id": str(client_id),
            "vertical": vertical,
            "report_month": report_month.isoformat(),
            "formula_version": formula_version,
        }
        if input_hash is not None:
            filters["input_hash"] = input_hash
        rows = await self._client.select(
            table="monthly_report_snapshots",
            columns=(
                "id",
                "client_id",
                "vertical",
                "report_month",
                "snapshot_version",
                "formula_version",
                "input_hash",
                "quality_status",
                "quality_reasons",
                "finalized_at",
            ),
            filters=filters,
            limit=1000,
        )
        if not rows:
            return None
        return max(rows, key=lambda row: int(row.get("snapshot_version") or 0))

    async def load_snapshot_metric_values(
        self,
        *,
        client_id: UUID,
        snapshot_id: UUID,
    ) -> dict[str, Decimal | None]:
        rows = await self._client.select(
            table="metric_snapshots",
            columns=("metric_key", "value"),
            filters={"client_id": str(client_id), "monthly_snapshot_id": str(snapshot_id)},
            limit=1000,
        )
        return {str(row["metric_key"]): _decimal_or_none(row.get("value")) for row in rows}

    async def list_snapshot_metric_ids(
        self,
        *,
        client_id: UUID,
        snapshot_id: UUID,
    ) -> tuple[UUID, ...]:
        rows = await self._client.select(
            table="metric_snapshots",
            columns=("id",),
            filters={"client_id": str(client_id), "monthly_snapshot_id": str(snapshot_id)},
            limit=1000,
        )
        return tuple(UUID(str(row["id"])) for row in rows)

    async def create_snapshot(
        self,
        *,
        result: MonthlyMetricResult,
        meta_sync_run_id: UUID | None,
        gsc_sync_run_id: UUID | None,
        lead_json_import_id: UUID | None,
        knowledge_rows: list[dict[str, Any]],
        knowledge_hash: str,
        kpi_rows: list[dict[str, Any]],
        kpi_hash: str,
        period_start: datetime,
        period_end: datetime,
    ) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
        report_month = date.fromisoformat(f"{result.report_month}-01")
        existing = await self.find_snapshot(
            client_id=result.client_id,
            report_month=report_month,
            vertical=result.vertical,
            formula_version=result.formula_version,
            input_hash=result.input_hash,
        )
        if existing is not None:
            return existing, ()
        latest = await self.find_snapshot(
            client_id=result.client_id,
            report_month=report_month,
            vertical=result.vertical,
            formula_version=result.formula_version,
        )
        snapshot_version = int(latest.get("snapshot_version") or 0) + 1 if latest else 1
        cutoff = _utc_now()
        snapshot = await self._client.insert(
            table="monthly_report_snapshots",
            row={
                "client_id": str(result.client_id),
                "vertical": result.vertical,
                "report_month": report_month.isoformat(),
                "snapshot_version": snapshot_version,
                "formula_version": result.formula_version,
                "input_cutoff_at": cutoff,
                "input_hash": result.input_hash,
                "meta_sync_run_id": str(meta_sync_run_id) if meta_sync_run_id else None,
                "gsc_sync_run_id": str(gsc_sync_run_id) if gsc_sync_run_id else None,
                "lead_json_import_id": str(lead_json_import_id) if lead_json_import_id else None,
                "knowledge_references": _knowledge_references(knowledge_rows),
                "knowledge_hash": knowledge_hash,
                "kpi_references": _kpi_references(kpi_rows),
                "kpi_hash": kpi_hash,
                "quality_status": result.quality_status,
                "quality_reasons": list(result.warnings),
                "finalized_at": cutoff,
            },
        )
        snapshot_id = UUID(str(snapshot["id"]))
        kpi_by_metric = {str(row["metric_key"]): row for row in kpi_rows}
        stored_metrics: list[dict[str, Any]] = []
        for metric in result.metrics:
            kpi = kpi_by_metric.get(metric.metric_key)
            stored_metrics.append(
                await self._client.insert(
                    table="metric_snapshots",
                    row={
                        "client_id": str(result.client_id),
                        "monthly_snapshot_id": str(snapshot_id),
                        "vertical": result.vertical,
                        "kpi_id": str(kpi["id"]) if kpi else None,
                        "metric_key": metric.metric_key,
                        "period_start": period_start.isoformat(),
                        "period_end": period_end.isoformat(),
                        "attribution_level": "client_month",
                        "source_entity_id": None,
                        "entity_display_name": None,
                        "value": _value(metric.value),
                        "unit": metric.unit,
                        "currency": metric.currency,
                        "numerator": _value(metric.numerator),
                        "denominator": _value(metric.denominator),
                        "formula_version": metric.formula_version,
                        "input_cutoff_at": cutoff,
                        "calculated_at": cutoff,
                        "quality_status": metric.quality_status,
                        "quality_reasons": (
                            [] if metric.value is not None else ["source_unavailable"]
                        ),
                        "previous_value": _value(metric.previous_value),
                        "absolute_change": _value(metric.absolute_change),
                        "percentage_change": _value(metric.percentage_change),
                        "kpi_target": _value(metric.kpi_target),
                    },
                )
            )
        return snapshot, tuple(stored_metrics)

    async def create_or_reuse_draft_report(
        self,
        *,
        client_id: UUID,
        vertical: str,
        snapshot_id: UUID,
        period_start: datetime,
        period_end: datetime,
        content: dict[str, Any],
        content_hash: str,
        metric_snapshot_ids: tuple[UUID, ...],
    ) -> dict[str, Any]:
        reports = await self._client.select(
            table="reports",
            columns=("id", "client_id", "status", "monthly_snapshot_id"),
            filters={
                "client_id": str(client_id),
                "monthly_snapshot_id": str(snapshot_id),
                "status": "draft",
            },
            limit=1,
        )
        report = (
            reports[0]
            if reports
            else await self._client.insert(
                table="reports",
                row={
                    "client_id": str(client_id),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "status": "draft",
                    "vertical": vertical,
                    "monthly_snapshot_id": str(snapshot_id),
                },
            )
        )
        report_id = UUID(str(report["id"]))
        versions = await self._client.select(
            table="report_versions",
            columns=("id", "version", "content_hash", "status"),
            filters={"client_id": str(client_id), "report_id": str(report_id)},
            limit=1000,
        )
        matching = next(
            (row for row in versions if str(row.get("content_hash")) == content_hash),
            None,
        )
        if matching is not None:
            return report
        version_number = max((int(row.get("version") or 0) for row in versions), default=0) + 1
        report_version = await self._client.insert(
            table="report_versions",
            row={
                "client_id": str(client_id),
                "report_id": str(report_id),
                "monthly_snapshot_id": str(snapshot_id),
                "version": version_number,
                "schema_version": "superk-franchise-report-v1",
                "content": content,
                "content_hash": content_hash,
                "status": "draft",
                "generated_by_label": "superk_monthly_report",
            },
        )
        if metric_snapshot_ids:
            await self._client.upsert(
                table="report_version_metric_snapshots",
                rows=tuple(
                    {
                        "client_id": str(client_id),
                        "report_version_id": str(report_version["id"]),
                        "metric_snapshot_id": str(metric_id),
                    }
                    for metric_id in metric_snapshot_ids
                ),
                on_conflict=("client_id", "report_version_id", "metric_snapshot_id"),
            )
        return report


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _kpi_is_effective(row: dict[str, Any], report_month: date) -> bool:
    try:
        active_from = date.fromisoformat(str(row["active_from"])[:10])
        active_to_raw = row.get("active_to")
        active_to = date.fromisoformat(str(active_to_raw)[:10]) if active_to_raw else None
    except (KeyError, ValueError, TypeError):
        return False
    return active_from <= report_month and (active_to is None or active_to >= report_month)


def _meta_external_id(insight: MetaInsightRow, entity_level: str) -> str | None:
    value = {
        "account": insight.account_id,
        "campaign": insight.campaign_id,
        "ad_set": insight.adset_id,
        "ad": insight.ad_id,
    }.get(entity_level)
    return str(value) if value else None


def _meta_display_name(insight: MetaInsightRow, entity_level: str) -> str | None:
    raw = insight.model_dump()
    key = {
        "account": "account_name",
        "campaign": "campaign_name",
        "ad_set": "adset_name",
        "ad": "ad_name",
    }.get(entity_level)
    value = raw.get(key) if key else None
    return str(value) if value else None


def _integer_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return parsed if parsed >= 0 else None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _decimal_string(value: Any) -> str | None:
    parsed = _decimal_or_none(value)
    return str(parsed) if parsed is not None and parsed >= 0 else None


def _meta_leads(insight: MetaInsightRow) -> int:
    accepted = {
        "lead",
        "omni_lead",
        "onsite_conversion.lead_grouped",
        "offsite_conversion.fb_pixel_lead",
    }
    total = 0
    for action in insight.actions:
        if str(action.get("action_type") or "") not in accepted:
            continue
        parsed = _integer_or_none(action.get("value"))
        if parsed is not None:
            total += parsed
    return total


def _knowledge_references(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(row["id"]),
            "version": row.get("version"),
            "source_hash": row.get("source_hash"),
        }
        for row in rows
    ]


def _kpi_references(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(row["id"]),
            "metric_key": row.get("metric_key"),
            "target_value": row.get("target_value"),
        }
        for row in rows
    ]


def _value(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
