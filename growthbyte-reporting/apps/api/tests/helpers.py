from collections.abc import Mapping, Sequence
from typing import Any

SYNTHETIC_CLIENT_A_ID = "00000000-0000-4000-8000-0000000000a1"
SYNTHETIC_CLIENT_B_ID = "00000000-0000-4000-8000-0000000000a2"
SYNTHETIC_KNOWLEDGE_A_ID = "00000000-0000-4000-8000-0000000000b1"
SYNTHETIC_KNOWLEDGE_B_ID = "00000000-0000-4000-8000-0000000000b2"
SYNTHETIC_KNOWLEDGE_A_EXTRA_ID = "00000000-0000-4000-8000-0000000000b3"
SYNTHETIC_KNOWLEDGE_B_EXTRA_ID = "00000000-0000-4000-8000-0000000000b4"
SYNTHETIC_KPI_A_ID = "00000000-0000-4000-8000-0000000000c1"
SYNTHETIC_KPI_B_ID = "00000000-0000-4000-8000-0000000000c2"
SYNTHETIC_KPI_A_EXTRA_ID = "00000000-0000-4000-8000-0000000000c3"
SYNTHETIC_KPI_B_EXTRA_ID = "00000000-0000-4000-8000-0000000000c4"

_SYNTHETIC_TIMESTAMP = "2026-08-01T00:00:00Z"


