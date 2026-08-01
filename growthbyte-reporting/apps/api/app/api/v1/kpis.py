from uuid import UUID

from fastapi import APIRouter, status

from app.api.v1.dependencies import ReportingClientDependency
from app.core.errors import ClientNotFoundError, KpiIntervalError, KpiRecordNotFoundError
from app.data.supabase import ReportingSupabaseClientProtocol
from app.models.client_management import KpiCreate, KpiRecord, KpiUpdate
from app.repositories.client_kpis import ClientKpiRepository
from app.repositories.clients import ReportingClientRepository

router = APIRouter(prefix="/clients/{client_id}/kpis", tags=["client KPIs"])


async def _require_client(client_id: UUID, client: ReportingSupabaseClientProtocol) -> None:
    if not await ReportingClientRepository(client).exists(client_id=client_id):
        raise ClientNotFoundError


@router.get("", response_model=list[KpiRecord])
async def list_kpis(
    client_id: UUID,
    client: ReportingClientDependency,
) -> tuple[KpiRecord, ...]:
    await _require_client(client_id, client)
    return await ClientKpiRepository(client).list_for_client(client_id=client_id)


@router.get("/{kpi_id}", response_model=KpiRecord)
async def get_kpi(
    client_id: UUID,
    kpi_id: UUID,
    client: ReportingClientDependency,
) -> KpiRecord:
    await _require_client(client_id, client)
    record = await ClientKpiRepository(client).get(client_id=client_id, kpi_id=kpi_id)
    if record is None:
        raise KpiRecordNotFoundError
    return record


@router.post("", response_model=KpiRecord, status_code=status.HTTP_201_CREATED)
async def create_kpi(
    client_id: UUID,
    create: KpiCreate,
    client: ReportingClientDependency,
) -> KpiRecord:
    await _require_client(client_id, client)
    return await ClientKpiRepository(client).create(client_id=client_id, create=create)


@router.patch("/{kpi_id}", response_model=KpiRecord)
async def update_kpi(
    client_id: UUID,
    kpi_id: UUID,
    update: KpiUpdate,
    client: ReportingClientDependency,
) -> KpiRecord:
    await _require_client(client_id, client)
    repository = ClientKpiRepository(client)
    existing = await repository.get(client_id=client_id, kpi_id=kpi_id)
    if existing is None:
        raise KpiRecordNotFoundError

    active_from = existing.active_from
    if "active_from" in update.model_fields_set:
        assert update.active_from is not None
        active_from = update.active_from
    active_to = update.active_to if "active_to" in update.model_fields_set else existing.active_to
    if active_to is not None and active_to < active_from:
        raise KpiIntervalError

    record = await repository.update(client_id=client_id, kpi_id=kpi_id, update=update)
    if record is None:
        raise KpiRecordNotFoundError
    return record
