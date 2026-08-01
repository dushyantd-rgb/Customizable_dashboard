from typing import Any

from app.data.supabase import SupabaseReadClient
from app.knowledge.errors import (
    DuplicateSourceClientError,
    InvalidSourceClientIdentifierError,
    MissingSourceClientError,
)
from app.knowledge.models import SourceClient, SourceKnowledgeRecord

_SOURCE_CLIENT_COLUMNS = ("id",)
_KNOWLEDGE_ITEM_COLUMNS = (
    "id",
    "client_id",
    "title",
    "content",
    "content_type",
    "tags",
    "created_at",
    "updated_at",
)
_KNOWLEDGE_SECTION_COLUMNS = (
    "id",
    "client_id",
    "section_number",
    "section_key",
    "title",
    "content",
    "structured_data",
    "approvals",
    "version",
    "created_at",
    "updated_at",
)


class ReadOnlyKnowledgeAdapter:
    """Narrow source interface containing read operations only."""

    def __init__(self, client: SupabaseReadClient) -> None:
        self.__client = client

    async def ping(self) -> None:
        await self.__client.ping(table="org_clients")

    async def get_client(self, *, source_client_identifier: str) -> SourceClient:
        normalized_identifier = source_client_identifier.strip()
        if not normalized_identifier or len(normalized_identifier) > 200:
            raise InvalidSourceClientIdentifierError
        rows = await self.__client.select(
            table="org_clients",
            columns=_SOURCE_CLIENT_COLUMNS,
            filters={"id": normalized_identifier},
            limit=2,
        )
        if not rows:
            raise MissingSourceClientError
        if len(rows) > 1:
            raise DuplicateSourceClientError
        identifier = _required_string(rows[0], "id")
        if identifier is None:
            raise MissingSourceClientError
        return SourceClient(identifier=identifier)

    async def list_knowledge(
        self, *, source_client_identifier: str
    ) -> tuple[SourceKnowledgeRecord, ...]:
        item_rows = await self.__client.select(
            table="org_knowledge_items",
            columns=_KNOWLEDGE_ITEM_COLUMNS,
            filters={"client_id": source_client_identifier},
            limit=1000,
        )
        section_rows = await self.__client.select(
            table="org_knowledge_base_sections",
            columns=_KNOWLEDGE_SECTION_COLUMNS,
            filters={"client_id": source_client_identifier},
            limit=1000,
        )
        return tuple(
            SourceKnowledgeRecord(table="org_knowledge_items", fields=row) for row in item_rows
        ) + tuple(
            SourceKnowledgeRecord(table="org_knowledge_base_sections", fields=row)
            for row in section_rows
        )


def _required_string(row: dict[str, Any], field: str) -> str | None:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()
