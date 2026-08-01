import json

import httpx
import pytest

from app.core.config import KnowledgeSupabaseSettings, ReportingSupabaseSettings
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
