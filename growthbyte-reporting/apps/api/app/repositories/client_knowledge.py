from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.data.supabase import ReportingSupabaseClientProtocol
from app.knowledge.errors import MappingValidationError, PartialImportError
from app.knowledge.models import MappedKnowledgeRecord

SOURCE_IDENTITY_CONFLICT_TARGET = (
    "client_id",
    "source_type",
    "source_identifier",
    "source_version",
)


class ClientKnowledgeRepository:
    def __init__(self, client: ReportingSupabaseClientProtocol) -> None:
        self.__client = client

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
