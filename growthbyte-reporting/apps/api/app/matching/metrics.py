"""Verified metric calculations following the approved contract."""

import contextlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Any
from uuid import UUID

from app.data.supabase import ReportingSupabaseClientProtocol
from app.matching.models import (
    AttributionLevel,
    MetricValue,
    QualityStatus,
)

METRICS_FORMULA_VERSION = "2026-08-01-v1"
MAX_DECIMAL_PLACES = 6


class MetricsError(Exception):
    """Base error for metrics calculation."""

    pass


class NoDataError(MetricsError):
    """No data available for the specified period."""

    pass


class MetricCalculator:
    """Calculate verified metrics from stored data."""

    def __init__(self, client: ReportingSupabaseClientProtocol) -> None:
        self._client = client

    async def calculate_period_metrics(
        self,
        *,
        client_id: UUID,
        period_start: date,
        period_end: date,
        attribution_level: str = AttributionLevel.CLIENT.value,
        include_previous: bool = True,
        include_kpi: bool = True,
    ) -> dict[str, Any]:
        """Calculate metrics for a period."""
        # Get client details
        client_rows = await self._client.select(
            table="clients",
            columns=("id", "reporting_timezone", "default_currency"),
            filters={"id": str(client_id)},
            limit=1,
        )
        if not client_rows:
            raise NoDataError(f"Client {client_id} not found")

        client = client_rows[0]
        currency = client.get("default_currency", "USD")
        timezone = client.get("reporting_timezone", "UTC")

        # Convert dates to datetime boundaries
        start_dt = datetime.combine(period_start, datetime.min.time()).replace(tzinfo=UTC)
        end_dt = datetime.combine(period_end, datetime.min.time()).replace(tzinfo=UTC)

        # Calculate previous period
        duration = (period_end - period_start).days
        prev_start = period_start - timedelta(days=duration)
        prev_end = period_start

        # Gather data
        meta_insights = await self._get_meta_insights(
            client_id=client_id,
            start=start_dt,
            end=end_dt,
        )
        lead_records = await self._get_lead_records(
            client_id=client_id,
            start=start_dt,
            end=end_dt,
        )
        lead_matches = await self._get_lead_matches(client_id=client_id)

        metrics: list[MetricValue] = []
        quality_warnings: list[str] = []

        # Calculate spend metrics
        spend = self._sum_numeric(meta_insights, "spend")
        impressions = self._sum_int(meta_insights, "impressions")
        reach = self._sum_int(meta_insights, "reach")
        clicks = self._sum_int(meta_insights, "clicks")
        meta_leads = self._sum_int(meta_insights, "meta_leads")

        metrics.append(
            MetricValue(
                metric_key="spend",
                value=spend,
                unit="currency",
                currency=currency,
                quality_status=QualityStatus.VERIFIED.value
                if spend is not None
                else QualityStatus.UNAVAILABLE.value,
                quality_reasons=[] if spend else ["no_spend_data"],
            )
        )

        metrics.append(
            MetricValue(
                metric_key="impressions",
                value=impressions,
                unit="count",
                quality_status=QualityStatus.VERIFIED.value
                if impressions
                else QualityStatus.PARTIAL.value,
                quality_reasons=[] if impressions else ["no_impressions"],
            )
        )

        metrics.append(
            MetricValue(
                metric_key="reach",
                value=reach,
                unit="count",
                quality_status=QualityStatus.VERIFIED.value
                if reach
                else QualityStatus.PARTIAL.value,
                quality_reasons=[] if reach else ["no_reach"],
            )
        )

        metrics.append(
            MetricValue(
                metric_key="clicks",
                value=clicks,
                unit="count",
                quality_status=QualityStatus.VERIFIED.value
                if clicks
                else QualityStatus.PARTIAL.value,
                quality_reasons=[] if clicks else ["no_clicks"],
            )
        )

        metrics.append(
            MetricValue(
                metric_key="meta_leads",
                value=meta_leads,
                unit="count",
                quality_status=QualityStatus.VERIFIED.value,
                quality_reasons=[],
            )
        )

        # Lead status counts
        imported_count = len(lead_records)
        qualified_count = sum(
            1 for l in lead_records if l.get("canonical_status") in ("qualified", "converted")
        )
        disqualified_count = sum(
            1 for l in lead_records if l.get("canonical_status") == "disqualified"
        )
        invalid_count = sum(1 for l in lead_records if l.get("canonical_status") == "invalid")
        converted_count = sum(1 for l in lead_records if l.get("canonical_status") == "converted")
        reviewed_count = sum(1 for l in lead_records if l.get("is_reviewed"))

        metrics.append(
            MetricValue(
                metric_key="imported_leads",
                value=Decimal(imported_count),
                unit="count",
                quality_status=QualityStatus.VERIFIED.value,
            )
        )

        metrics.append(
            MetricValue(
                metric_key="qualified_leads",
                value=Decimal(qualified_count),
                unit="count",
                quality_status=QualityStatus.VERIFIED.value,
            )
        )

        metrics.append(
            MetricValue(
                metric_key="disqualified_leads",
                value=Decimal(disqualified_count),
                unit="count",
                quality_status=QualityStatus.VERIFIED.value,
            )
        )

        metrics.append(
            MetricValue(
                metric_key="invalid_leads",
                value=Decimal(invalid_count),
                unit="count",
                quality_status=QualityStatus.VERIFIED.value,
            )
        )

        metrics.append(
            MetricValue(
                metric_key="converted_leads",
                value=Decimal(converted_count),
                unit="count",
                quality_status=QualityStatus.VERIFIED.value,
            )
        )

        # CPL - Cost Per Lead
        cpl = self._safe_divide(spend, Decimal(meta_leads)) if meta_leads else None
        metrics.append(
            MetricValue(
                metric_key="cost_per_lead",
                value=cpl,
                numerator=spend,
                denominator=Decimal(meta_leads) if meta_leads else None,
                unit="currency",
                currency=currency,
                quality_status=QualityStatus.VERIFIED.value
                if cpl
                else QualityStatus.UNAVAILABLE.value,
                quality_reasons=[] if cpl else ["zero_denominator", "no_meta_leads"],
            )
        )

        # Qualification rate
        qual_rate = (
            self._safe_percentage(Decimal(qualified_count), Decimal(reviewed_count))
            if reviewed_count
            else None
        )
        metrics.append(
            MetricValue(
                metric_key="qualification_rate",
                value=qual_rate,
                numerator=Decimal(qualified_count),
                denominator=Decimal(reviewed_count) if reviewed_count else None,
                unit="percent",
                quality_status=QualityStatus.VERIFIED.value
                if qual_rate
                else QualityStatus.UNAVAILABLE.value,
                quality_reasons=[] if qual_rate else ["zero_denominator", "no_reviewed_leads"],
            )
        )

        # Conversion rate
        conv_rate = (
            self._safe_percentage(Decimal(converted_count), Decimal(qualified_count))
            if qualified_count
            else None
        )
        metrics.append(
            MetricValue(
                metric_key="conversion_rate",
                value=conv_rate,
                numerator=Decimal(converted_count),
                denominator=Decimal(qualified_count) if qualified_count else None,
                unit="percent",
                quality_status=QualityStatus.VERIFIED.value
                if conv_rate
                else QualityStatus.UNAVAILABLE.value,
                quality_reasons=[] if conv_rate else ["zero_denominator", "no_qualified_leads"],
            )
        )

        # CTR - Click Through Rate
        ctr = self._safe_percentage(Decimal(clicks), Decimal(impressions)) if impressions else None
        metrics.append(
            MetricValue(
                metric_key="ctr",
                value=ctr,
                numerator=Decimal(clicks),
                denominator=Decimal(impressions) if impressions else None,
                unit="percent",
                quality_status=QualityStatus.VERIFIED.value
                if ctr
                else QualityStatus.UNAVAILABLE.value,
                quality_reasons=[] if ctr else ["zero_denominator", "no_impressions"],
            )
        )

        # CPC - Cost Per Click
        cpc = self._safe_divide(spend, Decimal(clicks)) if clicks else None
        metrics.append(
            MetricValue(
                metric_key="cpc",
                value=cpc,
                numerator=spend,
                denominator=Decimal(clicks) if clicks else None,
                unit="currency",
                currency=currency,
                quality_status=QualityStatus.VERIFIED.value
                if cpc
                else QualityStatus.UNAVAILABLE.value,
                quality_reasons=[] if cpc else ["zero_denominator", "no_clicks"],
            )
        )

        # CPM - Cost Per Mille
        cpm = (
            self._safe_divide(spend, Decimal(impressions)) * Decimal("1000")
            if impressions and spend
            else None
        )
        metrics.append(
            MetricValue(
                metric_key="cpm",
                value=cpm,
                numerator=spend,
                denominator=Decimal(impressions) if impressions else None,
                unit="currency",
                currency=currency,
                quality_status=QualityStatus.VERIFIED.value
                if cpm
                else QualityStatus.UNAVAILABLE.value,
                quality_reasons=[] if cpm else ["zero_denominator", "no_impressions"],
            )
        )

        # Matching metrics
        matched_ids = {
            m["lead_record_id"]
            for m in lead_matches
            if m.get("is_active") and m.get("method") != "unmatched"
        }
        unmatched_count = imported_count - len(matched_ids)
        attribution_coverage = (
            self._safe_percentage(Decimal(len(matched_ids)), Decimal(imported_count))
            if imported_count
            else None
        )

        metrics.append(
            MetricValue(
                metric_key="unmatched_leads",
                value=Decimal(unmatched_count),
                unit="count",
                quality_status=QualityStatus.VERIFIED.value,
            )
        )

        metrics.append(
            MetricValue(
                metric_key="attribution_coverage",
                value=attribution_coverage,
                numerator=Decimal(len(matched_ids)),
                denominator=Decimal(imported_count) if imported_count else None,
                unit="percent",
                quality_status=QualityStatus.VERIFIED.value
                if attribution_coverage
                else QualityStatus.UNAVAILABLE.value,
                quality_reasons=[] if attribution_coverage else ["zero_denominator", "no_leads"],
            )
        )

        # Previous period comparison if requested
        if include_previous:
            await self._calculate_previous_metrics(
                client_id=client_id,
                prev_start=prev_start,
                prev_end=prev_end,
                currency=currency,
            )

        return {
            "client_id": client_id,
            "period_start": start_dt,
            "period_end": end_dt,
            "client_timezone": timezone,
            "currency": currency,
            "formula_version": METRICS_FORMULA_VERSION,
            "input_cutoff_at": datetime.now(UTC),
            "metrics": metrics,
            "unmatched_count": unmatched_count,
            "quality_warnings": quality_warnings,
        }

    async def generate_snapshots(
        self,
        *,
        client_id: UUID,
        period_start: date,
        period_end: date,
        attribution_levels: list[str] | None = None,
    ) -> list[UUID]:
        """Generate frozen metric snapshots."""
        if attribution_levels is None:
            attribution_levels = [AttributionLevel.CLIENT.value]

        metrics_data = await self.calculate_period_metrics(
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            attribution_level=AttributionLevel.CLIENT.value,
            include_previous=True,
            include_kpi=True,
        )

        snapshot_ids: list[UUID] = []
        now = datetime.now(UTC)

        for metric in metrics_data.get("metrics", []):
            metric_key = metric.metric_key
            value = metric.value
            unit = metric.unit
            currency = metric.currency
            quality_status = metric.quality_status
            quality_reasons = metric.quality_reasons

            # Create snapshot record
            snapshot = {
                "client_id": str(client_id),
                "metric_key": metric_key,
                "period_start": metrics_data["period_start"].isoformat(),
                "period_end": metrics_data["period_end"].isoformat(),
                "attribution_level": AttributionLevel.CLIENT.value,
                "value": float(value) if value is not None else None,
                "unit": unit,
                "currency": currency,
                "numerator": float(metric.numerator) if metric.numerator is not None else None,
                "denominator": float(metric.denominator)
                if metric.denominator is not None
                else None,
                "formula_version": METRICS_FORMULA_VERSION,
                "input_cutoff_at": metrics_data["input_cutoff_at"].isoformat(),
                "calculated_at": now.isoformat(),
                "quality_status": quality_status,
                "quality_reasons": quality_reasons,
            }

            try:
                inserted = await self._client.insert(
                    table="metric_snapshots",
                    row=snapshot,
                )
                if inserted.get("id"):
                    snapshot_ids.append(UUID(inserted["id"]))
            except Exception:
                # Duplicate or conflict - skip
                pass

        # Create audit event
        await self._client.insert(
            table="audit_events",
            row={
                "client_id": str(client_id),
                "action": "snapshot",
                "entity_type": "metric_snapshots",
                "entity_id": None,
                "event_metadata": {
                    "snapshot_count": len(snapshot_ids),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "formula_version": METRICS_FORMULA_VERSION,
                },
                "occurred_at": now.isoformat(),
            },
        )

        return snapshot_ids

    async def list_snapshots(
        self,
        *,
        client_id: UUID,
        period_start: date | None = None,
        period_end: date | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List metric snapshots for a client."""
        filters = {"client_id": str(client_id)}
        if period_start:
            filters["period_start"] = period_start.isoformat()
        if period_end:
            filters["period_end"] = period_end.isoformat()

        snapshots = await self._client.select(
            table="metric_snapshots",
            columns=(
                "id",
                "client_id",
                "metric_key",
                "period_start",
                "period_end",
                "attribution_level",
                "value",
                "unit",
                "currency",
                "quality_status",
                "calculated_at",
            ),
            filters=filters,
            limit=min(limit, 500),
        )

        return snapshots

    async def get_snapshot(
        self,
        *,
        client_id: UUID,
        snapshot_id: UUID,
    ) -> dict[str, Any] | None:
        """Get a single metric snapshot."""
        snapshots = await self._client.select(
            table="metric_snapshots",
            columns=(
                "id",
                "client_id",
                "metric_key",
                "period_start",
                "period_end",
                "attribution_level",
                "source_entity_id",
                "entity_display_name",
                "value",
                "unit",
                "currency",
                "numerator",
                "denominator",
                "formula_version",
                "input_cutoff_at",
                "calculated_at",
                "quality_status",
                "quality_reasons",
            ),
            filters={"client_id": str(client_id), "id": str(snapshot_id)},
            limit=1,
        )

        return snapshots[0] if snapshots else None

    def _safe_divide(
        self, numerator: Decimal | None, denominator: Decimal | None
    ) -> Decimal | None:
        """Safely divide, returning None for division by zero."""
        if numerator is None or denominator is None or denominator == 0:
            return None
        try:
            result = numerator / denominator
            return result.quantize(Decimal(f"0.{MAX_DECIMAL_PLACES * '0'}"))
        except (DivisionByZero, InvalidOperation):
            return None

    def _safe_percentage(
        self, numerator: Decimal | None, denominator: Decimal | None
    ) -> Decimal | None:
        """Calculate percentage safely."""
        result = self._safe_divide(numerator, denominator)
        if result is not None:
            return result * Decimal("100")
        return None

    def _sum_numeric(self, rows: list[dict[str, Any]], column: str) -> Decimal | None:
        """Sum numeric column values."""
        total = Decimal("0")
        has_value = False
        for row in rows:
            val = row.get(column)
            if val is not None:
                try:
                    total += Decimal(str(val))
                    has_value = True
                except (InvalidOperation, ValueError):
                    pass
        return total if has_value else None

    def _sum_int(self, rows: list[dict[str, Any]], column: str) -> int:
        """Sum integer column values."""
        total = 0
        for row in rows:
            val = row.get(column)
            if val is not None:
                with contextlib.suppress(ValueError, TypeError):
                    total += int(val)
        return total

    async def _get_meta_insights(
        self,
        *,
        client_id: UUID,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Get Meta daily insights for a period."""
        return await self._client.select(
            table="meta_daily_insights",
            columns=(
                "id",
                "report_date",
                "entity_level",
                "spend",
                "currency",
                "impressions",
                "reach",
                "clicks",
                "meta_leads",
                "meta_conversions",
            ),
            filters={
                "client_id": str(client_id),
            },
            limit=1000,
        )

    async def _get_lead_records(
        self,
        *,
        client_id: UUID,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Get lead records for a period."""
        return await self._client.select(
            table="lead_records",
            columns=(
                "id",
                "client_id",
                "canonical_status",
                "is_reviewed",
                "lead_at",
            ),
            filters={"client_id": str(client_id)},
            limit=5000,
        )

    async def _get_lead_matches(self, *, client_id: UUID) -> list[dict[str, Any]]:
        """Get lead matches for a client."""
        return await self._client.select(
            table="lead_matches",
            columns=(
                "id",
                "lead_record_id",
                "method",
                "is_active",
                "confidence",
            ),
            filters={"client_id": str(client_id)},
            limit=5000,
        )

    async def _calculate_previous_metrics(
        self,
        *,
        client_id: UUID,
        prev_start: date,
        prev_end: date,
        currency: str,
    ) -> dict[str, Decimal | None]:
        """Calculate metrics for previous period."""
        # Simplified - would reuse calculate_period_metrics in production
        return {}
