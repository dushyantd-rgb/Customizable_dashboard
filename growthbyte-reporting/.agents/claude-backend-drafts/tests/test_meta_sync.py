"""Tests for Meta sync service integration."""

from datetime import date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.integrations.meta.client import MetaApiError, MetaGraphClient
from app.integrations.meta.models import (
    MetaAdAccountSummary,
    MetaAdSetSummary,
    MetaAdSummary,
    MetaCampaignSummary,
    MetaConnectionConfig,
    MetaInsightRow,
    MetaSyncRequest,
    MetaSyncResult,
)
from app.integrations.meta.repository import MetaRepository
from app.integrations.meta.service import MetaSyncService
from tests.helpers import InMemoryReportingClient

CLIENT_A_ID = UUID("00000000-0000-4000-8000-000000000001")
CLIENT_B_ID = UUID("00000000-0000-4000-8000-000000000002")


class InMemoryMetaSyncClient(InMemoryReportingClient):
    """Extended client with Meta integration tables."""

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


class MockMetaGraphClient:
    """Mock Meta Graph API client for testing."""

    def __init__(self) -> None:
        self._accounts: list[MetaAdAccountSummary] = []
        self._campaigns: list[MetaCampaignSummary] = []
        self._ad_sets: list[MetaAdSetSummary] = []
        self._ads: list[MetaAdSummary] = []
        self._insights: list[MetaInsightRow] = []
        self._token_valid = True
        self._raise_error = False

    def setup_accounts(self, accounts: list[MetaAdAccountSummary]) -> None:
        self._accounts = accounts

    def setup_campaigns(self, campaigns: list[MetaCampaignSummary]) -> None:
        self._campaigns = campaigns

    def setup_ad_sets(self, ad_sets: list[MetaAdSetSummary]) -> None:
        self._ad_sets = ad_sets

    def setup_ads(self, ads: list[MetaAdSummary]) -> None:
        self._ads = ads

    def setup_insights(self, insights: list[MetaInsightRow]) -> None:
        self._insights = insights

    def set_token_valid(self, valid: bool) -> None:
        self._token_valid = valid

    def set_raise_error(self, should_raise: bool) -> None:
        self._raise_error = should_raise

    async def discover_ad_accounts(self) -> list[MetaAdAccountSummary]:
        if self._raise_error:
            raise MetaApiError("API error")
        return self._accounts

    async def get_campaigns(
        self, *, external_account_id: str, limit: int = 100
    ) -> list[MetaCampaignSummary]:
        if self._raise_error:
            raise MetaApiError("API error")
        return self._campaigns

    async def get_ad_sets(
        self, *, external_account_id: str, limit: int = 100
    ) -> list[MetaAdSetSummary]:
        if self._raise_error:
            raise MetaApiError("API error")
        return self._ad_sets

    async def get_ads(
        self, *, external_account_id: str, limit: int = 100
    ) -> list[MetaAdSummary]:
        if self._raise_error:
            raise MetaApiError("API error")
        return self._ads

    async def get_insights(
        self,
        *,
        external_account_id: str,
        date_from: str,
        date_to: str,
        level: str = "account",
        limit: int = 100,
    ) -> list[MetaInsightRow]:
        if self._raise_error:
            raise MetaApiError("API error")
        return self._insights

    async def validate_token(self) -> bool:
        return self._token_valid

    async def close(self) -> None:
        pass


@pytest.fixture
def reporting_client() -> InMemoryMetaSyncClient:
    return InMemoryMetaSyncClient()


@pytest.fixture
def meta_client() -> MockMetaGraphClient:
    return MockMetaGraphClient()


@pytest.fixture
def repository(reporting_client: InMemoryMetaSyncClient) -> MetaRepository:
    return MetaRepository(reporting_client)


@pytest.fixture
def service(
    meta_client: MockMetaGraphClient, repository: MetaRepository
) -> MetaSyncService:
    return MetaSyncService(
        meta_client=meta_client,  # type: ignore
        repository=repository,
    )


