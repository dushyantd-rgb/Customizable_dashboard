"""Focused acceptance tests for the environment-token Meta prototype."""

from datetime import date
from uuid import UUID

import pytest

from app.integrations.meta.models import (
    MetaAdAccountSummary,
    MetaAdSetSummary,
    MetaAdSummary,
    MetaCampaignSummary,
    MetaConnectionConfig,
    MetaInsightRow,
    MetaSyncRequest,
)
from app.integrations.meta.repository import MetaRepository
from app.integrations.meta.service import MetaSyncService
from tests.helpers import SYNTHETIC_CLIENT_A_ID, SYNTHETIC_CLIENT_B_ID
from tests.phase3_helpers import Phase3MemoryClient


class _FakeMeta:
    async def validate_token(self) -> bool:
        return True

    async def discover_ad_accounts(self) -> list[MetaAdAccountSummary]:
        return [
            MetaAdAccountSummary(
                external_account_id="account-1",
                name="Synthetic account",
                currency="USD",
                account_timezone="UTC",
                account_status="active",
            )
        ]

    async def get_campaigns(self, *, external_account_id: str) -> list[MetaCampaignSummary]:
        assert external_account_id == "account-1"
        return [MetaCampaignSummary(external_campaign_id="campaign-1", name="Campaign")]

    async def get_ad_sets(self, *, external_account_id: str) -> list[MetaAdSetSummary]:
        assert external_account_id == "account-1"
        return [
            MetaAdSetSummary(
                external_ad_set_id="adset-1",
                external_campaign_id="campaign-1",
                name="Ad set",
            )
        ]

    async def get_ads(self, *, external_account_id: str) -> list[MetaAdSummary]:
        assert external_account_id == "account-1"
        return [MetaAdSummary(external_ad_id="ad-1", external_ad_set_id="adset-1", name="Ad")]

    async def get_insights(
        self,
        *,
        external_account_id: str,
        date_from: str,
        date_to: str,
        level: str,
    ) -> list[MetaInsightRow]:
        assert external_account_id == "account-1"
        identity = {
            "campaign": {"campaign_id": "campaign-1"},
            "adset": {"adset_id": "adset-1"},
            "ad": {"ad_id": "ad-1"},
        }[level]
        return [
            MetaInsightRow(
                date_start=date_from,
                date_stop=date_to,
                account_id="account-1",
                spend="12.50",
                impressions="100",
                clicks="8",
                actions=[{"action_type": "lead", "value": "2"}],
                **identity,
            )
        ]


class _FakeMetaWithHistoricalAd(_FakeMeta):
    async def get_insights(
        self,
        *,
        external_account_id: str,
        date_from: str,
        date_to: str,
        level: str,
    ) -> list[MetaInsightRow]:
        rows = await super().get_insights(
            external_account_id=external_account_id,
            date_from=date_from,
            date_to=date_to,
            level=level,
        )
        if level == "ad":
            rows.append(
                MetaInsightRow(
                    date_start=date_from,
                    date_stop=date_to,
                    account_id="account-1",
                    campaign_id="campaign-1",
                    adset_id="adset-1",
                    ad_id="historical-ad",
                    impressions="25",
                )
            )
        return rows


@pytest.mark.asyncio
async def test_meta_config_and_repeated_sync_are_client_scoped_and_idempotent() -> None:
    store = Phase3MemoryClient()
    repository = MetaRepository(store)
    service = MetaSyncService(meta_client=_FakeMeta(), repository=repository)  # type: ignore[arg-type]
    client_a = UUID(SYNTHETIC_CLIENT_A_ID)
    client_b = UUID(SYNTHETIC_CLIENT_B_ID)

    configured = await service.configure_connection(
        client_id=client_a,
        config=MetaConnectionConfig(external_account_id="account-1"),
    )
    assert configured["external_account_id"] == "account-1"
    assert await repository.get_connection(client_id=client_b) is None
    assert await repository.get_meta_account(client_id=client_b) is None

    request = MetaSyncRequest(date_from=date(2026, 7, 1), date_to=date(2026, 7, 1))
    first = await service.sync_data(client_id=client_a, request=request)
    second = await service.sync_data(client_id=client_a, request=request)

    assert first.status == second.status == "succeeded"
    assert len(store.rows["meta_campaigns"]) == 1
    assert len(store.rows["meta_ad_sets"]) == 1
    assert len(store.rows["meta_ads"]) == 1
    assert len(store.rows["meta_daily_insights"]) == 3
    assert [run["status"] for run in store.rows["sync_runs"]] == [
        "succeeded",
        "succeeded",
    ]
    latest_runs = await repository.get_sync_runs(client_id=client_a, limit=1)
    assert latest_runs[0]["id"] == second.sync_run_id
    assert all(row["client_id"] == SYNTHETIC_CLIENT_A_ID for row in store.rows["sync_runs"])
    assert all(
        call["filters"].get("client_id") in {None, SYNTHETIC_CLIENT_A_ID, SYNTHETIC_CLIENT_B_ID}
        for call in store.select_calls
    )


@pytest.mark.asyncio
async def test_meta_account_configuration_is_stable_on_repeat() -> None:
    store = Phase3MemoryClient()
    service = MetaSyncService(
        meta_client=_FakeMeta(),  # type: ignore[arg-type]
        repository=MetaRepository(store),
    )
    client_id = UUID(SYNTHETIC_CLIENT_A_ID)
    config = MetaConnectionConfig(external_account_id="account-1")
    await service.configure_connection(client_id=client_id, config=config)
    await service.configure_connection(client_id=client_id, config=config)
    assert len(store.rows["integration_connections"]) == 1
    assert len(store.rows["meta_accounts"]) == 1


@pytest.mark.asyncio
async def test_meta_sync_preserves_insights_for_deleted_historical_ads() -> None:
    store = Phase3MemoryClient()
    service = MetaSyncService(
        meta_client=_FakeMetaWithHistoricalAd(),  # type: ignore[arg-type]
        repository=MetaRepository(store),
    )
    client_id = UUID(SYNTHETIC_CLIENT_A_ID)
    await service.configure_connection(
        client_id=client_id,
        config=MetaConnectionConfig(external_account_id="account-1"),
    )

    result = await service.sync_data(
        client_id=client_id,
        request=MetaSyncRequest(date_from=date(2026, 7, 1), date_to=date(2026, 7, 1)),
    )

    assert result.status == "succeeded"
    assert result.warning_count == 1
    assert result.ads_synced == 2
    assert store.rows["sync_runs"][0]["rows_rejected"] == 1
    historical_ad = next(
        row for row in store.rows["meta_ads"] if row["external_ad_id"] == "historical-ad"
    )
    assert historical_ad["name"] is None
    assert any(
        row["entity_level"] == "ad"
        and row["external_entity_id"] == "historical-ad"
        and row["entity_id"] == historical_ad["id"]
        for row in store.rows["meta_daily_insights"]
    )
