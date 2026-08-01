from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import KnowledgeSupabaseSettings, ReportingSupabaseSettings, Settings
from app.main import create_app
from app.repositories.client_knowledge import ClientKnowledgeRepository
from app.repositories.client_kpis import ClientKpiRepository
from tests.helpers import (
    SYNTHETIC_CLIENT_A_ID,
    SYNTHETIC_CLIENT_B_ID,
    SYNTHETIC_KNOWLEDGE_A_EXTRA_ID,
    SYNTHETIC_KNOWLEDGE_A_ID,
    SYNTHETIC_KNOWLEDGE_B_EXTRA_ID,
    SYNTHETIC_KNOWLEDGE_B_ID,
    SYNTHETIC_KPI_A_EXTRA_ID,
    SYNTHETIC_KPI_A_ID,
    SYNTHETIC_KPI_B_EXTRA_ID,
    SYNTHETIC_KPI_B_ID,
    InMemoryReportingClient,
)


def _settings() -> Settings:
    return Settings(
        reporting_supabase=ReportingSupabaseSettings(
            url=None,
            service_role_key=None,
            _env_file=None,
        ),
        knowledge_supabase=KnowledgeSupabaseSettings(
            url=None,
            service_role_key=None,
            _env_file=None,
        ),
        _env_file=None,
    )


def _transport(reporting: InMemoryReportingClient) -> ASGITransport:
    application = create_app(
        application_settings=_settings(),
        reporting_supabase_client=reporting,
    )
    return ASGITransport(app=application, raise_app_exceptions=False)


def _row(reporting: InMemoryReportingClient, table: str, row_id: str) -> dict:
    return next(row for row in reporting.rows[table] if row["id"] == row_id)


