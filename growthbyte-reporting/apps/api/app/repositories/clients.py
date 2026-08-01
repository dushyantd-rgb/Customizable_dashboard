from uuid import UUID

from app.data.supabase import ReportingSupabaseClientProtocol


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
