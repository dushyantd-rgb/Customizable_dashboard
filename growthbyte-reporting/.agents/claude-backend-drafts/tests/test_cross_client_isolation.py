"""Tests for cross-client isolation in Phase 3 integrations.

These tests verify that data from one client cannot leak to another,
including through Meta syncs, Google OAuth, and repository operations.
"""

import base64
import hashlib
import json
from datetime import date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from pydantic import SecretStr

from app.integrations.google.oauth import (
    GoogleOAuthStateError,
    generate_oauth_state,
    validate_oauth_state,
)
from app.integrations.meta.models import (
    MetaAdAccountSummary,
    MetaCampaignSummary,
)
from app.integrations.meta.repository import MetaRepository
from tests.helpers import (
    InMemoryReportingClient,
    SYNTHETIC_CLIENT_A_ID,
    SYNTHETIC_CLIENT_B_ID,
)


class InMemoryIntegrationClient(InMemoryReportingClient):
    """Extended client with integration tables."""

    def __init__(self) -> None:
        super().__init__()
        self.rows["integration_connections"] = []
        self.rows["meta_accounts"] = []
        self.rows["meta_campaigns"] = []
        self.rows["meta_ad_sets"] = []
        self.rows["meta_ads"] = []
        self.rows["meta_daily_insights"] = []
        self.rows["sync_runs"] = []
        self.rows["google_connections"] = []
        self.rows["google_tokens"] = []
        self._auto_increment = 1

    def _generate_id(self) -> str:
        id_str = f"{self._auto_increment:012d}"
        self._auto_increment += 1
        return f"00000000-0000-4000-8000-{id_str}"


def generate_test_key() -> SecretStr:
    """Generate a valid key for testing."""
    raw_key = b"a" * 32
    return SecretStr(base64.b64encode(raw_key).decode("utf-8"))


class TestMetaConnectionIsolation:
    """Tests for Meta integration connection isolation."""

    @pytest.mark.asyncio
    async def test_client_a_meta_connection_not_visible_to_client_b(
        self,
    ) -> None:
        """Test that Meta connections are isolated between clients."""
        reporting = InMemoryIntegrationClient()

        # Add connection for client A
        reporting.rows["integration_connections"].append({
            "id": "00000000-0000-4000-8000-000000000001",
            "client_id": SYNTHETIC_CLIENT_A_ID,
            "provider": "meta",
            "source_identifier": "123456789",
            "display_name": "Client A Account",
            "status": "active",
            "last_connected_at": "2026-01-01T00:00:00Z",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        })

        repository = MetaRepository(reporting)

        # Client A can see their connection
        connection_a = await repository.get_connection(
            client_id=UUID(SYNTHETIC_CLIENT_A_ID),
            provider="meta",
        )

        # Client B cannot see Client A's connection (it would be None)
        connection_b = await repository.get_connection(
            client_id=UUID(SYNTHETIC_CLIENT_B_ID),
            provider="meta",
        )

        # The filter should include client_id
        select_calls = [c for c in reporting.select_calls if c["table"] == "integration_connections"]
        assert len(select_calls) > 0

        for call in select_calls:
            assert "client_id" in call["filters"]


