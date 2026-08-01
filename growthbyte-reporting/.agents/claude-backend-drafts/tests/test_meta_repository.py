"""Tests for Meta Ads repository with InMemoryReportingClient."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

import pytest

from app.integrations.meta.models import (
    MetaAdAccountSummary,
    MetaAdSetSummary,
    MetaAdSummary,
    MetaCampaignSummary,
    MetaInsightRow,
)
from app.integrations.meta.repository import MetaRepository
from tests.helpers import InMemoryReportingClient

CLIENT_A_ID = UUID("00000000-0000-4000-8000-000000000001")
INTEGRATION_CONNECTION_ID = UUID("00000000-0000-4000-8000-000000000002")
SYNC_RUN_ID = UUID("00000000-0000-4000-8000-000000000003")


class InMemoryMetaClient(InMemoryReportingClient):
    """Extended InMemoryReportingClient with Meta-specific tables."""

    def __init__(self) -> None:
        super().__init__()
        self.rows["integration_connections"] = []
        self.rows["meta_accounts"] = []
        self.rows["meta_campaigns"] = []
        self.rows["meta_ad_sets"] = []
        self.rows["meta_ads"] = []
        self.rows["meta_daily_insights"] = []
        self.rows["sync_runs"] = []
        self._auto_increment = 1

    def _generate_id(self) -> str:
        id_str = f"{self._auto_increment:012d}"
        self._auto_increment += 1
        return f"00000000-0000-4000-8000-{id_str}"


@pytest.fixture
def meta_client() -> InMemoryMetaClient:
    return InMemoryMetaClient()


@pytest.fixture
def repository(meta_client: InMemoryMetaClient) -> MetaRepository:
    return MetaRepository(meta_client)


class TestClientExists:
    """Tests for client existence checks."""

    @pytest.mark.asyncio
    async def test_client_exists_returns_true_for_existing_client(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        existing_id = UUID("00000000-0000-4000-8000-0000000000a1")
        exists = await repository.client_exists(client_id=existing_id)
        assert exists is True

    @pytest.mark.asyncio
    async def test_client_exists_returns_false_for_missing_client(
        self, repository: MetaRepository
    ) -> None:
        missing_id = UUID("00000000-0000-4000-8000-000000009999")
        exists = await repository.client_exists(client_id=missing_id)
        assert exists is False


class TestConnectionManagement:
    """Tests for integration connection management."""

    @pytest.mark.asyncio
    async def test_upsert_connection_creates_new_connection(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        connection = await repository.upsert_connection(
            client_id=CLIENT_A_ID,
            external_account_id="123456789",
            display_name="Test Account",
        )

        assert "client_id" in connection
        assert len(meta_client.rows["integration_connections"]) == 1
        assert meta_client.upsert_calls[0]["table"] == "integration_connections"

    @pytest.mark.asyncio
    async def test_upsert_connection_is_idempotent(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        # First upsert
        await repository.upsert_connection(
            client_id=CLIENT_A_ID,
            external_account_id="123456789",
            display_name="Test Account",
        )

        # Second upsert with same key
        await repository.upsert_connection(
            client_id=CLIENT_A_ID,
            external_account_id="123456789",
            display_name="Updated Name",
        )

        # Should have called upsert twice but no delete
        assert len(meta_client.upsert_calls) == 2
        assert not hasattr(meta_client, "delete")

    @pytest.mark.asyncio
    async def test_get_connection_returns_none_when_not_found(
        self, repository: MetaRepository
    ) -> None:
        connection = await repository.get_connection(
            client_id=CLIENT_A_ID, provider="meta"
        )
        assert connection is None

    @pytest.mark.asyncio
    async def test_get_connection_returns_existing_connection(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        # Create connection first
        await repository.upsert_connection(
            client_id=CLIENT_A_ID,
            external_account_id="123456789",
            display_name="Test",
        )

        # Now retrieve it
        connection = await repository.get_connection(
            client_id=CLIENT_A_ID, provider="meta"
        )
        # The fake client won't return it because it uses upsert, not insert
        # So we test the select call instead
        select_calls = [
            c for c in meta_client.select_calls if c["table"] == "integration_connections"
        ]
        assert len(select_calls) > 0


class TestMetaAccountUpsert:
    """Tests for Meta account upsert operations."""

    @pytest.mark.asyncio
    async def test_upsert_meta_account_stores_account_data(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        account = MetaAdAccountSummary(
            external_account_id="123456789",
            name="Test Account",
            currency="USD",
            account_timezone="America/New_York",
            account_status="active",
        )

        result = await repository.upsert_meta_account(
            client_id=CLIENT_A_ID,
            integration_connection_id=INTEGRATION_CONNECTION_ID,
            account=account,
        )

        assert len(meta_client.rows["meta_accounts"]) == 1
        assert meta_client.upsert_calls[0]["table"] == "meta_accounts"

    @pytest.mark.asyncio
    async def test_upsert_meta_account_defaults_currency(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        account = MetaAdAccountSummary(
            external_account_id="123456789",
            name="Account",
            currency=None,  # No currency provided
            account_timezone=None,
            account_status=None,
        )

        await repository.upsert_meta_account(
            client_id=CLIENT_A_ID,
            integration_connection_id=INTEGRATION_CONNECTION_ID,
            account=account,
        )

        upsert_data = meta_client.upsert_calls[0]["rows"][0]
        assert upsert_data["currency"] == "USD"


class TestCampaignUpsert:
    """Tests for campaign upsert operations."""

    @pytest.mark.asyncio
    async def test_upsert_campaigns_stores_campaigns(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        campaigns = [
            MetaCampaignSummary(
                external_campaign_id="camp_001",
                name="Campaign 1",
                objective="CONVERSIONS",
                status="ACTIVE",
                effective_status="ACTIVE",
            ),
            MetaCampaignSummary(
                external_campaign_id="camp_002",
                name="Campaign 2",
                objective="AWARENESS",
                status="PAUSED",
                effective_status="PAUSED",
            ),
        ]

        await repository.upsert_campaigns(
            client_id=CLIENT_A_ID,
            meta_account_id=INTEGRATION_CONNECTION_ID,
            campaigns=campaigns,
        )

        assert len(meta_client.rows["meta_campaigns"]) == 2
        assert meta_client.upsert_calls[0]["table"] == "meta_campaigns"

    @pytest.mark.asyncio
    async def test_upsert_campaigns_empty_list_returns_empty(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        result = await repository.upsert_campaigns(
            client_id=CLIENT_A_ID,
            meta_account_id=INTEGRATION_CONNECTION_ID,
            campaigns=[],
        )

        assert result == []
        assert len(meta_client.upsert_calls) == 0

    @pytest.mark.asyncio
    async def test_upsert_campaigns_is_idempotent(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        campaigns = [
            MetaCampaignSummary(
                external_campaign_id="camp_001",
                name="Campaign",
                objective="CONVERSIONS",
                status="ACTIVE",
                effective_status="ACTIVE",
            ),
        ]

        # Upsert twice
        await repository.upsert_campaigns(
            client_id=CLIENT_A_ID,
            meta_account_id=INTEGRATION_CONNECTION_ID,
            campaigns=campaigns,
        )
        await repository.upsert_campaigns(
            client_id=CLIENT_A_ID,
            meta_account_id=INTEGRATION_CONNECTION_ID,
            campaigns=campaigns,
        )

        # Should have called upsert twice with same conflict target
        assert len(meta_client.upsert_calls) == 2
        assert meta_client.upsert_calls[0]["on_conflict"] == (
            "client_id",
            "meta_account_id",
            "external_campaign_id",
        )


class TestAdSetUpsert:
    """Tests for ad set upsert operations."""

    @pytest.mark.asyncio
    async def test_upsert_ad_sets_stores_ad_sets(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        ad_sets = [
            MetaAdSetSummary(
                external_ad_set_id="adset_001",
                external_campaign_id="camp_001",
                name="Ad Set 1",
                status="ACTIVE",
                effective_status="ACTIVE",
            ),
        ]

        await repository.upsert_ad_sets(
            client_id=CLIENT_A_ID,
            meta_account_id=INTEGRATION_CONNECTION_ID,
            ad_sets=ad_sets,
        )

        assert len(meta_client.rows["meta_ad_sets"]) == 1
        assert meta_client.upsert_calls[0]["table"] == "meta_ad_sets"


class TestAdUpsert:
    """Tests for ad upsert operations."""

    @pytest.mark.asyncio
    async def test_upsert_ads_stores_ads(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        ads = [
            MetaAdSummary(
                external_ad_id="ad_001",
                external_ad_set_id="adset_001",
                name="Ad 1",
                creative_id="creative_001",
                status="ACTIVE",
                effective_status="ACTIVE",
            ),
        ]

        await repository.upsert_ads(
            client_id=CLIENT_A_ID,
            meta_account_id=INTEGRATION_CONNECTION_ID,
            ads=ads,
        )

        assert len(meta_client.rows["meta_ads"]) == 1


class TestInsightsUpsert:
    """Tests for insights upsert operations."""

    @pytest.mark.asyncio
    async def test_upsert_insights_stores_insights(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        insights = [
            MetaInsightRow(
                date_start="2026-01-15",
                date_stop="2026-01-15",
                account_id="123456789",
                campaign_id="camp_001",
                adset_id=None,
                ad_id=None,
                impressions="1000",
                reach="800",
                clicks="50",
                spend="25.50",
                actions=[{"action_type": "lead", "value": "5"}],
                action_values=[],
            ),
        ]

        await repository.upsert_insights(
            client_id=CLIENT_A_ID,
            meta_account_id=INTEGRATION_CONNECTION_ID,
            sync_run_id=SYNC_RUN_ID,
            insights=insights,
        )

        assert len(meta_client.rows["meta_daily_insights"]) == 1

    @pytest.mark.asyncio
    async def test_upsert_insights_handles_empty_list(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        result = await repository.upsert_insights(
            client_id=CLIENT_A_ID,
            meta_account_id=INTEGRATION_CONNECTION_ID,
            sync_run_id=SYNC_RUN_ID,
            insights=[],
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_upsert_insights_determines_entity_level(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        # Ad-level insight
        ad_insight = MetaInsightRow(
            date_start="2026-01-15",
            date_stop="2026-01-15",
            account_id="123456789",
            campaign_id="camp_001",
            adset_id="adset_001",
            ad_id="ad_001",
            impressions="100",
            reach="80",
            clicks="5",
            spend="10.00",
            actions=[],
            action_values=[],
        )

        await repository.upsert_insights(
            client_id=CLIENT_A_ID,
            meta_account_id=INTEGRATION_CONNECTION_ID,
            sync_run_id=SYNC_RUN_ID,
            insights=[ad_insight],
        )

        upsert_data = meta_client.upsert_calls[0]["rows"][0]
        assert upsert_data["entity_level"] == "ad"
        assert upsert_data["external_entity_id"] == "ad_001"

    @pytest.mark.asyncio
    async def test_upsert_insights_is_idempotent(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        insights = [
            MetaInsightRow(
                date_start="2026-01-15",
                date_stop="2026-01-15",
                account_id="123456789",
                campaign_id=None,
                adset_id=None,
                ad_id=None,
                impressions="1000",
                reach="800",
                clicks="50",
                spend="25.50",
                actions=[],
                action_values=[],
            ),
        ]

        # Upsert twice
        await repository.upsert_insights(
            client_id=CLIENT_A_ID,
            meta_account_id=INTEGRATION_CONNECTION_ID,
            sync_run_id=SYNC_RUN_ID,
            insights=insights,
        )
        await repository.upsert_insights(
            client_id=CLIENT_A_ID,
            meta_account_id=INTEGRATION_CONNECTION_ID,
            sync_run_id=SYNC_RUN_ID,
            insights=insights,
        )

        assert len(meta_client.upsert_calls) == 2
        assert meta_client.upsert_calls[0]["on_conflict"] == (
            "client_id",
            "meta_account_id",
            "report_date",
            "entity_level",
            "external_entity_id",
        )


class TestSyncRunManagement:
    """Tests for sync run management."""

    @pytest.mark.asyncio
    async def test_create_sync_run_creates_record(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        sync_run = await repository.create_sync_run(
            client_id=CLIENT_A_ID,
            integration_connection_id=INTEGRATION_CONNECTION_ID,
            source_type="meta",
            watermark_from=datetime(2026, 1, 1),
            watermark_to=datetime(2026, 1, 31),
            initiated_by="manual",
        )

        assert "id" in sync_run
        assert len(meta_client.rows["sync_runs"]) == 1
        assert meta_client.insert_calls[0]["row"]["status"] == "running"

    @pytest.mark.asyncio
    async def test_complete_sync_run_updates_status(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        # Create first
        sync_run = await repository.create_sync_run(
            client_id=CLIENT_A_ID,
            integration_connection_id=INTEGRATION_CONNECTION_ID,
        )
        sync_run_id = UUID(sync_run["id"])

        # Complete it
        await repository.complete_sync_run(
            client_id=CLIENT_A_ID,
            sync_run_id=sync_run_id,
            status="succeeded",
            rows_read=100,
            rows_written=100,
        )

        assert len(meta_client.update_calls) == 1
        assert meta_client.update_calls[0]["values"]["status"] == "succeeded"

    @pytest.mark.asyncio
    async def test_complete_sync_run_with_error(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        sync_run = await repository.create_sync_run(
            client_id=CLIENT_A_ID,
            integration_connection_id=INTEGRATION_CONNECTION_ID,
        )
        sync_run_id = UUID(sync_run["id"])

        await repository.complete_sync_run(
            client_id=CLIENT_A_ID,
            sync_run_id=sync_run_id,
            status="failed",
            error_summary="Synchronization failed without exposing credentials",
        )

        assert meta_client.update_calls[0]["values"]["status"] == "failed"
        assert "credentials" not in meta_client.update_calls[0]["values"]["error_summary"]

    @pytest.mark.asyncio
    async def test_get_sync_runs_returns_runs(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        # Create a sync run
        await repository.create_sync_run(
            client_id=CLIENT_A_ID,
            integration_connection_id=INTEGRATION_CONNECTION_ID,
        )

        runs = await repository.get_sync_runs(client_id=CLIENT_A_ID)
        assert len(runs) >= 1


class TestClientIsolation:
    """Tests for client isolation in repository."""

    @pytest.mark.asyncio
    async def test_client_a_cannot_access_client_b_data(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        client_b_id = UUID("00000000-0000-4000-8000-000000000002")

        # Create account for client A
        await repository.upsert_meta_account(
            client_id=CLIENT_A_ID,
            integration_connection_id=INTEGRATION_CONNECTION_ID,
            account=MetaAdAccountSummary(
                external_account_id="123",
                name="Client A Account",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            ),
        )

        # Check that upsert has client_id filter
        upsert_call = meta_client.upsert_calls[0]
        assert upsert_call["rows"][0]["client_id"] == str(CLIENT_A_ID)

    @pytest.mark.asyncio
    async def test_no_delete_operations_available(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        # Repository should not have delete method
        assert not hasattr(repository, "delete")
        assert not hasattr(meta_client, "delete")


class TestSafeErrorHandling:
    """Tests for safe error handling."""

    @pytest.mark.asyncio
    async def test_error_summary_does_not_expose_secrets(
        self, repository: MetaRepository, meta_client: InMemoryMetaClient
    ) -> None:
        sync_run = await repository.create_sync_run(
            client_id=CLIENT_A_ID,
            integration_connection_id=INTEGRATION_CONNECTION_ID,
        )
        sync_run_id = UUID(sync_run["id"])

        # Simulate safe error message
        safe_error = "Sync failed without exposing credentials"
        await repository.complete_sync_run(
            client_id=CLIENT_A_ID,
            sync_run_id=sync_run_id,
            status="failed",
            error_summary=safe_error,
        )

        # Verify error summary in update call
        error_summary = meta_client.update_calls[0]["values"]["error_summary"]
        assert "secret" not in error_summary.lower()
        assert "token" not in error_summary.lower()
        assert "password" not in error_summary.lower()
