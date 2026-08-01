import json

import httpx
import pytest

from app.core.config import KnowledgeSupabaseSettings, ReportingSupabaseSettings
from app.core.errors import ReportingWriteConflictError
from app.data.supabase import (
    create_knowledge_supabase_client,
    create_reporting_supabase_client,
)
from app.knowledge.errors import (
    ReportingDatabaseUnavailableError,
    SourceDatabaseUnavailableError,
    UpsertConflictError,
)


@pytest.mark.asyncio
async def test_reporting_upsert_uses_postgrest_four_column_conflict_target() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["method"] = request.method
        observed["conflict"] = request.url.params.get("on_conflict")
        observed["rows"] = json.loads(request.content)
        return httpx.Response(200, json=observed["rows"])

    settings = ReportingSupabaseSettings(
        url="https://reporting.invalid", service_role_key="r" * 32, _env_file=None
    )
    client = create_reporting_supabase_client(settings, transport=httpx.MockTransport(handler))
    try:
        result = await client.upsert(
            table="client_knowledge",
            rows=({"client_id": "synthetic"},),
            on_conflict=(
                "client_id",
                "source_type",
                "source_identifier",
                "source_version",
            ),
        )
    finally:
        await client.close()

    assert observed["method"] == "POST"
    assert observed["conflict"] == ("client_id,source_type,source_identifier,source_version")
    assert result == [{"client_id": "synthetic"}]


@pytest.mark.asyncio
async def test_source_client_has_no_mutation_interface_and_collapses_backend_details() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="synthetic-secret-backend-detail")

    settings = KnowledgeSupabaseSettings(
        url="https://knowledge.invalid", service_role_key="k" * 32, _env_file=None
    )
    client = create_knowledge_supabase_client(settings, transport=httpx.MockTransport(handler))
    try:
        for mutation_name in ("insert", "update", "upsert", "delete", "rpc", "_post"):
            assert not hasattr(client, mutation_name)
        with pytest.raises(SourceDatabaseUnavailableError) as captured:
            await client.ping(table="org_clients")
    finally:
        await client.close()

    assert "synthetic-secret-backend-detail" not in str(captured.value)


@pytest.mark.asyncio
async def test_reporting_errors_distinguish_unavailability_and_upsert_conflict() -> None:
    responses = iter(
        (
            httpx.Response(503, text="synthetic-reporting-detail"),
            httpx.Response(409, text="synthetic-conflict-detail"),
        )
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return next(responses)

    settings = ReportingSupabaseSettings(
        url="https://reporting.invalid", service_role_key="r" * 32, _env_file=None
    )
    client = create_reporting_supabase_client(settings, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ReportingDatabaseUnavailableError):
            await client.ping(table="clients")
        with pytest.raises(UpsertConflictError) as captured:
            await client.upsert(
                table="client_knowledge",
                rows=({"client_id": "synthetic"},),
                on_conflict=(
                    "client_id",
                    "source_type",
                    "source_identifier",
                    "source_version",
                ),
            )
    finally:
        await client.close()

    assert "synthetic-conflict-detail" not in str(captured.value)


@pytest.mark.asyncio
async def test_reporting_insert_and_update_use_safe_postgrest_methods_and_filters() -> None:
    observed: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        observed.append(
            {
                "method": request.method,
                "path": request.url.path,
                "client_filter": request.url.params.get("client_id"),
                "id_filter": request.url.params.get("id"),
                "prefer": request.headers.get("Prefer"),
                "body": body,
            }
        )
        if request.method == "POST":
            return httpx.Response(201, json=body)
        return httpx.Response(200, json=[body | {"id": "synthetic-row"}])

    settings = ReportingSupabaseSettings(
        url="https://reporting.invalid", service_role_key="r" * 32, _env_file=None
    )
    client = create_reporting_supabase_client(settings, transport=httpx.MockTransport(handler))
    try:
        inserted = await client.insert(
            table="client_knowledge",
            row={"client_id": "synthetic-client", "source_type": "manual"},
        )
        updated = await client.update(
            table="client_knowledge",
            values={"status": "approved"},
            filters={"client_id": "synthetic-client", "id": "synthetic-row"},
        )
    finally:
        await client.close()

    assert inserted == {"client_id": "synthetic-client", "source_type": "manual"}
    assert updated == [{"status": "approved", "id": "synthetic-row"}]
    assert observed == [
        {
            "method": "POST",
            "path": "/rest/v1/client_knowledge",
            "client_filter": None,
            "id_filter": None,
            "prefer": "return=representation",
            "body": [{"client_id": "synthetic-client", "source_type": "manual"}],
        },
        {
            "method": "PATCH",
            "path": "/rest/v1/client_knowledge",
            "client_filter": "eq.synthetic-client",
            "id_filter": "eq.synthetic-row",
            "prefer": "return=representation",
            "body": {"status": "approved"},
        },
    ]


@pytest.mark.asyncio
async def test_reporting_writes_require_filters_and_collapse_conflict_details() -> None:
    request_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(409, text="synthetic-private-conflict-detail")

    settings = ReportingSupabaseSettings(
        url="https://reporting.invalid", service_role_key="r" * 32, _env_file=None
    )
    client = create_reporting_supabase_client(settings, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ValueError):
            await client.update(
                table="client_kpis",
                values={"target_value": "1"},
                filters={},
            )
        assert request_count == 0

        with pytest.raises(ReportingWriteConflictError) as captured_insert:
            await client.insert(
                table="client_kpis",
                row={"client_id": "synthetic-client"},
            )
        with pytest.raises(ReportingWriteConflictError) as captured_update:
            await client.update(
                table="client_kpis",
                values={"target_value": "1"},
                filters={"client_id": "synthetic-client", "id": "synthetic-kpi"},
            )
    finally:
        await client.close()

    assert request_count == 2
    assert "synthetic-private-conflict-detail" not in str(captured_insert.value)
    assert "synthetic-private-conflict-detail" not in str(captured_update.value)