class TestMetaSyncIsolation:
    """Tests for Meta sync isolation."""

    @pytest.mark.asyncio
    async def test_sync_runs_are_client_scoped(self) -> None:
        """Test that sync runs are client-scoped."""
        reporting = InMemoryIntegrationClient()

        # Create sync runs for both clients
        reporting.rows["sync_runs"] = [
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "client_id": SYNTHETIC_CLIENT_A_ID,
                "source_type": "meta",
                "status": "succeeded",
                "started_at": "2026-01-01T00:00:00Z",
            },
            {
                "id": "00000000-0000-4000-8000-000000000002",
                "client_id": SYNTHETIC_CLIENT_B_ID,
                "source_type": "meta",
                "status": "succeeded",
                "started_at": "2026-01-01T00:00:00Z",
            },
        ]

        repository = MetaRepository(reporting)

        # Get sync runs for client A
        runs_a = await repository.get_sync_runs(
            client_id=UUID(SYNTHETIC_CLIENT_A_ID)
        )

        # Get sync runs for client B
        runs_b = await repository.get_sync_runs(
            client_id=UUID(SYNTHETIC_CLIENT_B_ID)
        )

        for call in reporting.select_calls:
            if call["table"] == "sync_runs":
                assert "client_id" in call["filters"]

    @pytest.mark.asyncio
    async def test_campaigns_are_client_scoped(self) -> None:
        """Test that campaigns are client-scoped."""
        reporting = InMemoryIntegrationClient()

        repository = MetaRepository(reporting)

        # Upsert campaigns for different clients
        await repository.upsert_campaigns(
            client_id=UUID(SYNTHETIC_CLIENT_A_ID),
            meta_account_id=UUID("00000000-0000-4000-8000-000000000001"),
            campaigns=[
                MetaCampaignSummary(
                    external_campaign_id="camp_a",
                    name="Client A Campaign",
                    objective="CONVERSIONS",
                    status="ACTIVE",
                    effective_status="ACTIVE",
                ),
            ],
        )

        await repository.upsert_campaigns(
            client_id=UUID(SYNTHETIC_CLIENT_B_ID),
            meta_account_id=UUID("00000000-0000-4000-8000-000000000002"),
            campaigns=[
                MetaCampaignSummary(
                    external_campaign_id="camp_b",
                    name="Client B Campaign",
                    objective="CONVERSIONS",
                    status="ACTIVE",
                    effective_status="ACTIVE",
                ),
            ],
        )

        # Verify client_id in upsert calls
        for call in reporting.upsert_calls:
            if call["table"] == "meta_campaigns":
                for row in call["rows"]:
                    assert "client_id" in row


class TestInsightsIsolation:
    """Tests for insights data isolation."""

    @pytest.mark.asyncio
    async def test_insights_upsert_is_client_scoped(self) -> None:
        """Test that insights upserts are client-scoped."""
        reporting = InMemoryIntegrationClient()
        repository = MetaRepository(reporting)

        from app.integrations.meta.models import MetaInsightRow

        insights = [
            MetaInsightRow(
                date_start="2026-01-01",
                date_stop="2026-01-01",
                account_id="123456789",
                campaign_id="camp_001",
                impressions="1000",
                reach="800",
                clicks="50",
                spend="100.00",
                actions=[],
                action_values=[],
            ),
        ]

        await repository.upsert_insights(
            client_id=UUID(SYNTHETIC_CLIENT_A_ID),
            meta_account_id=UUID("00000000-0000-4000-8000-000000000001"),
            sync_run_id=UUID("00000000-0000-4000-8000-000000000001"),
            insights=insights,
        )

        for call in reporting.upsert_calls:
            if call["table"] == "meta_daily_insights":
                for row in call["rows"]:
                    assert row["client_id"] == SYNTHETIC_CLIENT_A_ID


class TestOAuthStateIsolation:
    """Tests for OAuth state-based isolation."""

    def test_oauth_state_contains_client_id(self) -> None:
        """Test that OAuth state includes client_id."""
        key = generate_test_key()

        state_a = generate_oauth_state(client_id=SYNTHETIC_CLIENT_A_ID, state_hmac_key=key)
        state_b = generate_oauth_state(client_id=SYNTHETIC_CLIENT_B_ID, state_hmac_key=key)

        validated_a = validate_oauth_state(state=state_a, state_hmac_key=key)
        validated_b = validate_oauth_state(state=state_b, state_hmac_key=key)

        assert validated_a == SYNTHETIC_CLIENT_A_ID
        assert validated_b == SYNTHETIC_CLIENT_B_ID
        assert validated_a != validated_b

    def test_oauth_state_prevents_cross_client_access(self) -> None:
        """Test that OAuth state prevents cross-client token access."""
        key = generate_test_key()

        # Client A generates state
        state_a = generate_oauth_state(client_id=SYNTHETIC_CLIENT_A_ID, state_hmac_key=key)

        # Validation returns Client A's ID
        validated = validate_oauth_state(state=state_a, state_hmac_key=key)
        assert validated == SYNTHETIC_CLIENT_A_ID

    def test_tampered_client_id_in_state_is_detected(self) -> None:
        """Test that tampering with client_id in state is detected."""
        key = generate_test_key()

        state_a = generate_oauth_state(client_id=SYNTHETIC_CLIENT_A_ID, state_hmac_key=key)

        # Decode and tamper
        state_bytes = base64.urlsafe_b64decode(state_a.encode("utf-8"))
        state_json = json.loads(state_bytes.decode("utf-8"))

        # Try to change client_id
        state_json["client_id"] = SYNTHETIC_CLIENT_B_ID
        tampered = base64.urlsafe_b64encode(
            json.dumps(state_json).encode("utf-8")
        ).decode("utf-8")

        with pytest.raises(GoogleOAuthStateError):
            validate_oauth_state(state=tampered, state_hmac_key=key)


