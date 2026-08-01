"""Read-only HTTP client for Google Search Console."""

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

import httpx

from app.core.errors import SafeApplicationError
from app.integrations.google.search_console.models import (
    SearchConsoleMetricRow,
    SearchConsoleProperty,
    SearchConsoleQueryResult,
)

logger = logging.getLogger(__name__)


class SearchConsoleApiError(SafeApplicationError):
    code = "gsc_api_error"
    safe_message = "The Google Search Console request failed"
    status_code = 502


class GoogleSearchConsoleClient:
    """Small GET/POST-only client for the read-only Search Console API."""

    def __init__(
        self,
        *,
        access_token: str,
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._access_token = access_token
        self._http_client = http_client
        self._timeout_seconds = timeout_seconds
        self._owned_client = False

    async def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url="https://www.googleapis.com/webmasters/v3",
                timeout=httpx.Timeout(self._timeout_seconds, connect=10.0),
            )
            self._owned_client = True
        return self._http_client

    async def close(self) -> None:
        if self._owned_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
            self._owned_client = False

    async def list_sites(self) -> tuple[SearchConsoleProperty, ...]:
        payload = await self._request("GET", "/sites")
        entries = payload.get("siteEntry", [])
        if not isinstance(entries, list):
            raise SearchConsoleApiError
        properties: list[SearchConsoleProperty] = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("siteUrl"), str):
                continue
            properties.append(
                SearchConsoleProperty(
                    site_url=entry["siteUrl"],
                    permission_level=(
                        str(entry["permissionLevel"])
                        if entry.get("permissionLevel") is not None
                        else None
                    ),
                )
            )
        return tuple(properties)

    async def query_search_analytics(
        self,
        *,
        site_url: str,
        period_start: date,
        period_end: date,
        dimensions: tuple[str, ...] = (),
        row_limit: int = 25_000,
    ) -> SearchConsoleQueryResult:
        body: dict[str, Any] = {
            "startDate": period_start.isoformat(),
            "endDate": period_end.isoformat(),
            "dataState": "final",
            "rowLimit": min(max(row_limit, 1), 25_000),
            "startRow": 0,
        }
        if dimensions:
            body["dimensions"] = list(dimensions)
        payload = await self._request(
            "POST",
            f"/sites/{quote(site_url, safe='')}/searchAnalytics/query",
            json_body=body,
        )
        raw_rows = payload.get("rows", [])
        if not isinstance(raw_rows, list):
            raise SearchConsoleApiError
        rows: list[SearchConsoleMetricRow] = []
        for raw in raw_rows:
            if not isinstance(raw, dict):
                continue
            raw_keys = raw.get("keys") or []
            rows.append(
                SearchConsoleMetricRow(
                    keys=tuple(str(key) for key in raw_keys if key is not None),
                    clicks=_decimal(raw.get("clicks")),
                    impressions=_decimal(raw.get("impressions")),
                    ctr=_decimal(raw.get("ctr")),
                    average_position=_decimal(raw.get("position")),
                )
            )
        aggregation = payload.get("responseAggregationType")
        return SearchConsoleQueryResult(
            rows=tuple(rows),
            response_aggregation_type=str(aggregation) if aggregation is not None else None,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        client = await self._client()
        try:
            response = await client.request(
                method,
                path,
                json=json_body,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Accept": "application/json",
                },
            )
        except (httpx.TimeoutException, httpx.TransportError) as error:
            logger.warning("GSC network request failed", extra={"path": path})
            raise SearchConsoleApiError from error
        if response.status_code >= 400:
            logger.warning(
                "GSC provider request failed",
                extra={"path": path, "status": response.status_code},
            )
            raise SearchConsoleApiError
        try:
            payload = response.json()
        except ValueError as error:
            raise SearchConsoleApiError from error
        if not isinstance(payload, dict) or payload.get("error") is not None:
            raise SearchConsoleApiError
        return payload


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise SearchConsoleApiError from error
