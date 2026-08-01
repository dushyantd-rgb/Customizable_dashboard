from uuid import UUID

from app.data.supabase import ReportingSupabaseClientProtocol
from app.models.client_management import KpiCreate, KpiRecord, KpiUpdate

_KPI_COLUMNS = (
    "id",
    "client_id",
    "metric_key",
    "label",
    "target_value",
    "unit",
    "direction",
    "attribution_level",
    "active_from",
    "active_to",
    "created_at",
    "updated_at",
)


class ClientKpiRepository:
    def __init__(self, client: ReportingSupabaseClientProtocol) -> None:
        self.__client = client

    async def list_for_client(self, *, client_id: UUID) -> tuple[KpiRecord, ...]:
        rows = await self.__client.select(
            table="client_kpis",
            columns=_KPI_COLUMNS,
            filters={"client_id": str(client_id)},
            limit=1000,
        )
        return tuple(KpiRecord.model_validate(row) for row in rows)

    async def get(self, *, client_id: UUID, kpi_id: UUID) -> KpiRecord | None:
        rows = await self.__client.select(
            table="client_kpis",
            columns=_KPI_COLUMNS,
            filters={"client_id": str(client_id), "id": str(kpi_id)},
            limit=1,
        )
        if not rows:
            return None
        return KpiRecord.model_validate(rows[0])

    async def create(self, *, client_id: UUID, create: KpiCreate) -> KpiRecord:
        row = create.model_dump(mode="json")
        row["client_id"] = str(client_id)
        inserted = await self.__client.insert(table="client_kpis", row=row)
        return KpiRecord.model_validate(inserted)

    async def update(
        self,
        *,
        client_id: UUID,
        kpi_id: UUID,
        update: KpiUpdate,
    ) -> KpiRecord | None:
        values = update.model_dump(mode="json", exclude_unset=True)
        rows = await self.__client.update(
            table="client_kpis",
            values=values,
            filters={"client_id": str(client_id), "id": str(kpi_id)},
        )
        if not rows:
            return None
        return KpiRecord.model_validate(rows[0])