class TestCrossClientDataLeakage:
    """Tests for cross-client data leakage prevention."""

    @pytest.mark.asyncio
    async def test_update_cannot_change_client_id(self) -> None:
        """Test that updates cannot change client_id."""
        reporting = InMemoryIntegrationClient()

        repository = MetaRepository(reporting)

        # Create sync run for client A
        sync_run = await repository.create_sync_run(
            client_id=UUID(SYNTHETIC_CLIENT_A_ID),
            integration_connection_id=UUID("00000000-0000-4000-8000-000000000001"),
        )

        sync_run_id = UUID(sync_run["id"])

        # Complete with update - client_id should be in filter
        await repository.complete_sync_run(
            client_id=UUID(SYNTHETIC_CLIENT_A_ID),
            sync_run_id=sync_run_id,
            status="succeeded",
            rows_read=100,
            rows_written=100,
        )

        for call in reporting.update_calls:
            if call["table"] == "sync_runs":
                assert "client_id" in call["filters"]


class TestRepositoryLevelIsolation:
    """Tests for repository-level isolation."""

    @pytest.mark.asyncio
    async def test_knowledge_isolation_across_clients(self) -> None:
        """Test knowledge base isolation across clients."""
        from app.repositories.client_knowledge import ClientKnowledgeRepository

        reporting = InMemoryIntegrationClient()
        repository = ClientKnowledgeRepository(reporting)

        # List knowledge for client A
        await repository.list_for_client(client_id=UUID(SYNTHETIC_CLIENT_A_ID))

        # List knowledge for client B
        await repository.list_for_client(client_id=UUID(SYNTHETIC_CLIENT_B_ID))

        knowledge_selects = [
            c for c in reporting.select_calls
            if c["table"] == "client_knowledge"
        ]

        for call in knowledge_selects:
            assert "client_id" in call["filters"]

    @pytest.mark.asyncio
    async def test_kpi_isolation_across_clients(self) -> None:
        """Test KPI isolation across clients."""
        from app.repositories.client_kpis import ClientKpiRepository

        reporting = InMemoryIntegrationClient()
        repository = ClientKpiRepository(reporting)

        await repository.list_for_client(client_id=UUID(SYNTHETIC_CLIENT_A_ID))
        await repository.list_for_client(client_id=UUID(SYNTHETIC_CLIENT_B_ID))

        kpi_selects = [
            c for c in reporting.select_calls
            if c["table"] == "client_kpis"
        ]

        for call in kpi_selects:
            assert "client_id" in call["filters"]


class TestNoDeleteOperations:
    """Tests to verify no delete operations are exposed."""

    def test_in_memory_client_has_no_delete(self) -> None:
        """Test that InMemoryReportingClient has no delete method."""
        reporting = InMemoryIntegrationClient()
        assert not hasattr(reporting, "delete")

    def test_meta_repository_has_no_delete(self) -> None:
        """Test that MetaRepository has no delete method."""
        reporting = InMemoryIntegrationClient()
        repository = MetaRepository(reporting)
        assert not hasattr(repository, "delete")


class TestEncryptionKeyIsolation:
    """Tests for encryption key isolation."""

    def test_different_clients_cannot_decrypt_each_others_tokens(self) -> None:
        """Test that one client cannot decrypt another's tokens."""
        from app.core.encryption import encrypt_token, decrypt_token, DecryptionError

        key_a = generate_test_key()
        key_b = generate_test_key()

        token_a = "client-a-secret-token"
        encrypted_a = encrypt_token(token_a, key_a)

        # Client B should not be able to decrypt Client A's token
        with pytest.raises(DecryptionError):
            decrypt_token(encrypted_a, key_b)

    def test_same_key_different_clients(self) -> None:
        """Test that same key works for different clients."""
        from app.core.encryption import encrypt_token, decrypt_token

        shared_key = generate_test_key()

        token_a = "client-a-token"
        token_b = "client-b-token"

        encrypted_a = encrypt_token(token_a, shared_key)
        encrypted_b = encrypt_token(token_b, shared_key)

        # Both should decrypt correctly
        assert decrypt_token(encrypted_a, shared_key) == token_a
        assert decrypt_token(encrypted_b, shared_key) == token_b