@pytest.mark.asyncio
async def test_two_synthetic_clients_with_colliding_keys_never_mix_list_results() -> None:
    reporting = InMemoryReportingClient()
    async with AsyncClient(transport=_transport(reporting), base_url="http://test") as client:
        alpha_knowledge = await client.get(f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/knowledge")
        beta_knowledge = await client.get(f"/api/v1/clients/{SYNTHETIC_CLIENT_B_ID}/knowledge")
        alpha_kpis = await client.get(f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/kpis")
        beta_kpis = await client.get(f"/api/v1/clients/{SYNTHETIC_CLIENT_B_ID}/kpis")

    assert alpha_knowledge.status_code == beta_knowledge.status_code == 200
    assert alpha_kpis.status_code == beta_kpis.status_code == 200
    assert [row["id"] for row in alpha_knowledge.json()] == [
        SYNTHETIC_KNOWLEDGE_A_ID,
        SYNTHETIC_KNOWLEDGE_A_EXTRA_ID,
    ]
    assert [row["id"] for row in beta_knowledge.json()] == [
        SYNTHETIC_KNOWLEDGE_B_ID,
        SYNTHETIC_KNOWLEDGE_B_EXTRA_ID,
    ]
    assert [row["id"] for row in alpha_kpis.json()] == [
        SYNTHETIC_KPI_A_ID,
        SYNTHETIC_KPI_A_EXTRA_ID,
    ]
    assert [row["id"] for row in beta_kpis.json()] == [
        SYNTHETIC_KPI_B_ID,
        SYNTHETIC_KPI_B_EXTRA_ID,
    ]

    assert alpha_knowledge.json()[0]["knowledge_key"] == "shared_key"
    assert beta_knowledge.json()[0]["knowledge_key"] == "shared_key"
    assert alpha_kpis.json()[0]["metric_key"] == "shared_metric"
    assert beta_kpis.json()[0]["metric_key"] == "shared_metric"

    child_calls = [
        call
        for call in reporting.select_calls
        if call["table"] in {"client_knowledge", "client_kpis"}
    ]
    assert child_calls
    assert all(set(call["filters"]) == {"client_id"} for call in child_calls)


@pytest.mark.asyncio
async def test_client_list_and_details_return_only_safe_reporting_fields() -> None:
    reporting = InMemoryReportingClient()
    async with AsyncClient(transport=_transport(reporting), base_url="http://test") as client:
        list_response = await client.get("/api/v1/clients")
        detail_response = await client.get(f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}")

    assert list_response.status_code == detail_response.status_code == 200
    assert [row["id"] for row in list_response.json()] == [
        SYNTHETIC_CLIENT_A_ID,
        SYNTHETIC_CLIENT_B_ID,
    ]
    assert detail_response.json() == {
        "id": SYNTHETIC_CLIENT_A_ID,
        "name": "Development Alpha",
        "slug": "development-alpha",
        "status": "active",
        "reporting_timezone": "UTC",
        "default_currency": "USD",
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": "2026-08-01T00:00:00Z",
    }
    serialized = list_response.text + detail_response.text
    for forbidden in ("service_role", "credential", "secret", "source_hash"):
        assert forbidden not in serialized.lower()


@pytest.mark.asyncio
async def test_manual_knowledge_create_and_update_keep_server_owned_scope_and_provenance() -> None:
    reporting = InMemoryReportingClient()
    async with AsyncClient(transport=_transport(reporting), base_url="http://test") as client:
        create_response = await client.post(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/knowledge",
            json={
                "category": "brand",
                "knowledge_key": "tone",
                "value": {"summary": "Synthetic, concise, and factual"},
                "status": "draft",
            },
        )
        created = create_response.json()
        update_response = await client.patch(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/knowledge/{created['id']}",
            json={"status": "approved"},
        )

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert created["client_id"] == SYNTHETIC_CLIENT_A_ID
    assert created["source_type"] == "manual"
    for nullable_provenance in (
        "source_identifier",
        "source_display_name",
        "source_reference",
        "source_version",
        "imported_at",
    ):
        assert created[nullable_provenance] is None
    assert created["version"] == 1
    assert update_response.json()["status"] == "approved"
    assert reporting.insert_calls[0]["row"]["client_id"] == SYNTHETIC_CLIENT_A_ID
    assert reporting.update_calls[0]["filters"] == {
        "client_id": SYNTHETIC_CLIENT_A_ID,
        "id": created["id"],
    }
    assert "client_id" not in reporting.update_calls[0]["values"]


@pytest.mark.asyncio
async def test_kpi_create_and_update_keep_path_client_scope() -> None:
    reporting = InMemoryReportingClient()
    async with AsyncClient(transport=_transport(reporting), base_url="http://test") as client:
        create_response = await client.post(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_B_ID}/kpis",
            json={
                "metric_key": "synthetic_revenue_target",
                "label": "Synthetic revenue target",
                "target_value": "32.5",
                "unit": "currency",
                "direction": "increase",
                "attribution_level": "client",
                "active_from": "2026-02-01",
                "active_to": None,
            },
        )
        created = create_response.json()
        update_response = await client.patch(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_B_ID}/kpis/{created['id']}",
            json={"target_value": "35", "active_to": "2026-12-31"},
        )

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert created["client_id"] == SYNTHETIC_CLIENT_B_ID
    assert update_response.json()["target_value"] == "35"
    assert update_response.json()["active_to"] == "2026-12-31"
    assert reporting.insert_calls[0]["row"]["client_id"] == SYNTHETIC_CLIENT_B_ID
    assert reporting.update_calls[0]["filters"] == {
        "client_id": SYNTHETIC_CLIENT_B_ID,
        "id": created["id"],
    }
    assert "client_id" not in reporting.update_calls[0]["values"]


