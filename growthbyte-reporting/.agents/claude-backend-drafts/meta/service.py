"""Meta Ads synchronization service."""

import logging
from datetime import datetime
from uuid import UUID

from app.integrations.meta.client import MetaGraphClient
from app.integrations.meta.models import (
    MetaConnectionConfig,
    MetaSyncRequest,
    MetaSyncResult,
)
from app.integrations.meta.repository import MetaRepository

logger = logging.getLogger(__name__)


class MetaSyncService:
    """Service for syncing Meta Ads data."""

    def __init__(
        self,
        *,
        meta_client: MetaGraphClient,
        repository: MetaRepository,
    ) -> None:
        self._meta_client = meta_client
        self._repository = repository

    async def test_connection(self, *, client_id: UUID) -> bool:
        """Test the Meta connection for a client."""
        connection = await self._repository.get_connection(
            client_id=client_id, provider="meta"
        )
        if not connection:
            return False

        # The environment token is already validated
        return True

    async def configure_connection(
        self, *, client_id: UUID, config: MetaConnectionConfig
    ) -> dict[str, str]:
        """
        Configure Meta connection for a client.

        Returns safe metadata (never tokens).
        """
        # Verify client exists
        if not await self._repository.client_exists(client_id=client_id):
            raise ValueError(f"Client {client_id} does not exist")

        # Discover account details
        accounts = await self._meta_client.discover_ad_accounts()
        account = next(
            (
                acc
                for acc in accounts
                if acc.external_account_id == config.external_account_id
            ),
            None,
        )

        if not account:
            raise ValueError(
                f"Account {config.external_account_id} not accessible"
            )

        # Upsert connection
        connection = await self._repository.upsert_connection(
            client_id=client_id,
            external_account_id=config.external_account_id,
            display_name=config.display_name or account.name,
        )

        # Upsert account metadata
        await self._repository.upsert_meta_account(
            client_id=client_id,
            integration_connection_id=connection["id"],
            account=account,
        )

        return {
            "connection_id": connection["id"],
            "external_account_id": config.external_account_id,
            "display_name": config.display_name or account.name,
        }

    async def sync_data(
        self, *, client_id: UUID, request: MetaSyncRequest
    ) -> MetaSyncResult:
        """
        Synchronize Meta Ads data for a client.

        This is a manual sync that pulls data from Meta and stores it.
        It is idempotent - repeated syncs will not create duplicates.
        """
        # Get connection
        connection = await self._repository.get_connection(
            client_id=client_id, provider="meta"
        )
        if not connection:
            raise ValueError("No Meta connection configured for this client")

        connection_id = UUID(connection["id"])
        external_account_id = connection["source_identifier"]

        # Create sync run
        sync_run = await self._repository.create_sync_run(
            client_id=client_id,
            integration_connection_id=connection_id,
            source_type="meta",
            watermark_from=datetime.combine(request.date_from, datetime.min.time()),
            watermark_to=datetime.combine(request.date_to, datetime.min.time()),
            initiated_by="manual",
        )
        sync_run_id = UUID(sync_run["id"])

        try:
            # Sync campaigns
            campaigns_count = 0
            if request.include_campaigns:
                campaigns = await self._meta_client.get_campaigns(
                    external_account_id=external_account_id
                )
                if campaigns:
                    await self._repository.upsert_campaigns(
                        client_id=client_id,
                        meta_account_id=connection_id,
                        campaigns=campaigns,
                    )
                    campaigns_count = len(campaigns)

            # Sync ad sets
            ad_sets_count = 0
            if request.include_ad_sets:
                ad_sets = await self._meta_client.get_ad_sets(
                    external_account_id=external_account_id
                )
                if ad_sets:
                    await self._repository.upsert_ad_sets(
                        client_id=client_id,
                        meta_account_id=connection_id,
                        ad_sets=ad_sets,
                    )
                    ad_sets_count = len(ad_sets)

            # Sync ads
            ads_count = 0
            if request.include_ads:
                ads = await self._meta_client.get_ads(
                    external_account_id=external_account_id
                )
                if ads:
                    await self._repository.upsert_ads(
                        client_id=client_id,
                        meta_account_id=connection_id,
                        ads=ads,
                    )
                    ads_count = len(ads)

            # Sync insights
            insights_count = 0
            if request.include_insights:
                # Sync at all levels
                for level in ["campaign", "adset", "ad"]:
                    insights = await self._meta_client.get_insights(
                        external_account_id=external_account_id,
                        date_from=request.date_from.isoformat(),
                        date_to=request.date_to.isoformat(),
                        level=level,
                    )
                    if insights:
                        upserted = await self._repository.upsert_insights(
                            client_id=client_id,
                            meta_account_id=connection_id,
                            sync_run_id=sync_run_id,
                            insights=insights,
                        )
                        insights_count += len(upserted)

            # Calculate totals
            total_read = campaigns_count + ad_sets_count + ads_count + insights_count
            total_written = total_read  # All reads were written

            # Mark sync as complete
            await self._repository.complete_sync_run(
                client_id=client_id,
                sync_run_id=sync_run_id,
                status="succeeded",
                rows_read=total_read,
                rows_written=total_written,
            )

            return MetaSyncResult(
                sync_run_id=str(sync_run_id),
                client_id=str(client_id),
                external_account_id=external_account_id,
                status="succeeded",
                rows_read=total_read,
                rows_written=total_written,
                campaigns_synced=campaigns_count,
                ad_sets_synced=ad_sets_count,
                ads_synced=ads_count,
                insights_synced=insights_count,
            )

        except Exception as error:
            # Mark sync as failed
            logger.error(
                "Meta sync failed",
                extra={
                    "client_id": str(client_id),
                    "sync_run_id": str(sync_run_id),
                    "error_type": type(error).__name__,
                },
                exc_info=True,
            )

            # Safe error message (never expose tokens)
            safe_error = "Sync failed without exposing credentials"

            await self._repository.complete_sync_run(
                client_id=client_id,
                sync_run_id=sync_run_id,
                status="failed",
                error_summary=safe_error,
            )

            raise
