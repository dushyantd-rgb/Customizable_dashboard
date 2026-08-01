import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal, NoReturn, Protocol

import httpx

from app.core.config import SupabaseConnectionSettings
from app.knowledge.errors import (
    PlaceholderCredentialsError,
    ReportingDatabaseUnavailableError,
    SourceDatabaseUnavailableError,
    UpsertConflictError,
)

_IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")

REPORTING_TABLES = frozenset({"clients", "client_knowledge"})
KNOWLEDGE_SOURCE_TABLES = frozenset(
    {
        "org_clients",
        "org_knowledge_items",
        "org_knowledge_base_sections",
    }
)


class SupabaseReadClient(Protocol):
    async def select(
        self,
        *,
        table: str,
        columns: Sequence[str],
        filters: Mapping[str, str],
        limit: int,
    ) -> list[dict[str, Any]]: ...

    async def ping(self, *, table: str) -> None: ...

    async def close(self) -> None: ...


class ReportingSupabaseClientProtocol(SupabaseReadClient, Protocol):
    async def upsert(
        self,
        *,
        table: str,
        rows: Sequence[Mapping[str, Any]],
        on_conflict: Sequence[str],
    ) -> list[dict[str, Any]]: ...


class _SupabaseRestClient:
    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        allowed_tables: frozenset[str],
        component: Literal["reporting", "knowledge"],
    ) -> None:
        self._http_client = http_client
        self._allowed_tables = allowed_tables
        self._component = component

    def _validate_table(self, table: str) -> None:
        if table not in self._allowed_tables:
            raise ValueError("Table is not allowlisted for this Supabase client")

    @staticmethod
    def _validate_identifiers(identifiers: Sequence[str]) -> None:
        if not identifiers or any(not _IDENTIFIER_PATTERN.fullmatch(item) for item in identifiers):
            raise ValueError("Supabase query contains an invalid identifier")

    async def _get(self, *, table: str, params: list[tuple[str, str]]) -> httpx.Response:
        self._validate_table(table)
        try:
            response = await self._http_client.get(f"/{table}", params=params)
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._raise_unavailable(error)
        if response.status_code >= 400:
            self._raise_unavailable()
        return response

    def _raise_unavailable(self, cause: Exception | None = None) -> NoReturn:
        if self._component == "knowledge":
            raise SourceDatabaseUnavailableError from cause
        raise ReportingDatabaseUnavailableError from cause

    @staticmethod
    def _decode_rows(response: httpx.Response) -> list[dict[str, Any]]:
        try:
            payload = response.json()
        except ValueError as error:
            raise ReportingDatabaseUnavailableError from error
        if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
            raise ReportingDatabaseUnavailableError
        return payload

    async def select(
        self,
        *,
        table: str,
        columns: Sequence[str],
        filters: Mapping[str, str],
        limit: int,
    ) -> list[dict[str, Any]]:
        self._validate_identifiers(columns)
        if filters:
            self._validate_identifiers(tuple(filters))
        if limit < 1 or limit > 1000:
            raise ValueError("Supabase query limit is outside the allowed range")
        params = [("select", ",".join(columns)), ("limit", str(limit))]
        params.extend((column, f"eq.{value}") for column, value in filters.items())
        response = await self._get(table=table, params=params)
        try:
            payload = response.json()
        except ValueError:
            self._raise_unavailable()
        if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
            self._raise_unavailable()
        return payload

    async def ping(self, *, table: str) -> None:
        await self.select(table=table, columns=("id",), filters={}, limit=1)

    async def close(self) -> None:
        await self._http_client.aclose()


class ReportingSupabaseClient(_SupabaseRestClient):
    async def upsert(
        self,
        *,
        table: str,
        rows: Sequence[Mapping[str, Any]],
        on_conflict: Sequence[str],
    ) -> list[dict[str, Any]]:
        self._validate_identifiers(on_conflict)
        if not rows:
            return []
        self._validate_table(table)
        try:
            response = await self._http_client.post(
                f"/{table}",
                params=[("on_conflict", ",".join(on_conflict))],
                json=list(rows),
                headers={"Prefer": "resolution=merge-duplicates,return=representation"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._raise_unavailable(error)
        if response.status_code == 409:
            raise UpsertConflictError
        if response.status_code >= 400:
            self._raise_unavailable()
        return self._decode_rows(response)


class ReadOnlyKnowledgeSupabaseClient(_SupabaseRestClient):
    """GET-only client; mutation methods are intentionally absent."""


def _build_http_client(
    settings: SupabaseConnectionSettings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    if not settings.configured or settings.url is None or settings.service_role_key is None:
        raise PlaceholderCredentialsError
    service_role_key = settings.service_role_key.get_secret_value()
    return httpx.AsyncClient(
        base_url=f"{settings.url}/rest/v1",
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Accept": "application/json",
        },
        timeout=httpx.Timeout(10.0, connect=5.0),
        transport=transport,
    )


def create_reporting_supabase_client(
    settings: SupabaseConnectionSettings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ReportingSupabaseClient:
    return ReportingSupabaseClient(
        http_client=_build_http_client(settings, transport=transport),
        allowed_tables=REPORTING_TABLES,
        component="reporting",
    )


def create_knowledge_supabase_client(
    settings: SupabaseConnectionSettings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ReadOnlyKnowledgeSupabaseClient:
    return ReadOnlyKnowledgeSupabaseClient(
        http_client=_build_http_client(settings, transport=transport),
        allowed_tables=KNOWLEDGE_SOURCE_TABLES,
        component="knowledge",
    )
