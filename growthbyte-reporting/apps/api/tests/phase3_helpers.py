"""Small PostgREST-shaped in-memory store for Phase 3 connector tests."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from tests.helpers import SYNTHETIC_CLIENT_A_ID, SYNTHETIC_CLIENT_B_ID


class Phase3MemoryClient:
    """Persist connector rows and enforce the filters repositories send."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {
            "clients": [
                {"id": SYNTHETIC_CLIENT_A_ID},
                {"id": SYNTHETIC_CLIENT_B_ID},
            ]
        }
        self.select_calls: list[dict[str, Any]] = []
        self.insert_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []
        self.upsert_calls: list[dict[str, Any]] = []

    @staticmethod
    def _matches(row: Mapping[str, Any], filters: Mapping[str, str]) -> bool:
        return all(str(row.get(column)) == str(value) for column, value in filters.items())

    @staticmethod
    def _stored(row: Mapping[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        return {
            "id": str(row.get("id") or uuid4()),
            "created_at": str(row.get("created_at") or now),
            "updated_at": str(row.get("updated_at") or now),
            **dict(row),
        }

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
        matches = [row for row in self.rows.get(table, []) if self._matches(row, filters)][:limit]
        return [{column: row.get(column) for column in columns} for row in matches]

    async def insert(self, *, table: str, row: Mapping[str, Any]) -> dict[str, Any]:
        stored = self._stored(row)
        self.insert_calls.append({"table": table, "row": dict(row)})
        self.rows.setdefault(table, []).append(stored)
        return dict(stored)

    async def update(
        self,
        *,
        table: str,
        values: Mapping[str, Any],
        filters: Mapping[str, str],
    ) -> list[dict[str, Any]]:
        self.update_calls.append({"table": table, "values": dict(values), "filters": dict(filters)})
        updated: list[dict[str, Any]] = []
        for row in self.rows.get(table, []):
            if self._matches(row, filters):
                row.update(values)
                row["updated_at"] = datetime.now(UTC).isoformat()
                updated.append(dict(row))
        return updated

    async def upsert(
        self,
        *,
        table: str,
        rows: Sequence[Mapping[str, Any]],
        on_conflict: Sequence[str],
    ) -> list[dict[str, Any]]:
        incoming = [dict(row) for row in rows]
        self.upsert_calls.append(
            {"table": table, "rows": incoming, "on_conflict": tuple(on_conflict)}
        )
        stored_rows: list[dict[str, Any]] = []
        table_rows = self.rows.setdefault(table, [])
        for row in incoming:
            existing = next(
                (
                    candidate
                    for candidate in table_rows
                    if all(
                        str(candidate.get(column)) == str(row.get(column)) for column in on_conflict
                    )
                ),
                None,
            )
            if existing is None:
                existing = self._stored(row)
                table_rows.append(existing)
            else:
                existing.update(row)
                existing["updated_at"] = datetime.now(UTC).isoformat()
            stored_rows.append(dict(existing))
        return stored_rows

    async def ping(self, *, table: str) -> None:
        self.rows.setdefault(table, [])

    async def close(self) -> None:
        return None
