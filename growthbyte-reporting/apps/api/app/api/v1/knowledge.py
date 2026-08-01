from uuid import UUID

from fastapi import APIRouter, status

from app.api.v1.dependencies import ReportingClientDependency
from app.core.errors import ClientNotFoundError, KnowledgeRecordNotFoundError
from app.data.supabase import ReportingSupabaseClientProtocol
from app.models.client_management import KnowledgeCreate, KnowledgeRecord, KnowledgeUpdate
from app.repositories.client_knowledge import ClientKnowledgeRepository
from app.repositories.clients import ReportingClientRepository

router = APIRouter(prefix="/clients/{client_id}/knowledge", tags=["client knowledge"])


async def _require_client(client_id: UUID, client: ReportingSupabaseClientProtocol) -> None:
    if not await ReportingClientRepository(client).exists(client_id=client_id):
        raise ClientNotFoundError


@router.get("", response_model=list[KnowledgeRecord])
async def list_knowledge(
    client_id: UUID,
    client: ReportingClientDependency,
) -> tuple[KnowledgeRecord, ...]:
    await _require_client(client_id, client)
    return await ClientKnowledgeRepository(client).list_for_client(client_id=client_id)


@router.get("/{knowledge_id}", response_model=KnowledgeRecord)
async def get_knowledge(
    client_id: UUID,
    knowledge_id: UUID,
    client: ReportingClientDependency,
) -> KnowledgeRecord:
    await _require_client(client_id, client)
    record = await ClientKnowledgeRepository(client).get(
        client_id=client_id, knowledge_id=knowledge_id
    )
    if record is None:
        raise KnowledgeRecordNotFoundError
    return record


@router.post("", response_model=KnowledgeRecord, status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    client_id: UUID,
    create: KnowledgeCreate,
    client: ReportingClientDependency,
) -> KnowledgeRecord:
    await _require_client(client_id, client)
    return await ClientKnowledgeRepository(client).create_manual(client_id=client_id, create=create)


@router.patch("/{knowledge_id}", response_model=KnowledgeRecord)
async def update_knowledge(
    client_id: UUID,
    knowledge_id: UUID,
    update: KnowledgeUpdate,
    client: ReportingClientDependency,
) -> KnowledgeRecord:
    await _require_client(client_id, client)
    record = await ClientKnowledgeRepository(client).update(
        client_id=client_id,
        knowledge_id=knowledge_id,
        update=update,
    )
    if record is None:
        raise KnowledgeRecordNotFoundError
    return record