class InMemoryReportingClient:
    """PostgREST-shaped fake with two de-identified, deliberately colliding clients."""

    def __init__(self) -> None:
        alpha_audience = self._knowledge_row(
            row_id=SYNTHETIC_KNOWLEDGE_A_EXTRA_ID,
            client_id=SYNTHETIC_CLIENT_A_ID,
            value="alpha synthetic audience",
        )
        alpha_audience.update(
            {
                "category": "audience",
                "knowledge_key": "buyer_profile",
                "value": {"segments": ["synthetic operations", "synthetic finance"]},
                "source_type": "manual",
                "source_identifier": None,
                "source_display_name": None,
                "source_reference": None,
                "source_version": None,
                "source_hash": None,
                "import_batch_id": None,
                "imported_at": None,
                "version": 1,
            }
        )
        beta_offering = self._knowledge_row(
            row_id=SYNTHETIC_KNOWLEDGE_B_EXTRA_ID,
            client_id=SYNTHETIC_CLIENT_B_ID,
            value="beta synthetic offering",
        )
        beta_offering.update(
            {
                "category": "offering",
                "knowledge_key": "service_catalog",
                "value": {"services": [{"name": "Synthetic advisory", "tier": "test"}]},
                "source_version": "3",
                "version": 3,
            }
        )

        alpha_cost_kpi = self._kpi_row(
            row_id=SYNTHETIC_KPI_A_EXTRA_ID,
            client_id=SYNTHETIC_CLIENT_A_ID,
            target="45",
        )
        alpha_cost_kpi.update(
            {
                "metric_key": "cost_per_lead",
                "label": "Synthetic cost per lead",
                "unit": "currency",
                "direction": "decrease",
            }
        )
        beta_rate_kpi = self._kpi_row(
            row_id=SYNTHETIC_KPI_B_EXTRA_ID,
            client_id=SYNTHETIC_CLIENT_B_ID,
            target="60",
        )
        beta_rate_kpi.update(
            {
                "metric_key": "qualification_rate",
                "label": "Synthetic qualification rate",
                "unit": "percent",
                "direction": "increase",
                "active_from": "2026-04-01",
                "active_to": None,
            }
        )

        self.rows: dict[str, list[dict[str, Any]]] = {
            "clients": [
                {
                    "id": SYNTHETIC_CLIENT_A_ID,
                    "name": "Development Alpha",
                    "slug": "development-alpha",
                    "reporting_timezone": "UTC",
                    "default_currency": "USD",
                    "status": "active",
                    "created_at": _SYNTHETIC_TIMESTAMP,
                    "updated_at": _SYNTHETIC_TIMESTAMP,
                },
                {
                    "id": SYNTHETIC_CLIENT_B_ID,
                    "name": "Development Beta",
                    "slug": "development-beta",
                    "reporting_timezone": "UTC",
                    "default_currency": "USD",
                    "status": "active",
                    "created_at": _SYNTHETIC_TIMESTAMP,
                    "updated_at": _SYNTHETIC_TIMESTAMP,
                },
            ],
            "client_knowledge": [
                self._knowledge_row(
                    row_id=SYNTHETIC_KNOWLEDGE_A_ID,
                    client_id=SYNTHETIC_CLIENT_A_ID,
                    value="alpha synthetic knowledge",
                ),
                self._knowledge_row(
                    row_id=SYNTHETIC_KNOWLEDGE_B_ID,
                    client_id=SYNTHETIC_CLIENT_B_ID,
                    value="beta synthetic knowledge",
                ),
                alpha_audience,
                beta_offering,
            ],
            "client_kpis": [
                self._kpi_row(
                    row_id=SYNTHETIC_KPI_A_ID,
                    client_id=SYNTHETIC_CLIENT_A_ID,
                    target="10",
                ),
                self._kpi_row(
                    row_id=SYNTHETIC_KPI_B_ID,
                    client_id=SYNTHETIC_CLIENT_B_ID,
                    target="20",
                ),
                alpha_cost_kpi,
                beta_rate_kpi,
            ],
        }
        self.select_calls: list[dict[str, Any]] = []
        self.insert_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []
        self.upsert_calls: list[dict[str, Any]] = []

    @staticmethod
    def _knowledge_row(*, row_id: str, client_id: str, value: str) -> dict[str, Any]:
        return {
            "id": row_id,
            "client_id": client_id,
            "category": "shared_category",
            "knowledge_key": "shared_key",
            "value": {"summary": value},
            "status": "draft",
            "source_type": "knowledge_supabase_section",
            "source_identifier": "shared-source-identifier",
            "source_display_name": "Synthetic source section",
            "source_reference": "org_knowledge_base_sections",
            "source_version": "7",
            "source_hash": "synthetic-internal-source-hash",
            "import_batch_id": "00000000-0000-4000-8000-0000000000d1",
            "imported_at": _SYNTHETIC_TIMESTAMP,
            "version": 7,
            "approved_by_label": None,
            "approved_at": None,
            "created_at": _SYNTHETIC_TIMESTAMP,
            "updated_at": _SYNTHETIC_TIMESTAMP,
        }

    @staticmethod
    def _kpi_row(*, row_id: str, client_id: str, target: str) -> dict[str, Any]:
        return {
            "id": row_id,
            "client_id": client_id,
            "metric_key": "shared_metric",
            "label": "Shared synthetic metric",
            "target_value": target,
            "unit": "count",
            "direction": "increase",
            "attribution_level": "client",
            "active_from": "2026-01-01",
            "active_to": "2026-12-31",
            "created_at": _SYNTHETIC_TIMESTAMP,
            "updated_at": _SYNTHETIC_TIMESTAMP,
        }

    @staticmethod
    def _matches(row: Mapping[str, Any], filters: Mapping[str, str]) -> bool:
        return all(str(row.get(column)) == value for column, value in filters.items())

    async def select(
        self,
        *,
        table: str,
        columns: Sequence[str],
        filters: Mapping[str, str],
        limit: int,
    ) -> list[dict[str, Any]]:
        self.select_calls.append(
            {"table": table, "columns": tuple(columns), "filters": dict(filters), "limit": limit}
        )
        matches = (row for row in self.rows.get(table, []) if self._matches(row, filters))
        return [{column: row.get(column) for column in columns} for row in list(matches)[:limit]]

    async def insert(self, *, table: str, row: Mapping[str, Any]) -> dict[str, Any]:
        copied = dict(row)
        self.insert_calls.append({"table": table, "row": copied})
        if table == "client_knowledge":
            inserted = self._knowledge_row(
                row_id="00000000-0000-4000-8000-0000000000bf",
                client_id=str(copied["client_id"]),
                value="manual synthetic knowledge",
            )
            inserted.update(
                {
                    "source_type": "manual",
                    "source_identifier": None,
                    "source_display_name": None,
                    "source_reference": None,
                    "source_version": None,
                    "source_hash": None,
                    "import_batch_id": None,
                    "imported_at": None,
                    "version": 1,
                }
            )
            inserted.update(copied)
        elif table == "client_kpis":
            inserted = self._kpi_row(
                row_id="00000000-0000-4000-8000-0000000000cf",
                client_id=str(copied["client_id"]),
                target=str(copied.get("target_value") or "0"),
            )
            inserted.update(copied)
        else:
            raise AssertionError("Unexpected synthetic insert table")
        self.rows[table].append(inserted)
        return dict(inserted)

    async def update(
        self,
        *,
        table: str,
        values: Mapping[str, Any],
        filters: Mapping[str, str],
    ) -> list[dict[str, Any]]:
        copied_values = dict(values)
        copied_filters = dict(filters)
        self.update_calls.append(
            {"table": table, "values": copied_values, "filters": copied_filters}
        )
        updated: list[dict[str, Any]] = []
        for row in self.rows.get(table, []):
            if self._matches(row, copied_filters):
                row.update(copied_values)
                row["updated_at"] = "2026-08-02T00:00:00Z"
                updated.append(dict(row))
        return updated

    async def upsert(
        self,
        *,
        table: str,
        rows: Sequence[Mapping[str, Any]],
        on_conflict: Sequence[str],
    ) -> list[dict[str, Any]]:
        copied_rows = [dict(row) for row in rows]
        self.upsert_calls.append(
            {"table": table, "rows": copied_rows, "on_conflict": tuple(on_conflict)}
        )
        return copied_rows

    async def ping(self, *, table: str) -> None:
        if table not in self.rows:
            raise RuntimeError("Unknown synthetic table")

    async def close(self) -> None:
        return None