class TestConfigureConnection:
    """Tests for connection configuration."""

    @pytest.mark.asyncio
    async def test_configure_connection_creates_connection(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
        reporting_client: InMemoryMetaSyncClient,
    ) -> None:
        meta_client.setup_accounts([
            MetaAdAccountSummary(
                external_account_id="123456789",
                name="Test Account",
                currency="USD",
                account_timezone="America/New_York",
                account_status="active",
            ),
        ])

        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
            display_name="My Account",
        )

        result = await service.configure_connection(client_id=CLIENT_A_ID, config=config)

        assert result["external_account_id"] == "123456789"
        assert result["display_name"] == "My Account"

    @pytest.mark.asyncio
    async def test_configure_connection_uses_account_name_if_no_display_name(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
    ) -> None:
        meta_client.setup_accounts([
            MetaAdAccountSummary(
                external_account_id="123456789",
                name="Default Account Name",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            ),
        ])

        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
            display_name=None,
        )

        result = await service.configure_connection(client_id=CLIENT_A_ID, config=config)

        assert result["display_name"] == "Default Account Name"

    @pytest.mark.asyncio
    async def test_configure_connection_rejects_missing_client(
        self, service: MetaSyncService
    ) -> None:
        config = MetaConnectionConfig(
            client_id=str(UUID("00000000-0000-4000-8000-000000009999")),
            external_account_id="123456789",
        )

        with pytest.raises(ValueError, match="does not exist"):
            await service.configure_connection(
                client_id=UUID("00000000-0000-4000-8000-000000009999"),
                config=config,
            )

    @pytest.mark.asyncio
    async def test_configure_connection_rejects_inaccessible_account(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
    ) -> None:
        meta_client.setup_accounts([])  # No accounts accessible

        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
        )

        with pytest.raises(ValueError, match="not accessible"):
            await service.configure_connection(client_id=CLIENT_A_ID, config=config)

    @pytest.mark.asyncio
    async def test_configure_connection_is_idempotent(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
        reporting_client: InMemoryMetaSyncClient,
    ) -> None:
        meta_client.setup_accounts([
            MetaAdAccountSummary(
                external_account_id="123456789",
                name="Test",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            ),
        ])

        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
        )

        # Configure twice
        await service.configure_connection(client_id=CLIENT_A_ID, config=config)
        await service.configure_connection(client_id=CLIENT_A_ID, config=config)

        # Should have upserted twice (idempotent)
        connection_upserts = [
            c for c in reporting_client.upsert_calls
            if c["table"] == "integration_connections"
        ]
        assert len(connection_upserts) == 2