@pytest.mark.asyncio
async def test_client_a_cannot_get_client_b_knowledge_or_kpi_by_identifier() -> None:
    reporting = InMemoryReportingClient()
    async with AsyncClient(transport=_transport(reporting), base_url="http://test") as client:
        knowledge_response = await client.get(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/knowledge/{SYNTHETIC_KNOWLEDGE_B_ID}"
        )
        kpi_response = await client.get(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/kpis/{SYNTHETIC_KPI_B_ID}"
        )

    assert knowledge_response.status_code == 404
    assert knowledge_response.json()["error"]["code"] == "knowledge_record_not_found"
    assert kpi_response.status_code == 404
    assert kpi_response.json()["error"]["code"] == "kpi_record_not_found"

    knowledge_call = next(
        call for call in reporting.select_calls if call["table"] == "client_knowledge"
    )
    kpi_call = next(call for call in reporting.select_calls if call["table"] == "client_kpis")
    assert knowledge_call["filters"] == {
        "client_id": SYNTHETIC_CLIENT_A_ID,
        "id": SYNTHETIC_KNOWLEDGE_B_ID,
    }
    assert kpi_call["filters"] == {
        "client_id": SYNTHETIC_CLIENT_A_ID,
        "id": SYNTHETIC_KPI_B_ID,
    }


@pytest.mark.asyncio
async def test_cross_client_updates_are_filtered_and_leave_other_client_unchanged() -> None:
    reporting = InMemoryReportingClient()
    beta_knowledge_before = dict(_row(reporting, "client_knowledge", SYNTHETIC_KNOWLEDGE_B_ID))
    beta_kpi_before = dict(_row(reporting, "client_kpis", SYNTHETIC_KPI_B_ID))

    async with AsyncClient(transport=_transport(reporting), base_url="http://test") as client:
        knowledge_response = await client.patch(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/knowledge/{SYNTHETIC_KNOWLEDGE_B_ID}",
            json={"value": {"summary": "cross-client overwrite attempt"}},
        )
        kpi_response = await client.patch(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/kpis/{SYNTHETIC_KPI_B_ID}",
            json={"target_value": "999"},
        )

    assert knowledge_response.status_code == 404
    assert kpi_response.status_code == 404
    assert _row(reporting, "client_knowledge", SYNTHETIC_KNOWLEDGE_B_ID) == (beta_knowledge_before)
    assert _row(reporting, "client_kpis", SYNTHETIC_KPI_B_ID) == beta_kpi_before
    assert reporting.update_calls[0]["filters"] == {
        "client_id": SYNTHETIC_CLIENT_A_ID,
        "id": SYNTHETIC_KNOWLEDGE_B_ID,
    }
    assert not any(call["table"] == "client_kpis" for call in reporting.update_calls)