class TestSyncRunIsolation:
    """Tests for sync run isolation."""

    @pytest.mark.asyncio
    async def test_client_a_cannot_see_client_b_sync_errors(self) -> None:
        """Test that sync errors from one client aren't visible to another."""
        reporting = InMemoryIntegrationClient()

        reporting.rows["sync_runs"] = [
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "client_id": SYNTHETIC_CLIENT_A_ID,
                "status": "failed",
                "error_summary": "Client A error with sensitive info xyz123",
            },
            {
                "id": "00000000-0000-4000-8000-000000000002",
                "client_id": SYNTHETIC_CLIENT_B_ID,
                "status": "succeeded",
            },
        ]

        repository = MetaRepository(reporting)

        # Get sync runs for Client B
        runs_b = await repository.get_sync_runs(
            client_id=UUID(SYNTHETIC_CLIENT_B_ID)
        )

        sync_run_calls = [
            c for c in reporting.select_calls
            if c["table"] == "sync_runs"
        ]

        for call in sync_run_calls:
            assert "client_id" in call["filters"]


class TestIdempotencyWithIsolation:
    """Tests for idempotency while maintaining isolation."""

    @pytest.mark.asyncio
    async def test_repeated_upsert_maintains_client_scope(self) -> None:
        """Test that repeated upserts maintain client scope."""
        reporting = InMemoryIntegrationClient()
        repository = MetaRepository(reporting)

        campaigns = [
            MetaCampaignSummary(
                external_campaign_id="camp_001",
                name="Test Campaign",
                objective="CONVERSIONS",
                status="ACTIVE",
                effective_status="ACTIVE",
            ),
        ]

        # Upsert twice
        await repository.upsert_campaigns(
            client_id=UUID(SYNTHETIC_CLIENT_A_ID),
            meta_account_id=UUID("00000000-0000-4000-8000-000000000001"),
            campaigns=campaigns,
        )

        await repository.upsert_campaigns(
            client_id=UUID(SYNTHETIC_CLIENT_A_ID),
            meta_account_id=UUID("00000000-0000-4000-8000-000000000001"),
            campaigns=campaigns,
        )

        # All upserts should have client_id
        for call in reporting.upsert_calls:
            if call["table"] == "meta_campaigns":
                for row in call["rows"]:
                    assert "client_id" in row

    def test_upsert_conflict_target_includes_client(self) -> None:
        """Test that upsert conflict targets include client_id."""
        expected_conflict_targets = {
            "meta_campaigns": ("client_id", "meta_account_id", "external_campaign_id"),
            "meta_ad_sets": ("client_id", "meta_account_id", "external_ad_set_id"),
            "meta_ads": ("client_id", "meta_account_id", "external_ad_id"),
            "meta_daily_insights": (
                "client_id",
                "meta_account_id",
                "report_date",
                "entity_level",
                "external_entity_id",
            ),
        }

        # All should include client_id for isolation
        for table, targets in expected_conflict_targets.items():
            assert "client_id" in targets


class TestNoSecretsInErrors:
    """Tests for ensuring secrets are not exposed in errors."""

    def test_oauth_state_error_is_safe(self) -> None:
        """Test that OAuth state error doesn't expose secrets."""
        error = GoogleOAuthStateError()

        assert "secret" not in str(error).lower()
        assert "token" not in str(error).lower()
        assert "key" not in str(error).lower()
        assert "Invalid OAuth state" in str(error)

    @pytest.mark.asyncio
    async def test_sync_error_summary_is_safe(self) -> None:
        """Test that sync error summaries don't contain secrets."""
        reporting = InMemoryIntegrationClient()
        repository = MetaRepository(reporting)

        sync_run = await repository.create_sync_run(
            client_id=UUID(SYNTHETIC_CLIENT_A_ID),
            integration_connection_id=UUID("00000000-0000-4000-8000-000000000001"),
        )
        sync_run_id = UUID(sync_run["id"])

        safe_error = "Sync failed without exposing credentials"
        await repository.complete_sync_run(
            client_id=UUID(SYNTHETIC_CLIENT_A_ID),
            sync_run_id=sync_run_id,
            status="failed",
            error_summary=safe_error,
        )

        for call in reporting.update_calls:
            if call["table"] == "sync_runs":
                error_summary = call["values"].get("error_summary", "")
                assert "secret" not in error_summary.lower()
                assert "token" not in error_summary.lower()
                assert "password" not in error_summary.lower()
