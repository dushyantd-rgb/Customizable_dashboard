from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from app.core.config import GLMSettings, MetaSettings, Settings, SuperKSettings
from app.main import create_app
from app.superk.dependencies import get_superk_service
from app.superk.repository import SuperKRepository
from app.superk.service import SuperKReportingService

CLIENT_ID = UUID("00000000-0000-4000-8000-0000000000a1")


class SuperKMemoryClient:
    """Small PostgREST-shaped store used to exercise the full route/service boundary."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {
            "clients": [
                {
                    "id": str(CLIENT_ID),
                    "name": "Synthetic SuperK",
                    "slug": "superk",
                    "reporting_timezone": "Asia/Kolkata",
                    "default_currency": "INR",
                    "status": "active",
                }
            ],
            "client_knowledge": [
                {
                    "id": "00000000-0000-4000-8000-0000000000b1",
                    "client_id": str(CLIENT_ID),
                    "category": "brand",
                    "knowledge_key": "positioning",
                    "value": {"summary": "Synthetic approved franchise context"},
                    "status": "approved",
                    "source_type": "manual",
                    "source_identifier": None,
                    "source_version": None,
                    "source_hash": "synthetic-knowledge-hash",
                    "version": 1,
                    "approved_at": "2026-01-01T00:00:00Z",
                }
            ],
            "client_kpis": [
                {
                    "id": "00000000-0000-4000-8000-0000000000c1",
                    "client_id": str(CLIENT_ID),
                    "metric_key": "cost_per_lead",
                    "label": "Synthetic CPL target",
                    "target_value": "500",
                    "unit": "currency",
                    "direction": "decrease",
                    "attribution_level": "client_month",
                    "active_from": "2026-01-01",
                    "active_to": None,
                }
            ],
        }

    @staticmethod
    def _matches(row: Mapping[str, Any], filters: Mapping[str, str]) -> bool:
        return all(str(row.get(key)) == str(value) for key, value in filters.items())

    async def select(
        self,
        *,
        table: str,
        columns: Sequence[str],
        filters: Mapping[str, str],
        limit: int,
    ) -> list[dict[str, Any]]:
        matching = [row for row in self.rows.get(table, []) if self._matches(row, filters)]
        return [{column: row.get(column) for column in columns} for row in matching[:limit]]

    async def insert(self, *, table: str, row: Mapping[str, Any]) -> dict[str, Any]:
        inserted = dict(row)
        inserted.setdefault("id", str(uuid4()))
        inserted.setdefault("created_at", "2026-08-01T00:00:00Z")
        self.rows.setdefault(table, []).append(inserted)
        return dict(inserted)

    async def update(
        self,
        *,
        table: str,
        values: Mapping[str, Any],
        filters: Mapping[str, str],
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for row in self.rows.get(table, []):
            if self._matches(row, filters):
                row.update(values)
                updated.append(dict(row))
        return updated

    async def upsert(
        self,
        *,
        table: str,
        rows: Sequence[Mapping[str, Any]],
        on_conflict: Sequence[str],
    ) -> list[dict[str, Any]]:
        stored: list[dict[str, Any]] = []
        for candidate in rows:
            candidate_row = dict(candidate)
            existing = next(
                (
                    row
                    for row in self.rows.get(table, [])
                    if all(str(row.get(key)) == str(candidate_row.get(key)) for key in on_conflict)
                ),
                None,
            )
            if existing is None:
                candidate_row.setdefault("id", str(uuid4()))
                self.rows.setdefault(table, []).append(candidate_row)
                stored.append(dict(candidate_row))
            else:
                existing.update(candidate_row)
                stored.append(dict(existing))
        return stored

    async def ping(self, *, table: str) -> None:
        return None

    async def close(self) -> None:
        return None


def _settings() -> Settings:
    project_root = Path(__file__).resolve().parents[3]
    return Settings(
        app_env="test",
        superk=SuperKSettings(
            client_id=CLIENT_ID,
            franchise_meta_account_id="123456789",
            gsc_site_url="sc-domain:superk.invalid",
            lead_json_path=project_root / "superk_purchase_qcom.json",
        ),
        meta=MetaSettings(
            access_token=None,
            silpa_access_token=None,
            superk_access_token=None,
            superk_ads_access_token=None,
            franchise_ads_access_token=None,
            superk_page_access_token=None,
            franchise_page_access_token=None,
        ),
        glm=GLMSettings(base_url=None, auth_token=None),
        token_encryption_key=None,
    )


def _service(client: SuperKMemoryClient, settings: Settings) -> SuperKReportingService:
    return SuperKReportingService(
        repository=SuperKRepository(client),
        settings=settings,
        clock=lambda: datetime(2026, 8, 1, 8, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_status_is_client_locked_and_rejects_the_qcom_purchase_export() -> None:
    store = SuperKMemoryClient()
    settings = _settings()
    app = create_app(application_settings=settings, reporting_supabase_client=store)
    app.dependency_overrides[get_superk_service] = lambda: _service(store, settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/clients/{CLIENT_ID}/superk-franchise-report/status")
        other_client = await client.get(
            "/api/v1/clients/00000000-0000-4000-8000-0000000000a2/superk-franchise-report/status"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["report_month"] == "2026-07"
    assert payload["vertical"] == "b2b_franchise"
    assert payload["sources"]["lead_json"] == {
        "status": "rejected",
        "detail": "source_vertical_mismatch",
        "synced_at": None,
    }
    assert other_client.status_code == 404


@pytest.mark.asyncio
async def test_empty_generate_request_degrades_sources_and_reuses_snapshot() -> None:
    store = SuperKMemoryClient()
    settings = _settings()
    service = _service(store, settings)
    app = create_app(application_settings=settings, reporting_supabase_client=store)
    app.dependency_overrides[get_superk_service] = lambda: service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        first = await client.post(f"/api/v1/clients/{CLIENT_ID}/superk-franchise-report/generate")
        second = await client.post(f"/api/v1/clients/{CLIENT_ID}/superk-franchise-report/generate")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["snapshot_reused"] is False
    assert second_payload["snapshot_reused"] is True
    assert second_payload["snapshot_id"] == first_payload["snapshot_id"]
    assert first_payload["quality_status"] == "unavailable"
    assert first_payload["report_status"] == "draft"
    assert first_payload["sources"]["meta"]["status"] == "not_configured"
    assert first_payload["sources"]["gsc"]["status"] == "not_configured"
    assert first_payload["sources"]["lead_json"]["status"] == "rejected"
    assert len(first_payload["monthly_snapshot"]["metrics"]) == 20
    assert all(isinstance(section, list) for section in first_payload["sections"].values())
    assert len(store.rows["monthly_report_snapshots"]) == 1
    assert len(store.rows["metric_snapshots"]) == 20
    assert len(store.rows["reports"]) == 1
