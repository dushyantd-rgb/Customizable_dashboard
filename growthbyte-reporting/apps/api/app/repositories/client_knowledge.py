from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.data.supabase import ReportingSupabaseClientProtocol
from app.knowledge.errors import MappingValidationError, PartialImportError
from app.knowledge.models import MappedKnowledgeRecord
from app.models.client_management import KnowledgeCreate, KnowledgeRecord, KnowledgeUpdate

_KNOWLEDGE_COLUMNS = (
    "id",
    "client_id",
    "category",
    "knowledge_key",
    "value",
    "status",
    "source_type",
    "source_identifier",
    "source_display_name",
    "source_reference",
    "source_version",
    "imported_at",
    "version",
    "approved_by_label",
    "approved_at",
    "created_at",
    "updated_at",
)

SOURCE_IDENTITY_CONFLICT_TARGET = (
    "client_id",
    "source_type",
    "source_identifier",
    "source_version",
)


class ClientKnowledgeRepository:
    def __init__(self, client: ReportingSupabaseClientProtocol) -> None:
        self.__client = client

    async def list_for_client(self, *, client_id: UUID) -> tuple[KnowledgeRecord, ...]:
        rows = await self.__client.select(
            table="client_knowledge",
            columns=_KNOWLEDGE_COLUMNS,
            filters={"client_id": str(client_id)},
            limit=1000,
        )
        return tuple(KnowledgeRecord.model_validate(row) for row in rows)

    async def get(self, *, client_id: UUID, knowledge_id: UUID) -> KnowledgeRecord | None:
        rows = await self.__client.select(
            table="client_knowledge",
            columns=_KNOWLEDGE_COLUMNS,
            filters={"client_id": str(client_id), "id": str(knowledge_id)},
            limit=1,
        )
        if not rows:
            return None
        return KnowledgeRecord.model_validate(rows[0])

    async def create_manual(self, *, client_id: UUID, create: KnowledgeCreate) -> KnowledgeRecord:
        row = create.model_dump(mode="json")
        row.update(
            {
                "client_id": str(client_id),
                "source_type": "manual",
                "source_identifier": None,
                "source_version": None,
                "version": 1,
            }
        )
        inserted = await self.__client.insert(table="client_knowledge", row=row)
        return KnowledgeRecord.model_validate(inserted)

    async def update(
        self,
        *,
        client_id: UUID,
        knowledge_id: UUID,
        update: KnowledgeUpdate,
    ) -> KnowledgeRecord | None:
        values = update.model_dump(mode="json", exclude_unset=True)
        rows = await self.__client.update(
            table="client_knowledge",
            values=values,
            filters={"client_id": str(client_id), "id": str(knowledge_id)},
        )
        if not rows:
            return None
        return KnowledgeRecord.model_validate(rows[0])

    async def upsert_imported(
        self,
        *,
        client_id: UUID,
        records: Sequence[MappedKnowledgeRecord],
        imported_at: datetime,
        import_batch_id: UUID,
    ) -> int:
        if any(not record.source_identifier or not record.source_version for record in records):
            raise MappingValidationError
        if not records:
            return 0

        rows = [
            {
                "client_id": str(client_id),
                "category": record.category,
                "knowledge_key": record.knowledge_key,
                "value": record.value,
                "status": record.status,
                "source_type": record.source_type,
                "source_identifier": record.source_identifier,
                "source_display_name": record.source_display_name,
                "source_reference": record.source_reference,
                "source_version": record.source_version,
                "source_hash": record.source_hash,
                "import_batch_id": str(import_batch_id),
                "imported_at": imported_at.isoformat(),
                "version": record.version,
            }
            for record in records
        ]
        returned_rows = await self.__client.upsert(
            table="client_knowledge",
            rows=rows,
            on_conflict=SOURCE_IDENTITY_CONFLICT_TARGET,
        )
        if len(returned_rows) != len(rows):
            raise PartialImportError
        return len(returned_rows)