class FakeReportingClient:
    def __init__(self, *, client_exists: bool = True, reachable: bool = True) -> None:
        self.client_exists = client_exists
        self.reachable = reachable
        self.select_calls: list[dict[str, Any]] = []
        self.upsert_calls: list[dict[str, Any]] = []
        self.rows_by_source_identity: dict[tuple[str, ...], dict[str, Any]] = {}

    async def select(
        self,
        *,
        table: str,
        columns: Sequence[str],
        filters: Mapping[str, str],
        limit: int,
    ) -> list[dict[str, Any]]:
        self.select_calls.append(
            {"table": table, "columns": tuple(columns), "filters": dict(filters), "limit": limit}
        )
        if table == "clients" and self.client_exists:
            return [{"id": filters["id"]}]
        return []

    async def upsert(
        self,
        *,
        table: str,
        rows: Sequence[Mapping[str, Any]],
        on_conflict: Sequence[str],
    ) -> list[dict[str, Any]]:
        copied_rows = [dict(row) for row in rows]
        self.upsert_calls.append(
            {"table": table, "rows": copied_rows, "on_conflict": tuple(on_conflict)}
        )
        for row in copied_rows:
            identity = tuple(str(row[column]) for column in on_conflict)
            self.rows_by_source_identity[identity] = row
        return copied_rows

    async def ping(self, *, table: str) -> None:
        if not self.reachable:
            raise RuntimeError("synthetic backend failure")

    async def close(self) -> None:
        return None


class FakeKnowledgeClient:
    def __init__(
        self,
        *,
        rows: dict[str, list[dict[str, Any]]] | None = None,
        reachable: bool = True,
    ) -> None:
        self.rows = rows or {}
        self.reachable = reachable
        self.select_calls: list[dict[str, Any]] = []

    async def select(
        self,
        *,
        table: str,
        columns: Sequence[str],
        filters: Mapping[str, str],
        limit: int,
    ) -> list[dict[str, Any]]:
        self.select_calls.append(
            {"table": table, "columns": tuple(columns), "filters": dict(filters), "limit": limit}
        )
        return [dict(row) for row in self.rows.get(table, [])]

    async def ping(self, *, table: str) -> None:
        if not self.reachable:
            raise RuntimeError("synthetic backend failure")

    async def close(self) -> None:
        return None


def source_rows(
    *, section_overrides: dict[str, Any] | None = None
) -> dict[str, list[dict[str, Any]]]:
    section = {
        "id": "00000000-0000-4000-8000-000000000020",
        "client_id": "source-client",
        "section_key": "sample_section",
        "content": "synthetic fragment",
        "version": 2,
    }
    section.update(section_overrides or {})
    return {
        "org_clients": [{"id": "source-client"}],
        "org_knowledge_items": [],
        "org_knowledge_base_sections": [section],
    }
