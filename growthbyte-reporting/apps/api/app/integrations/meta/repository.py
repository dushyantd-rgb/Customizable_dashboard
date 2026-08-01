"""Schema-aligned, client-scoped persistence for Meta Ads data."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.core.errors import SafeApplicationError
from app.data.supabase import ReportingSupabaseClientProtocol
from app.integrations.meta.models import (
    MetaAdAccountSummary,
    MetaAdSetSummary,
    MetaAdSummary,
    MetaCampaignSummary,
    MetaInsightRow,
)


class MetaConfigurationError(SafeApplicationError):
    code = "invalid_meta_configuration"
    safe_message = "The Meta account configuration is invalid"
    status_code = 422


class MetaConnectionRequiredError(SafeApplicationError):
    code = "meta_connection_required"
    safe_message = "Configure a Meta ad account for this client first"
    status_code = 409


class MetaDataReferenceError(SafeApplicationError):
    code = "meta_source_reference_missing"
    safe_message = "Meta returned an incomplete entity hierarchy"
    status_code = 502


class MetaRepository:
    def __init__(self, client: ReportingSupabaseClientProtocol) -> None:
        self._client = client

    async def client_exists(self, *, client_id: UUID) -> bool:
        rows = await self._client.select(
            table="clients",
            columns=("id",),
            filters={"id": str(client_id)},
            limit=1,
        )
        return bool(rows)

    async def get_connection(self, *, client_id: UUID) -> dict[str, Any] | None:
        rows = await self._client.select(
            table="integration_connections",
            columns=(
                "id",
                "client_id",
                "provider",
                "source_identifier",
                "display_name",
                "status",
                "last_connected_at",
            ),
            filters={"client_id": str(client_id), "provider": "meta"},
            limit=1,
        )
        return rows[0] if rows else None

    async def save_connection(
        self,
        *,
        client_id: UUID,
        external_account_id: str,
        display_name: str | None,
    ) -> dict[str, Any]:
        values = {
            "source_identifier": external_account_id,
            "display_name": display_name,
            "status": "active",
            "last_connected_at": _utc_now(),
        }
        existing = await self.get_connection(client_id=client_id)
        if existing is not None:
            rows = await self._client.update(
                table="integration_connections",
                values=values,
                filters={"client_id": str(client_id), "id": str(existing["id"])},
            )
            if len(rows) != 1:
                raise MetaConfigurationError
            return rows[0]
        return await self._client.insert(
            table="integration_connections",
            row={"client_id": str(client_id), "provider": "meta", **values},
        )

    async def save_meta_account(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
        account: MetaAdAccountSummary,
    ) -> dict[str, Any]:
        values = {
            "integration_connection_id": str(connection_id),
            "external_account_id": account.external_account_id,
            "name": account.name,
            "currency": account.currency or "USD",
            "account_timezone": account.account_timezone or "UTC",
            "status": account.account_status or "active",
            "last_seen_at": _utc_now(),
        }
        existing = await self.get_meta_account(client_id=client_id)
        if existing is not None:
            rows = await self._client.update(
                table="meta_accounts",
                values=values,
                filters={"client_id": str(client_id), "id": str(existing["id"])},
            )
            if len(rows) != 1:
                raise MetaConfigurationError
            return rows[0]
        return await self._client.insert(
            table="meta_accounts",
            row={"client_id": str(client_id), **values},
        )

    async def get_meta_account(self, *, client_id: UUID) -> dict[str, Any] | None:
        rows = await self._client.select(
            table="meta_accounts",
            columns=(
                "id",
                "client_id",
                "integration_connection_id",
                "external_account_id",
                "name",
                "currency",
                "account_timezone",
                "status",
            ),
            filters={"client_id": str(client_id)},
            limit=1,
        )
        return rows[0] if rows else None

    async def upsert_campaigns(
        self,
        *,
        client_id: UUID,
        meta_account_id: UUID,
        campaigns: list[MetaCampaignSummary],
    ) -> int:
        if not campaigns:
            return 0
        rows = await self._client.upsert(
            table="meta_campaigns",
            rows=tuple(
                {
                    "client_id": str(client_id),
                    "meta_account_id": str(meta_account_id),
                    "external_campaign_id": campaign.external_campaign_id,
                    "name": campaign.name,
                    "objective": campaign.objective,
                    "status": campaign.status,
                    "effective_status": campaign.effective_status,
                }
                for campaign in campaigns
            ),
            on_conflict=("client_id", "meta_account_id", "external_campaign_id"),
        )
        return len(rows)

    async def upsert_ad_sets(
        self,
        *,
        client_id: UUID,
        meta_account_id: UUID,
        ad_sets: list[MetaAdSetSummary],
    ) -> int:
        rows_to_upsert: list[dict[str, Any]] = []
        for ad_set in ad_sets:
            if not ad_set.external_campaign_id:
                raise MetaDataReferenceError
            campaign = await self._find_one(
                table="meta_campaigns",
                columns=("id",),
                filters={
                    "client_id": str(client_id),
                    "meta_account_id": str(meta_account_id),
                    "external_campaign_id": ad_set.external_campaign_id,
                },
            )
            if campaign is None:
                raise MetaDataReferenceError
            rows_to_upsert.append(
                {
                    "client_id": str(client_id),
                    "meta_account_id": str(meta_account_id),
                    "campaign_id": str(campaign["id"]),
                    "external_ad_set_id": ad_set.external_ad_set_id,
                    "name": ad_set.name,
                    "status": ad_set.status,
                    "effective_status": ad_set.effective_status,
                }
            )
        if not rows_to_upsert:
            return 0
        rows = await self._client.upsert(
            table="meta_ad_sets",
            rows=rows_to_upsert,
            on_conflict=("client_id", "meta_account_id", "external_ad_set_id"),
        )
        return len(rows)

    async def upsert_ads(
        self,
        *,
        client_id: UUID,
        meta_account_id: UUID,
        ads: list[MetaAdSummary],
    ) -> int:
        rows_to_upsert: list[dict[str, Any]] = []
        for ad in ads:
            if not ad.external_ad_set_id:
                raise MetaDataReferenceError
            ad_set = await self._find_one(
                table="meta_ad_sets",
                columns=("id", "campaign_id"),
                filters={
                    "client_id": str(client_id),
                    "meta_account_id": str(meta_account_id),
                    "external_ad_set_id": ad.external_ad_set_id,
                },
            )
            if ad_set is None:
                raise MetaDataReferenceError
            rows_to_upsert.append(
                {
                    "client_id": str(client_id),
                    "meta_account_id": str(meta_account_id),
                    "campaign_id": str(ad_set["campaign_id"]),
                    "ad_set_id": str(ad_set["id"]),
                    "external_ad_id": ad.external_ad_id,
                    "name": ad.name,
                    "creative_id": ad.creative_id,
                    "status": ad.status,
                    "effective_status": ad.effective_status,
                }
            )
        if not rows_to_upsert:
            return 0
        rows = await self._client.upsert(
            table="meta_ads",
            rows=rows_to_upsert,
            on_conflict=("client_id", "meta_account_id", "external_ad_id"),
        )
        return len(rows)

    async def upsert_insights(
        self,
        *,
        client_id: UUID,
        meta_account_id: UUID,
        sync_run_id: UUID,
        currency: str,
        insights: list[MetaInsightRow],
    ) -> int:
        rows_to_upsert: list[dict[str, Any]] = []
        for insight in insights:
            level, external_entity_id, table = _insight_identity(insight)
            entity = await self._find_one(
                table=table,
                columns=("id",),
                filters={
                    "client_id": str(client_id),
                    "meta_account_id": str(meta_account_id),
                    _external_id_column(level): external_entity_id,
                },
            )
            if entity is None:
                raise MetaDataReferenceError
            leads, conversions, conversion_value = _actions(insight)
            rows_to_upsert.append(
                {
                    "client_id": str(client_id),
                    "meta_account_id": str(meta_account_id),
                    "report_date": insight.date_start,
                    "entity_level": level,
                    "entity_id": str(entity["id"]),
                    "external_entity_id": external_entity_id,
                    "spend": _decimal_string(insight.spend),
                    "currency": currency,
                    "impressions": _integer(insight.impressions),
                    "reach": _integer(insight.reach),
                    "clicks": _integer(insight.clicks),
                    "meta_leads": leads,
                    "meta_conversions": conversions,
                    "conversion_value": conversion_value,
                    "raw_metrics": insight.model_dump(mode="json"),
                    "sync_run_id": str(sync_run_id),
                    "source_updated_at": _utc_now(),
                }
            )
        if not rows_to_upsert:
            return 0
        rows = await self._client.upsert(
            table="meta_daily_insights",
            rows=rows_to_upsert,
            on_conflict=(
                "client_id",
                "meta_account_id",
                "report_date",
                "entity_level",
                "external_entity_id",
            ),
        )
        return len(rows)

    async def create_sync_run(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        return await self._client.insert(
            table="sync_runs",
            row={
                "client_id": str(client_id),
                "integration_connection_id": str(connection_id),
                "source_type": "meta",
                "status": "running",
                "started_at": _utc_now(),
                "watermark_from": f"{date_from}T00:00:00+00:00",
                "watermark_to": f"{date_to}T23:59:59.999999+00:00",
                "initiated_by_label": "manual",
            },
        )

    async def complete_sync_run(
        self,
        *,
        client_id: UUID,
        sync_run_id: UUID,
        status: str,
        rows_read: int = 0,
        rows_written: int = 0,
        warning_count: int = 0,
        error_summary: str | None = None,
    ) -> None:
        rows = await self._client.update(
            table="sync_runs",
            values={
                "status": status,
                "finished_at": _utc_now(),
                "rows_read": rows_read,
                "rows_written": rows_written,
                "rows_rejected": warning_count,
                "error_summary": error_summary,
            },
            filters={"client_id": str(client_id), "id": str(sync_run_id)},
        )
        if len(rows) != 1:
            raise MetaConfigurationError

    async def get_sync_runs(
        self,
        *,
        client_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        normalized_limit = min(max(limit, 1), 100)
        rows = await self._client.select(
            table="sync_runs",
            columns=(
                "id",
                "client_id",
                "source_type",
                "status",
                "started_at",
                "finished_at",
                "rows_read",
                "rows_written",
                "rows_rejected",
                "error_summary",
                "created_at",
            ),
            filters={"client_id": str(client_id), "source_type": "meta"},
            limit=100,
        )
        return sorted(
            rows,
            key=lambda row: str(row.get("started_at") or row.get("created_at") or ""),
            reverse=True,
        )[:normalized_limit]

    async def _find_one(
        self,
        *,
        table: str,
        columns: tuple[str, ...],
        filters: dict[str, str],
    ) -> dict[str, Any] | None:
        rows = await self._client.select(
            table=table,
            columns=columns,
            filters=filters,
            limit=1,
        )
        return rows[0] if rows else None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _insight_identity(insight: MetaInsightRow) -> tuple[str, str, str]:
    if insight.ad_id:
        return "ad", insight.ad_id, "meta_ads"
    if insight.adset_id:
        return "ad_set", insight.adset_id, "meta_ad_sets"
    if insight.campaign_id:
        return "campaign", insight.campaign_id, "meta_campaigns"
    raise MetaDataReferenceError


def _external_id_column(level: str) -> str:
    return {
        "campaign": "external_campaign_id",
        "ad_set": "external_ad_set_id",
        "ad": "external_ad_id",
    }[level]


def _integer(value: str) -> int:
    try:
        return max(0, int(Decimal(value)))
    except (InvalidOperation, ValueError) as error:
        raise MetaDataReferenceError from error


def _decimal_string(value: str) -> str:
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise MetaDataReferenceError from error
    if result < 0:
        raise MetaDataReferenceError
    return str(result)


def _actions(insight: MetaInsightRow) -> tuple[int, int, str | None]:
    leads = 0
    conversions = 0
    for action in insight.actions:
        action_type = str(action.get("action_type", ""))
        count = _integer(str(action.get("value", "0")))
        if action_type == "lead":
            leads += count
        if action_type in {"offsite_conversion", "purchase", "omni_purchase"}:
            conversions += count
    conversion_value = Decimal("0")
    has_conversion_value = False
    for action in insight.action_values:
        if str(action.get("action_type", "")) in {
            "offsite_conversion",
            "purchase",
            "omni_purchase",
        }:
            conversion_value += Decimal(str(action.get("value", "0")))
            has_conversion_value = True
    return leads, conversions, str(conversion_value) if has_conversion_value else None
