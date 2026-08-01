from typing import Any

from fastapi import APIRouter, Request

from app.core.config import Settings
from app.models.health import (
    DependencyReadiness,
    DependencyState,
    HealthResponse,
    ReadinessResponse,
)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    return HealthResponse(status="ok", version=settings.app_version)


@router.get("/ready", response_model=ReadinessResponse)
async def ready(request: Request) -> ReadinessResponse:
    settings: Settings = request.app.state.settings
    reporting_state = await _dependency_state(
        configured=settings.reporting_supabase.configured,
        client=request.app.state.reporting_supabase_client,
        table="clients",
    )
    knowledge_state = await _dependency_state(
        configured=settings.knowledge_supabase.configured,
        client=request.app.state.knowledge_supabase_client,
        table="org_clients",
    )
    dependencies = DependencyReadiness(
        reporting_supabase=reporting_state,
        knowledge_supabase=knowledge_state,
    )
    overall_state = _overall_state(reporting_state, knowledge_state)
    return ReadinessResponse(
        status=overall_state,
        version=settings.app_version,
        dependencies=dependencies,
    )


async def _dependency_state(*, configured: bool, client: Any | None, table: str) -> DependencyState:
    if not configured:
        return "not_configured"
    if client is None:
        return "configured"
    try:
        await client.ping(table=table)
    except Exception:  # The response deliberately collapses all backend details.
        return "unavailable"
    return "reachable"


def _overall_state(*states: DependencyState) -> DependencyState:
    if all(state == "reachable" for state in states):
        return "reachable"
    if "unavailable" in states:
        return "unavailable"
    if "not_configured" in states:
        return "not_configured"
    return "configured"
