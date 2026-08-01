"""Manual Meta Ads configuration and synchronization service."""

import logging
from uuid import UUID

from app.integrations.meta.client import MetaApiError, MetaGraphClient
from app.integrations.meta.models import MetaConnectionConfig, MetaSyncRequest, MetaSyncResult
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
            insights_read = 0
            insights_written = 0
            if request.include_insights:
                for level in ("campaign", "adset", "ad"):
                    insights = await self._meta_client.get_insights(
                        external_account_id=external_account_id,
                        date_from=request.date_from.isoformat(),
                        date_to=request.date_to.isoformat(),
                        level=level,
                    )
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
            )
            return MetaSyncResult(
                sync_run_id=str(sync_run_id),
                client_id=str(client_id),
                external_account_id=external_account_id,
                status="succeeded",
                rows_read=rows_read,
                rows_written=rows_written,
                warning_count=0,
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
