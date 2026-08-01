import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import (
    KnowledgeSupabaseSettings,
    ReportingSupabaseSettings,
    Settings,
)
from app.main import create_app
from tests.helpers import FakeKnowledgeClient, FakeReportingClient


def _settings(*, configured: bool) -> Settings:
    reporting = ReportingSupabaseSettings(_env_file=None)
    knowledge = KnowledgeSupabaseSettings(_env_file=None)
    if configured:
        reporting = ReportingSupabaseSettings(
            url="https://reporting.invalid", service_role_key="r" * 32, _env_file=None
        )
        knowledge = KnowledgeSupabaseSettings(
            url="https://knowledge.invalid", service_role_key="k" * 32, _env_file=None
        )
    return Settings(
        reporting_supabase=reporting,
        knowledge_supabase=knowledge,
        _env_file=None,
    )


@pytest.mark.asyncio
async def test_health_and_unconfigured_readiness_are_secret_safe() -> None:
    app = create_app(application_settings=_settings(configured=False))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health_response = await client.get("/health")
        ready_response = await client.get("/ready")
        versioned_response = await client.get("/api/v1/health")

    assert health_response.json() == {"service": "api", "status": "ok", "version": "0.1.0"}
    assert versioned_response.json() == health_response.json()
    assert ready_response.json()["dependencies"] == {
        "reporting_supabase": "not_configured",
        "knowledge_supabase": "not_configured",
    }
    assert ready_response.json()["status"] == "not_configured"


@pytest.mark.asyncio
async def test_readiness_reports_reachable_and_unavailable_without_details() -> None:
    app = create_app(
        application_settings=_settings(configured=True),
        reporting_supabase_client=FakeReportingClient(reachable=True),
        knowledge_supabase_client=FakeKnowledgeClient(reachable=False),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")

    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["dependencies"] == {
        "reporting_supabase": "reachable",
        "knowledge_supabase": "unavailable",
    }
    serialized = response.text
    for forbidden in ("reporting.invalid", "knowledge.invalid", "synthetic backend failure"):
        assert forbidden not in serialized