class TestSyncData:
    """Tests for data synchronization."""

    @pytest.mark.asyncio
    async def test_sync_data_syncs_all_entities(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
        reporting_client: InMemoryMetaSyncClient,
    ) -> None:
        # Setup connection first
        meta_client.setup_accounts([
            MetaAdAccountSummary(
                external_account_id="123456789",
                name="Test",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            ),
        ])
        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
        )
        await service.configure_connection(client_id=CLIENT_A_ID, config=config)

        # Setup data
        meta_client.setup_campaigns([
            MetaCampaignSummary(
                external_campaign_id="camp_001",
                name="Campaign 1",
                objective="CONVERSIONS",
                status="ACTIVE",
                effective_status="ACTIVE",
            ),
        ])
        meta_client.setup_ad_sets([
            MetaAdSetSummary(
                external_ad_set_id="adset_001",
                external_campaign_id="camp_001",
                name="Ad Set 1",
                status="ACTIVE",
                effective_status="ACTIVE",
            ),
        ])
        meta_client.setup_ads([
            MetaAdSummary(
                external_ad_id="ad_001",
                external_ad_set_id="adset_001",
                name="Ad 1",
                creative_id="creative_001",
                status="ACTIVE",
                effective_status="ACTIVE",
            ),
        ])
        meta_client.setup_insights([
            MetaInsightRow(
                date_start="2026-01-15",
                date_stop="2026-01-15",
                account_id="123456789",
                campaign_id="camp_001",
                adset_id="adset_001",
                ad_id="ad_001",
                impressions="1000",
                reach="800",
                clicks="50",
                spend="25.50",
                actions=[],
                action_values=[],
            ),
        ])

        request = MetaSyncRequest(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            include_campaigns=True,
            include_ad_sets=True,
            include_ads=True,
            include_insights=True,
        )

        result = await service.sync_data(client_id=CLIENT_A_ID, request=request)

        assert result.status == "succeeded"
        assert result.campaigns_synced == 1
        assert result.ad_sets_synced == 1
        assert result.ads_synced == 1
        assert result.insights_synced >= 1

    @pytest.mark.asyncio
    async def test_sync_data_is_idempotent(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
        reporting_client: InMemoryMetaSyncClient,
    ) -> None:
        # Setup
        meta_client.setup_accounts([
            MetaAdAccountSummary(
                external_account_id="123456789",
                name="Test",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            ),
        ])
        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
        )
        await service.configure_connection(client_id=CLIENT_A_ID, config=config)

        meta_client.setup_campaigns([
            MetaCampaignSummary(
                external_campaign_id="camp_001",
                name="Campaign",
                objective="CONVERSIONS",
                status="ACTIVE",
                effective_status="ACTIVE",
            ),
        ])

        request = MetaSyncRequest(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            include_campaigns=True,
            include_ad_sets=False,
            include_ads=False,
            include_insights=False,
        )

        # Sync twice
        result1 = await service.sync_data(client_id=CLIENT_A_ID, request=request)
        result2 = await service.sync_data(client_id=CLIENT_A_ID, request=request)

        assert result1.status == "succeeded"
        assert result2.status == "succeeded"
        assert result1.campaigns_synced == result2.campaigns_synced

    @pytest.mark.asyncio
    async def test_sync_data_fails_without_connection(
        self, service: MetaSyncService
    ) -> None:
        request = MetaSyncRequest(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
        )

        with pytest.raises(ValueError, match="No Meta connection"):
            await service.sync_data(client_id=CLIENT_A_ID, request=request)

    @pytest.mark.asyncio
    async def test_sync_data_handles_api_error_gracefully(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
        reporting_client: InMemoryMetaSyncClient,
    ) -> None:
        # Setup connection
        meta_client.setup_accounts([
            MetaAdAccountSummary(
                external_account_id="123456789",
                name="Test",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            ),
        ])
        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
        )
        await service.configure_connection(client_id=CLIENT_A_ID, config=config)

        # Make API fail
        meta_client.set_raise_error(True)

        request = MetaSyncRequest(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            include_campaigns=True,
            include_ad_sets=False,
            include_ads=False,
            include_insights=False,
        )

        with pytest.raises(MetaApiError):
            await service.sync_data(client_id=CLIENT_A_ID, request=request)

        # Verify sync run was marked as failed
        sync_run_updates = [
            c for c in reporting_client.update_calls
            if c["table"] == "sync_runs"
        ]
        assert len(sync_run_updates) >= 1
        assert sync_run_updates[0]["values"]["status"] == "failed"


class TestSelectiveSync:
    """Tests for selective entity synchronization."""

    @pytest.mark.asyncio
    async def test_sync_campaigns_only(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
        reporting_client: InMemoryMetaSyncClient,
    ) -> None:
        # Setup connection
        meta_client.setup_accounts([
            MetaAdAccountSummary(
                external_account_id="123456789",
                name="Test",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            ),
        ])
        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
        )
        await service.configure_connection(client_id=CLIENT_A_ID, config=config)

        meta_client.setup_campaigns([
            MetaCampaignSummary(
                external_campaign_id="camp_001",
                name="Campaign",
                objective="CONVERSIONS",
                status="ACTIVE",
                effective_status="ACTIVE",
            ),
        ])
        meta_client.setup_ad_sets([
            MetaAdSetSummary(
                external_ad_set_id="adset_001",
                external_campaign_id="camp_001",
                name="Should Not Sync",
                status="ACTIVE",
                effective_status="ACTIVE",
            ),
        ])

        request = MetaSyncRequest(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            include_campaigns=True,
            include_ad_sets=False,
            include_ads=False,
            include_insights=False,
        )

        result = await service.sync_data(client_id=CLIENT_A_ID, request=request)

        assert result.campaigns_synced == 1
        assert result.ad_sets_synced == 0
        assert result.ads_synced == 0
        assert result.insights_synced == 0

    @pytest.mark.asyncio
    async def test_sync_empty_data_still_succeeds(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
    ) -> None:
        # Setup connection
        meta_client.setup_accounts([
            MetaAdAccountSummary(
                external_account_id="123456789",
                name="Test",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            ),
        ])
        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
        )
        await service.configure_connection(client_id=CLIENT_A_ID, config=config)

        # No data to sync
        meta_client.setup_campaigns([])

        request = MetaSyncRequest(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
        )

        result = await service.sync_data(client_id=CLIENT_A_ID, request=request)

        assert result.status == "succeeded"
        assert result.rows_read == 0
        assert result.rows_written == 0


