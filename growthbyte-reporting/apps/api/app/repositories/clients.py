from uuid import UUID

from app.data.supabase import ReportingSupabaseClientProtocol
from app.models.client_management import ClientDetails, ClientSummary

_CLIENT_SUMMARY_COLUMNS = ("id", "name", "slug", "status")
_CLIENT_DETAIL_COLUMNS = (
    "id",
    "name",
    "slug",
    "reporting_timezone",
    "default_currency",
    "status",
    "created_at",
    "updated_at",
)


class ReportingClientRepository:
    def __init__(self, client: ReportingSupabaseClientProtocol) -> None:
        self.__client = client

    async def exists(self, *, client_id: UUID) -> bool:
        rows = await self.__client.select(
            table="clients",
            columns=("id",),
            filters={"id": str(client_id)},
            limit=1,
        )
        return bool(rows)

    async def list_all(self) -> tuple[ClientSummary, ...]:
        rows = await self.__client.select(
            table="clients",
            columns=_CLIENT_SUMMARY_COLUMNS,
            filters={},
            limit=1000,
        )
        return tuple(ClientSummary.model_validate(row) for row in rows)

    async def get(self, *, client_id: UUID) -> ClientDetails | None:
        rows = await self.__client.select(
            table="clients",
            columns=_CLIENT_DETAIL_COLUMNS,
            filters={"id": str(client_id)},
            limit=1,
        )
        if not rows:
            return None
        return ClientDetails.model_validate(rows[0])
