from uuid import UUID

from fastapi import APIRouter

from app.api.v1.dependencies import ReportingClientDependency
from app.core.errors import ClientNotFoundError
from app.models.client_management import ClientDetails, ClientSummary
from app.repositories.clients import ReportingClientRepository

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientSummary])
async def list_clients(
    client: ReportingClientDependency,
) -> tuple[ClientSummary, ...]:
    return await ReportingClientRepository(client).list_all()


@router.get("/{client_id}", response_model=ClientDetails)
async def get_client(
    client_id: UUID,
    client: ReportingClientDependency,
) -> ClientDetails:
    record = await ReportingClientRepository(client).get(client_id=client_id)
    if record is None:
        raise ClientNotFoundError
    return record