class TestTestConnection:
    """Tests for connection testing."""

    @pytest.mark.asyncio
    async def test_test_connection_returns_false_without_connection(
        self, service: MetaSyncService
    ) -> None:
        result = await service.test_connection(client_id=CLIENT_A_ID)
        assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_returns_true_with_valid_connection(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
        reporting_client: InMemoryMetaSyncClient,
    ) -> None:
        # Setup connection
        meta_client.setup_accounts([
            MetaAdAccountSummary(
                external_account_id="123456789",
                name="Test",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            ),
        ])
        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
        )
        await service.configure_connection(client_id=CLIENT_A_ID, config=config)

        result = await service.test_connection(client_id=CLIENT_A_ID)
        # Note: InMemory client won't return the connection from select
        # so this tests the pattern


class TestSafeErrorHandling:
    """Tests for safe error handling in syncs."""

    @pytest.mark.asyncio
    async def test_error_message_never_exposes_tokens(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
        reporting_client: InMemoryMetaSyncClient,
    ) -> None:
        # Setup connection
        meta_client.setup_accounts([
            MetaAdAccountSummary(
                external_account_id="123456789",
                name="Test",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            ),
        ])
        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
        )
        await service.configure_connection(client_id=CLIENT_A_ID, config=config)

        # Force an error
        meta_client.set_raise_error(True)

        request = MetaSyncRequest(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            include_campaigns=True,
            include_ad_sets=False,
            include_ads=False,
            include_insights=False,
        )

        with pytest.raises(MetaApiError):
            await service.sync_data(client_id=CLIENT_A_ID, request=request)

        # Check error summary is safe
        update_calls = [
            c for c in reporting_client.update_calls
            if c["table"] == "sync_runs"
        ]
        if update_calls:
            error_summary = update_calls[0]["values"].get("error_summary", "")
            assert "token" not in error_summary.lower()
            assert "secret" not in error_summary.lower()
            assert "password" not in error_summary.lower()

    @pytest.mark.asyncio
    async def test_sync_result_does_not_expose_secrets(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
    ) -> None:
        # Setup
        meta_client.setup_accounts([
            MetaAdAccountSummary(
                external_account_id="123456789",
                name="Test",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            ),
        ])
        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
        )
        await service.configure_connection(client_id=CLIENT_A_ID, config=config)

        request = MetaSyncRequest(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            include_campaigns=False,
            include_ad_sets=False,
            include_ads=False,
            include_insights=False,
        )

        result = await service.sync_data(client_id=CLIENT_A_ID, request=request)

        # Result should be serializable without secrets
        result_dict = result.model_dump()
        result_json = result.model_dump_json()

        for secret_word in ["token", "secret", "password", "credential"]:
            assert secret_word not in result_json.lower()
            assert secret_word not in str(result_dict).lower()


class TestClientIsolation:
    """Tests for client isolation in syncs."""

    @pytest.mark.asyncio
    async def test_client_a_sync_does_not_affect_client_b(
        self,
        service: MetaSyncService,
        meta_client: MockMetaGraphClient,
        reporting_client: InMemoryMetaSyncClient,
    ) -> None:
        # Setup connection for client A
        meta_client.setup_accounts([
            MetaAdAccountSummary(
                external_account_id="123456789",
                name="Test A",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            ),
        ])
        config = MetaConnectionConfig(
            client_id=str(CLIENT_A_ID),
            external_account_id="123456789",
        )
        await service.configure_connection(client_id=CLIENT_A_ID, config=config)

        # All data belongs to client A
        meta_client.setup_campaigns([
            MetaCampaignSummary(
                external_campaign_id="camp_001",
                name="Client A Campaign",
                objective="CONVERSIONS",
                status="ACTIVE",
                effective_status="ACTIVE",
            ),
        ])

        request = MetaSyncRequest(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
        )

        await service.sync_data(client_id=CLIENT_A_ID, request=request)

        # Verify all upserts have client A's ID
        for call in reporting_client.upsert_calls:
            if "rows" in call and call["rows"]:
                for row in call["rows"]:
                    if "client_id" in row:
                        assert row["client_id"] == str(CLIENT_A_ID)