@pytest.mark.asyncio
async def test_imported_provenance_is_preserved_during_manual_edit() -> None:
    reporting = InMemoryReportingClient()
    before = dict(_row(reporting, "client_knowledge", SYNTHETIC_KNOWLEDGE_A_ID))

    async with AsyncClient(transport=_transport(reporting), base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/knowledge/{SYNTHETIC_KNOWLEDGE_A_ID}",
            json={
                "value": {"summary": "manually reviewed synthetic override"},
                "status": "approved",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    for field in (
        "source_type",
        "source_identifier",
        "source_display_name",
        "source_reference",
        "source_version",
        "imported_at",
        "version",
    ):
        assert payload[field] == before[field]
    assert "source_hash" not in payload
    assert "import_batch_id" not in payload
    assert reporting.update_calls == [
        {
            "table": "client_knowledge",
            "values": {
                "value": {"summary": "manually reviewed synthetic override"},
                "status": "approved",
            },
            "filters": {
                "client_id": SYNTHETIC_CLIENT_A_ID,
                "id": SYNTHETIC_KNOWLEDGE_A_ID,
            },
        }
    ]


@pytest.mark.asyncio
async def test_client_id_body_tampering_is_rejected_without_writes_or_value_leakage() -> None:
    reporting = InMemoryReportingClient()
    secret_like_value = "synthetic-knowledge-value-that-must-not-be-echoed"

    async with AsyncClient(transport=_transport(reporting), base_url="http://test") as client:
        create_response = await client.post(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/knowledge",
            json={
                "client_id": SYNTHETIC_CLIENT_B_ID,
                "category": "profile",
                "knowledge_key": "tamper_attempt",
                "value": {"summary": secret_like_value},
                "status": "draft",
            },
        )
        update_response = await client.patch(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/kpis/{SYNTHETIC_KPI_A_ID}",
            json={"client_id": SYNTHETIC_CLIENT_B_ID, "target_value": "123"},
        )

    assert create_response.status_code == update_response.status_code == 422
    assert create_response.json()["error"]["code"] == "validation_error"
    assert update_response.json()["error"]["code"] == "validation_error"
    assert secret_like_value not in create_response.text
    assert reporting.insert_calls == []
    assert reporting.update_calls == []


@pytest.mark.asyncio
async def test_kpi_patch_validates_interval_merged_with_stored_dates() -> None:
    reporting = InMemoryReportingClient()
    async with AsyncClient(transport=_transport(reporting), base_url="http://test") as client:
        invalid_end = await client.patch(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/kpis/{SYNTHETIC_KPI_A_ID}",
            json={"active_to": "2025-12-31"},
        )
        invalid_start = await client.patch(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/kpis/{SYNTHETIC_KPI_A_ID}",
            json={"active_from": "2027-01-01"},
        )

    for response in (invalid_end, invalid_start):
        assert response.status_code == 422
        assert response.json() == {
            "error": {
                "code": "invalid_kpi_interval",
                "message": "The KPI effective-date interval is invalid",
            }
        }
    assert reporting.update_calls == []


@pytest.mark.asyncio
async def test_unknown_client_and_invalid_knowledge_are_safe_and_do_not_echo_values() -> None:
    reporting = InMemoryReportingClient()
    unknown_client = "00000000-0000-4000-8000-0000000000ff"
    protected_value = "synthetic-protected-knowledge-fragment"

    async with AsyncClient(transport=_transport(reporting), base_url="http://test") as client:
        missing_detail_response = await client.get(f"/api/v1/clients/{unknown_client}")
        missing_response = await client.get(f"/api/v1/clients/{unknown_client}/knowledge")
        invalid_response = await client.post(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/knowledge",
            json={
                "category": " ",
                "knowledge_key": "safe-error-check",
                "value": {"summary": protected_value},
                "status": "draft",
            },
        )

    assert missing_detail_response.status_code == missing_response.status_code == 404
    expected_missing_error = {
        "error": {
            "code": "client_not_found",
            "message": "The reporting client does not exist",
        }
    }
    assert missing_detail_response.json() == expected_missing_error
    assert missing_response.json() == expected_missing_error
    assert invalid_response.status_code == 422
    assert invalid_response.json()["error"]["code"] == "validation_error"
    assert protected_value not in invalid_response.text
    assert reporting.insert_calls == []
    assert not any(
        call["table"] == "client_knowledge" and call["filters"].get("client_id") == unknown_client
        for call in reporting.select_calls
    )


@pytest.mark.asyncio
async def test_owned_repository_methods_require_client_id_and_expose_no_delete() -> None:
    reporting = InMemoryReportingClient()
    knowledge = ClientKnowledgeRepository(reporting)
    kpis = ClientKpiRepository(reporting)

    with pytest.raises(TypeError):
        await knowledge.list_for_client()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        await knowledge.get(  # type: ignore[call-arg]
            knowledge_id=UUID(SYNTHETIC_KNOWLEDGE_A_ID)
        )
    with pytest.raises(TypeError):
        await kpis.list_for_client()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        await kpis.get(kpi_id=UUID(SYNTHETIC_KPI_A_ID))  # type: ignore[call-arg]

    assert not hasattr(knowledge, "delete")
    assert not hasattr(kpis, "delete")
    assert not hasattr(reporting, "delete")

    async with AsyncClient(transport=_transport(reporting), base_url="http://test") as client:
        knowledge_delete = await client.delete(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/knowledge/{SYNTHETIC_KNOWLEDGE_A_ID}"
        )
        kpi_delete = await client.delete(
            f"/api/v1/clients/{SYNTHETIC_CLIENT_A_ID}/kpis/{SYNTHETIC_KPI_A_ID}"
        )

    assert knowledge_delete.status_code == kpi_delete.status_code == 405
