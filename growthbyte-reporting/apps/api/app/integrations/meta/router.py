"""Client-scoped Meta Ads integration routes."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.v1.dependencies import ReportingClientDependency
from app.core.errors import ClientNotFoundError
from app.integrations.meta.dependencies import (
    MetaRepositoryDependency,
    MetaSyncServiceDependency,
)
from app.integrations.meta.models import (
    MetaAccountDiscoveryResponse,
    MetaConnectionConfig,
    MetaSyncRequest,
    MetaSyncResult,
)

router = APIRouter(prefix="/integrations/meta/clients/{client_id}", tags=["meta"])


async def _require_client(client_id: UUID, client: ReportingClientDependency) -> None:
    from app.repositories.clients import ReportingClientRepository

    if not await ReportingClientRepository(client).exists(client_id=client_id):
        raise ClientNotFoundError


@router.get("/accounts", response_model=MetaAccountDiscoveryResponse)
async def discover_meta_accounts(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    service: MetaSyncServiceDependency,
) -> MetaAccountDiscoveryResponse:
    await _require_client(client_id, reporting_client)
    return MetaAccountDiscoveryResponse(
        accounts=await service.discover_accounts(client_id=client_id)
    )


@router.post("/config")
async def configure_meta_connection(
    client_id: UUID,
    config: MetaConnectionConfig,
    reporting_client: ReportingClientDependency,
    service: MetaSyncServiceDependency,
) -> dict[str, str | None]:
    await _require_client(client_id, reporting_client)
    return await service.configure_connection(client_id=client_id, config=config)


@router.post("/test")
async def test_meta_connection(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    service: MetaSyncServiceDependency,
) -> dict[str, bool]:
    await _require_client(client_id, reporting_client)
    return {"connected": await service.test_connection(client_id=client_id)}


@router.post("/sync", response_model=MetaSyncResult)
async def sync_meta_data(
    client_id: UUID,
    sync_request: MetaSyncRequest,
    reporting_client: ReportingClientDependency,
    service: MetaSyncServiceDependency,
) -> MetaSyncResult:
    await _require_client(client_id, reporting_client)
    return await service.sync_data(client_id=client_id, request=sync_request)


@router.get("/sync-runs")
async def get_meta_sync_runs(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    repository: MetaRepositoryDependency,
    limit: int = Query(default=10, ge=1, le=100),
) -> list[dict[str, str | int | None]]:
    await _require_client(client_id, reporting_client)
    return await repository.get_sync_runs(client_id=client_id, limit=limit)
