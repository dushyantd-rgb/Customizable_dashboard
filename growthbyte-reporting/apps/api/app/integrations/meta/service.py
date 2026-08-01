"""Manual Meta Ads configuration and synchronization service."""

import logging
from uuid import UUID

from app.integrations.meta.client import MetaApiError, MetaGraphClient
from app.integrations.meta.models import (
    MetaAdSetSummary,
    MetaAdSummary,
    MetaCampaignSummary,
    MetaConnectionConfig,
    MetaInsightRow,
    MetaSyncRequest,
    MetaSyncResult,
)
from app.integrations.meta.repository import (
    MetaConfigurationError,
    MetaConnectionRequiredError,
    MetaRepository,
)

logger = logging.getLogger(__name__)


class MetaSyncService:
    def __init__(self, *, meta_client: MetaGraphClient, repository: MetaRepository) -> None:
        self._meta_client = meta_client
        self._repository = repository

    async def discover_accounts(self, *, client_id: UUID):
        if not await self._repository.client_exists(client_id=client_id):
            raise MetaConfigurationError
        if not await self._meta_client.validate_token():
            raise MetaApiError
        return await self._meta_client.discover_ad_accounts()

    async def configure_connection(
        self,
        *,
        client_id: UUID,
        config: MetaConnectionConfig,
    ) -> dict[str, str | None]:
        accounts = await self.discover_accounts(client_id=client_id)
        account = next(
            (
                candidate
                for candidate in accounts
                if candidate.external_account_id == config.external_account_id
            ),
            None,
        )
        if account is None:
            raise MetaConfigurationError
        connection = await self._repository.save_connection(
            client_id=client_id,
            external_account_id=account.external_account_id,
            display_name=config.display_name or account.name,
        )
        meta_account = await self._repository.save_meta_account(
            client_id=client_id,
            connection_id=UUID(str(connection["id"])),
            account=account,
        )
        return {
            "connection_id": str(connection["id"]),
            "meta_account_id": str(meta_account["id"]),
            "external_account_id": account.external_account_id,
            "display_name": config.display_name or account.name,
        }

    async def test_connection(self, *, client_id: UUID) -> bool:
        connection = await self._repository.get_connection(client_id=client_id)
        account = await self._repository.get_meta_account(client_id=client_id)
        if connection is None or account is None:
            return False
        if str(connection["source_identifier"]) != str(account["external_account_id"]):
            return False
        return await self._meta_client.validate_token()

    async def sync_data(
        self,
        *,
        client_id: UUID,
        request: MetaSyncRequest,
    ) -> MetaSyncResult:
        connection = await self._repository.get_connection(client_id=client_id)
        account = await self._repository.get_meta_account(client_id=client_id)
        if connection is None or account is None:
            raise MetaConnectionRequiredError
        external_account_id = str(account["external_account_id"])
        if external_account_id != str(connection["source_identifier"]):
            raise MetaConfigurationError
        meta_account_id = UUID(str(account["id"]))
        sync_run = await self._repository.create_sync_run(
            client_id=client_id,
            connection_id=UUID(str(connection["id"])),
            date_from=request.date_from.isoformat(),
            date_to=request.date_to.isoformat(),
        )
        sync_run_id = UUID(str(sync_run["id"]))
        try:
            campaigns = (
                await self._meta_client.get_campaigns(external_account_id=external_account_id)
                if request.include_campaigns
                else []
            )
            campaigns_written = await self._repository.upsert_campaigns(
                client_id=client_id,
                meta_account_id=meta_account_id,
                campaigns=campaigns,
            )
            ad_sets = (
                await self._meta_client.get_ad_sets(external_account_id=external_account_id)
                if request.include_ad_sets
                else []
            )
            ad_sets_written = await self._repository.upsert_ad_sets(
                client_id=client_id,
                meta_account_id=meta_account_id,
                ad_sets=ad_sets,
            )
            ads = (
                await self._meta_client.get_ads(external_account_id=external_account_id)
                if request.include_ads
                else []
            )
            ads_written = await self._repository.upsert_ads(
                client_id=client_id,
                meta_account_id=meta_account_id,
                ads=ads,
            )
            campaign_ids = {campaign.external_campaign_id for campaign in campaigns}
            ad_set_ids = {ad_set.external_ad_set_id for ad_set in ad_sets}
            ad_ids = {ad.external_ad_id for ad in ads}
            insights_read = 0
            insights_written = 0
            warning_count = 0
            if request.include_insights:
                for level in ("campaign", "adset", "ad"):
                    insights = await self._meta_client.get_insights(
                        external_account_id=external_account_id,
                        date_from=request.date_from.isoformat(),
                        date_to=request.date_to.isoformat(),
                        level=level,
                    )
                    (
                        historical_campaigns,
                        historical_ad_sets,
                        historical_ads,
                    ) = await self._upsert_historical_insight_entities(
                        client_id=client_id,
                        meta_account_id=meta_account_id,
                        insights=insights,
                        campaign_ids=campaign_ids,
                        ad_set_ids=ad_set_ids,
                        ad_ids=ad_ids,
                    )
                    campaigns_written += historical_campaigns
                    ad_sets_written += historical_ad_sets
                    ads_written += historical_ads
                    warning_count += historical_campaigns + historical_ad_sets + historical_ads
                    insights_read += len(insights)
                    insights_written += await self._repository.upsert_insights(
                        client_id=client_id,
                        meta_account_id=meta_account_id,
                        sync_run_id=sync_run_id,
                        currency=str(account.get("currency") or "USD"),
                        insights=insights,
                    )
            rows_read = len(campaigns) + len(ad_sets) + len(ads) + insights_read
            rows_written = campaigns_written + ad_sets_written + ads_written + insights_written
            await self._repository.complete_sync_run(
                client_id=client_id,
                sync_run_id=sync_run_id,
                status="succeeded",
                rows_read=rows_read,
                rows_written=rows_written,
                warning_count=warning_count,
            )
            return MetaSyncResult(
                sync_run_id=str(sync_run_id),
                client_id=str(client_id),
                external_account_id=external_account_id,
                status="succeeded",
                rows_read=rows_read,
                rows_written=rows_written,
                warning_count=warning_count,
                campaigns_synced=campaigns_written,
                ad_sets_synced=ad_sets_written,
                ads_synced=ads_written,
                insights_synced=insights_written,
            )
        except Exception:
            logger.error(
                "Meta sync failed",
                extra={"client_id": str(client_id), "sync_run_id": str(sync_run_id)},
            )
            await self._repository.complete_sync_run(
                client_id=client_id,
                sync_run_id=sync_run_id,
                status="failed",
                error_summary="Meta sync failed safely",
            )
            raise

    async def _upsert_historical_insight_entities(
        self,
        *,
        client_id: UUID,
        meta_account_id: UUID,
        insights: list[MetaInsightRow],
        campaign_ids: set[str],
        ad_set_ids: set[str],
        ad_ids: set[str],
    ) -> tuple[int, int, int]:
        """Persist ID-only entities that Meta retains in insights after entity deletion."""
        campaigns = {
            insight.campaign_id: MetaCampaignSummary(external_campaign_id=insight.campaign_id)
            for insight in insights
            if insight.campaign_id and insight.campaign_id not in campaign_ids
        }
        campaigns_written = await self._repository.upsert_campaigns(
            client_id=client_id,
            meta_account_id=meta_account_id,
            campaigns=list(campaigns.values()),
        )
        campaign_ids.update(campaigns)

        ad_sets = {
            insight.adset_id: MetaAdSetSummary(
                external_ad_set_id=insight.adset_id,
                external_campaign_id=insight.campaign_id,
            )
            for insight in insights
            if insight.adset_id
            and insight.adset_id not in ad_set_ids
            and insight.campaign_id in campaign_ids
        }
        ad_sets_written = await self._repository.upsert_ad_sets(
            client_id=client_id,
            meta_account_id=meta_account_id,
            ad_sets=list(ad_sets.values()),
        )
        ad_set_ids.update(ad_sets)

        ads = {
            insight.ad_id: MetaAdSummary(
                external_ad_id=insight.ad_id,
                external_ad_set_id=insight.adset_id,
            )
            for insight in insights
            if insight.ad_id and insight.ad_id not in ad_ids and insight.adset_id in ad_set_ids
        }
        ads_written = await self._repository.upsert_ads(
            client_id=client_id,
            meta_account_id=meta_account_id,
            ads=list(ads.values()),
        )
        ad_ids.update(ads)
        return campaigns_written, ad_sets_written, ads_written
