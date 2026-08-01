"""API routes for Meta Ads integration."""

from uuid import UUID

from fastapi import APIRouter, status

from app.api.v1.dependencies import ReportingClientDependency
from app.core.errors import ClientNotFoundError
from app.integrations.meta.dependencies import (
    MetaClientDependency,
    MetaRepositoryDependency,
    MetaSyncServiceDependency,
)
from app.integrations.meta.models import (
    MetaAccountDiscoveryResponse,
    MetaConnectionConfig,
    MetaSyncRequest,
    MetaSyncResult,
)

router = APIRouter(prefix="/integrations/meta", tags=["meta"])


async def _require_client(
    client_id: UUID, client: ReportingClientDependency
) -> None:
    """Verify that a client exists."""
    from app.repositories.clients import ReportingClientRepository

    if not await ReportingClientRepository(client).exists(client_id=client_id):
        raise ClientNotFoundError


@router.get("/accounts", response_model=MetaAccountDiscoveryResponse)
async def discover_meta_accounts(
    meta_client: MetaClientDependency,
) -> MetaAccountDiscoveryResponse:
    """
    Discover Meta ad accounts accessible to the environment token.

    Returns account summaries with stable IDs and display names.
    Never returns tokens or credentials.
    """
    accounts = await meta_client.discover_ad_accounts()
    return MetaAccountDiscoveryResponse(accounts=accounts)


@router.post(
    "/clients/{client_id}/config",
    status_code=status.HTTP_200_OK,
)
async def configure_meta_connection(
    client_id: UUID,
    config: MetaConnectionConfig,
    reporting_client: ReportingClientDependency,
    sync_service: MetaSyncServiceDependency,
) -> dict[str, str]:
    """
    Configure a Meta connection for a specific client.

    Links one Meta ad account to the client.
    Stores only non-secret metadata.
    """
    await _require_client(client_id, reporting_client)
    return await sync_service.configure_connection(
        client_id=client_id, config=config
    )


@router.post("/clients/{client_id}/test", status_code=status.HTTP_200_OK)
async def test_meta_connection(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    repository: MetaRepositoryDependency,
) -> dict[str, bool]:
    """
    Test the Meta connection for a client.

    Returns success status without exposing credentials.
    """
    await _require_client(client_id, reporting_client)
    connected = await repository.get_connection(
        client_id=client_id, provider="meta"
    )
    return {"connected": connected is not None}


@router.post(
    "/clients/{client_id}/sync",
    response_model=MetaSyncResult,
    status_code=status.HTTP_200_OK,
)
async def sync_meta_data(
    client_id: UUID,
    request: MetaSyncRequest,
    reporting_client: ReportingClientDependency,
    sync_service: MetaSyncServiceDependency,
) -> MetaSyncResult:
    """
    Manually sync Meta Ads data for a client.

    Pulls campaigns, ad sets, ads, and insights for the specified date range.
    Stores data with client-scoped idempotency.
    Never returns or logs tokens.
    """
    await _require_client(client_id, reporting_client)
    return await sync_service.sync_data(client_id=client_id, request=request)


@router.get("/clients/{client_id}/sync-runs")
async def get_meta_sync_runs(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    repository: MetaRepositoryDependency,
    limit: int = 10,
) -> list[dict[str, str | int | None]]:
    """
    Get recent Meta sync runs for a client.

    Returns sync history with status, counts, and safe error summaries.
    """
    await _require_client(client_id, reporting_client)
    runs = await repository.get_sync_runs(
        client_id=client_id, source_type="meta", limit=limit
    )
    return runs
