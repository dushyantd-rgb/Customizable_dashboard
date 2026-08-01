from collections.abc import Mapping, Sequence
from typing import Any


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
