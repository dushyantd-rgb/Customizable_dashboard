"""Repository for Meta Ads data persistence."""

import hashlib
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.data.supabase import ReportingSupabaseClientProtocol
from app.integrations.meta.models import (
    MetaAdAccountSummary,
    MetaAdSetSummary,
    MetaAdSummary,
    MetaCampaignSummary,
    MetaInsightRow,
)

logger = logging.getLogger(__name__)


class MetaRepository:
    """Repository for Meta Ads configuration and data."""

    def __init__(self, client: ReportingSupabaseClientProtocol) -> None:
        self._client = client

    async def client_exists(self, *, client_id: UUID) -> bool:
        """Check if a client exists."""
        rows = await self._client.select(
            table="clients",
            columns=("id",),
            filters={"id": str(client_id)},
            limit=1,
        )
        return bool(rows)

    async def get_connection(
        self, *, client_id: UUID, provider: str = "meta"
    ) -> dict[str, Any] | None:
        """Get an integration connection for a client."""
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
                "created_at",
                "updated_at",
            ),
            filters={"client_id": str(client_id), "provider": provider},
            limit=1,
        )
        return rows[0] if rows else None

    async def upsert_connection(
        self,
        *,
        client_id: UUID,
        external_account_id: str,
        display_name: str | None,
    ) -> dict[str, Any]:
        """Create or update a Meta integration connection."""
        rows = await self._client.upsert(
            table="integration_connections",
            rows=[
                {
                    "client_id": str(client_id),
                    "provider": "meta",
                    "source_identifier": external_account_id,
                    "display_name": display_name,
                    "status": "active",
                    "last_connected_at": datetime.utcnow().isoformat(),
                }
            ],
            on_conflict=["client_id", "provider", "source_identifier"],
        )
        return rows[0]

    async def upsert_meta_account(
        self,
        *,
        client_id: UUID,
        integration_connection_id: UUID,
        account: MetaAdAccountSummary,
    ) -> dict[str, Any]:
        """Upsert a Meta ad account."""
        rows = await self._client.upsert(
            table="meta_accounts",
            rows=[
                {
                    "client_id": str(client_id),
                    "integration_connection_id": str(integration_connection_id),
                    "external_account_id": account.external_account_id,
                    "name": account.name,
                    "currency": account.currency or "USD",
                    "account_timezone": account.account_timezone or "UTC",
                    "status": account.account_status or "active",
                    "last_seen_at": datetime.utcnow().isoformat(),
                }
            ],
            on_conflict=["client_id", "external_account_id"],
        )
        return rows[0]

    async def upsert_campaigns(
        self,
        *,
        client_id: UUID,
        meta_account_id: UUID,
        campaigns: list[MetaCampaignSummary],
    ) -> list[dict[str, Any]]:
        """Upsert campaigns for a Meta account."""
        if not campaigns:
            return []

        rows = await self._client.upsert(
            table="meta_campaigns",
            rows=[
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
            ],
            on_conflict=["client_id", "meta_account_id", "external_campaign_id"],
        )
        return rows

    async def upsert_ad_sets(
        self,
        *,
        client_id: UUID,
        meta_account_id: UUID,
        ad_sets: list[MetaAdSetSummary],
    ) -> list[dict[str, Any]]:
        """Upsert ad sets for a Meta account."""
        if not ad_sets:
            return []

        rows = await self._client.upsert(
            table="meta_ad_sets",
            rows=[
                {
                    "client_id": str(client_id),
                    "meta_account_id": str(meta_account_id),
                    "external_ad_set_id": ad_set.external_ad_set_id,
                    "external_campaign_id": ad_set.external_campaign_id,
                    "name": ad_set.name,
                    "status": ad_set.status,
                    "effective_status": ad_set.effective_status,
                }
                for ad_set in ad_sets
            ],
            on_conflict=["client_id", "meta_account_id", "external_ad_set_id"],
        )
        return rows

    async def upsert_ads(
        self,
        *,
        client_id: UUID,
        meta_account_id: UUID,
        ads: list[MetaAdSummary],
    ) -> list[dict[str, Any]]:
        """Upsert ads for a Meta account."""
        if not ads:
            return []

        rows = await self._client.upsert(
            table="meta_ads",
            rows=[
                {
                    "client_id": str(client_id),
                    "meta_account_id": str(meta_account_id),
                    "external_ad_id": ad.external_ad_id,
                    "external_ad_set_id": ad.external_ad_set_id,
                    "name": ad.name,
                    "creative_id": ad.creative_id,
                    "status": ad.status,
                    "effective_status": ad.effective_status,
                }
                for ad in ads
            ],
            on_conflict=["client_id", "meta_account_id", "external_ad_id"],
        )
        return rows

    async def upsert_insights(
        self,
        *,
        client_id: UUID,
        meta_account_id: UUID,
        sync_run_id: UUID,
        insights: list[MetaInsightRow],
    ) -> list[dict[str, Any]]:
        """Upsert daily insights with idempotency."""
        if not insights:
            return []

        rows_to_insert = []
        for insight in insights:
            # Determine entity level and ID
            if insight.ad_id:
                entity_level = "ad"
                external_entity_id = insight.ad_id
            elif insight.adset_id:
                entity_level = "ad_set"
                external_entity_id = insight.adset_id
            elif insight.campaign_id:
                entity_level = "campaign"
                external_entity_id = insight.campaign_id
            else:
                entity_level = "account"
                external_entity_id = insight.account_id

            # Parse metrics
            impressions = int(insight.impressions) if insight.impressions else 0
            reach = int(insight.reach) if insight.reach else 0
            clicks = int(insight.clicks) if insight.clicks else 0
            spend = Decimal(insight.spend) if insight.spend else Decimal("0")

            # Extract lead and conversion counts
            meta_leads = 0
            meta_conversions = 0
            for action in insight.actions or []:
                action_type = action.get("action_type", "")
                value = action.get("value", "0")
                if action_type == "lead":
                    meta_leads = int(value)
                elif action_type == "offsite_conversion":
                    meta_conversions += int(value)

            # Calculate conversion value
            conversion_value = None
            for action_value in insight.action_values or []:
                if action_value.get("action_type") == "offsite_conversion":
                    conversion_value = Decimal(action_value.get("value", "0"))

            # Create deterministic hash for idempotency
            insight_hash = hashlib.sha256(
                f"{client_id}|{external_entity_id}|{insight.date_start}|{entity_level}".encode()
            ).hexdigest()

            rows_to_insert.append(
                {
                    "client_id": str(client_id),
                    "meta_account_id": str(meta_account_id),
                    "report_date": insight.date_start,
                    "entity_level": entity_level,
                    "external_entity_id": external_entity_id,
                    "spend": str(spend),
                    "currency": "USD",  # Will be replaced with account currency
                    "impressions": impressions,
                    "reach": reach,
                    "clicks": clicks,
                    "meta_leads": meta_leads,
                    "meta_conversions": meta_conversions,
                    "conversion_value": str(conversion_value) if conversion_value else None,
                    "raw_metrics": insight.model_dump(),
                    "sync_run_id": str(sync_run_id),
                    "source_updated_at": datetime.utcnow().isoformat(),
                }
            )

        rows = await self._client.upsert(
            table="meta_daily_insights",
            rows=rows_to_insert,
            on_conflict=[
                "client_id",
                "meta_account_id",
                "report_date",
                "entity_level",
                "external_entity_id",
            ],
        )
        return rows

    async def create_sync_run(
        self,
        *,
        client_id: UUID,
        integration_connection_id: UUID,
        source_type: str = "meta",
        watermark_from: datetime | None = None,
        watermark_to: datetime | None = None,
        initiated_by: str | None = None,
    ) -> dict[str, Any]:
        """Create a new sync run record."""
        row = {
            "client_id": str(client_id),
            "integration_connection_id": str(integration_connection_id),
            "source_type": source_type,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "watermark_from": watermark_from.isoformat() if watermark_from else None,
            "watermark_to": watermark_to.isoformat() if watermark_to else None,
            "initiated_by_label": initiated_by,
        }
        inserted = await self._client.insert(table="sync_runs", row=row)
        return inserted

    async def complete_sync_run(
        self,
        *,
        client_id: UUID,
        sync_run_id: UUID,
        status: str,
        rows_read: int = 0,
        rows_written: int = 0,
        rows_rejected: int = 0,
        error_summary: str | None = None,
    ) -> dict[str, Any]:
        """Mark a sync run as complete."""
        rows = await self._client.update(
            table="sync_runs",
            values={
                "status": status,
                "finished_at": datetime.utcnow().isoformat(),
                "rows_read": rows_read,
                "rows_written": rows_written,
                "rows_rejected": rows_rejected,
                "error_summary": error_summary,
            },
            filters={"client_id": str(client_id), "id": str(sync_run_id)},
        )
        return rows[0] if rows else {}

    async def get_sync_runs(
        self, *, client_id: UUID, source_type: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent sync runs for a client."""
        filters = {"client_id": str(client_id)}
        if source_type:
            filters["source_type"] = source_type

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
            filters=filters,
            limit=limit,
        )
        return rows
