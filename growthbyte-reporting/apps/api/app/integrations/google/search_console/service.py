"""OAuth, exact-property verification, and monthly GSC synchronization."""

import hashlib
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from uuid import UUID

from app.core.errors import SafeApplicationError
from app.integrations.google.oauth import refresh_access_token
from app.integrations.google.search_console.client import GoogleSearchConsoleClient
from app.integrations.google.search_console.models import SearchConsoleSyncResult
from app.integrations.google.search_console.repository import (
    SearchConsoleConnectionRequiredError,
    SearchConsoleRepository,
)

logger = logging.getLogger(__name__)

REQUIRED_GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
APPROVED_PERMISSION_LEVELS = frozenset({"siteOwner", "siteFullUser", "siteRestrictedUser"})


class SearchConsoleScopeRequiredError(SafeApplicationError):
    code = "gsc_reconnect_required"
    safe_message = "Reconnect Google to grant read-only Search Console access"
    status_code = 409


class SearchConsolePropertyMismatchError(SafeApplicationError):
    code = "gsc_property_mismatch"
    safe_message = "The configured SuperK Search Console property was not verified"
    status_code = 422


class SearchConsoleService:
    def __init__(
        self,
        *,
        repository: SearchConsoleRepository,
        settings: object,
        client_factory: Callable[[str], GoogleSearchConsoleClient] | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._client_factory = client_factory or (
            lambda token: GoogleSearchConsoleClient(access_token=token)
        )

    async def get_status(
        self,
        *,
        client_id: UUID,
        vertical: str,
        expected_site_url: str | None,
    ) -> dict[str, object]:
        connection = await self._repository.get_google_connection(client_id=client_id)
        if connection is None:
            return {
                "configured": expected_site_url is not None,
                "connected": False,
                "scope_valid": False,
                "property_verified": False,
                "status": "connection_required",
            }
        credentials = await self._repository.get_credentials(
            client_id=client_id,
            connection_id=UUID(str(connection["id"])),
        )
        scopes = set(credentials.get("granted_scopes", ())) if credentials else set()
        scope_valid = REQUIRED_GSC_SCOPE in scopes
        configured_property = await self._repository.get_property(
            client_id=client_id,
            vertical=vertical,
        )
        property_verified = bool(
            configured_property
            and expected_site_url
            and configured_property.get("site_url") == expected_site_url
            and configured_property.get("connection_status") == "verified"
        )
        if not credentials:
            status = "connection_required"
        elif not scope_valid:
            status = "reconnect_required"
        elif not property_verified:
            status = "property_verification_required"
        else:
            status = "ready"
        return {
            "configured": expected_site_url is not None,
            "connected": credentials is not None,
            "scope_valid": scope_valid,
            "property_verified": property_verified,
            "status": status,
        }

    async def ensure_configured_property(
        self,
        *,
        client_id: UUID,
        vertical: str,
        expected_site_url: str,
    ) -> dict[str, object]:
        connection, access_token = await self._get_access_token(client_id=client_id)
        client = self._client_factory(access_token)
        try:
            properties = await client.list_sites()
        finally:
            await client.close()
        match = next(
            (item for item in properties if item.site_url == expected_site_url),
            None,
        )
        if match is None or match.permission_level not in APPROVED_PERMISSION_LEVELS:
            raise SearchConsolePropertyMismatchError
        return await self._repository.save_property(
            client_id=client_id,
            vertical=vertical,
            connection_id=UUID(str(connection["id"])),
            site_url=match.site_url,
            permission_level=match.permission_level,
        )

    async def sync_period(
        self,
        *,
        client_id: UUID,
        vertical: str,
        expected_site_url: str,
        period_start: date,
        period_end: date,
    ) -> SearchConsoleSyncResult:
        property_row = await self.ensure_configured_property(
            client_id=client_id,
            vertical=vertical,
            expected_site_url=expected_site_url,
        )
        connection, access_token = await self._get_access_token(client_id=client_id)
        sync_run = await self._repository.create_sync_run(
            client_id=client_id,
            vertical=vertical,
            connection_id=UUID(str(connection["id"])),
            site_url=expected_site_url,
            period_start=period_start,
            period_end=period_end,
        )
        sync_run_id = UUID(str(sync_run["id"]))
        client = self._client_factory(access_token)
        try:
            totals = await client.query_search_analytics(
                site_url=expected_site_url,
                period_start=period_start,
                period_end=period_end,
            )
            queries = await client.query_search_analytics(
                site_url=expected_site_url,
                period_start=period_start,
                period_end=period_end,
                dimensions=("query",),
                row_limit=250,
            )
            pages = await client.query_search_analytics(
                site_url=expected_site_url,
                period_start=period_start,
                period_end=period_end,
                dimensions=("page",),
                row_limit=250,
            )
            property_id = UUID(str(property_row["id"]))
            totals_written, totals_hash = await self._repository.save_period_totals(
                client_id=client_id,
                vertical=vertical,
                property_id=property_id,
                sync_run_id=sync_run_id,
                period_start=period_start,
                period_end=period_end,
                result=totals,
            )
            query_count, query_hashes = await self._repository.save_dimension_metrics(
                client_id=client_id,
                vertical=vertical,
                property_id=property_id,
                sync_run_id=sync_run_id,
                period_start=period_start,
                period_end=period_end,
                dimension_type="query",
                result=queries,
            )
            page_count, page_hashes = await self._repository.save_dimension_metrics(
                client_id=client_id,
                vertical=vertical,
                property_id=property_id,
                sync_run_id=sync_run_id,
                period_start=period_start,
                period_end=period_end,
                dimension_type="page",
                result=pages,
            )
            warnings: list[str] = []
            if not totals.rows:
                warnings.append("gsc_totals_unavailable")
            if not queries.rows:
                warnings.append("gsc_queries_unavailable")
            if not pages.rows:
                warnings.append("gsc_pages_unavailable")
            combined_hash = hashlib.sha256(
                "|".join(
                    item
                    for item in (totals_hash, *sorted(query_hashes), *sorted(page_hashes))
                    if item
                ).encode("utf-8")
            ).hexdigest()
            rows_read = len(totals.rows) + len(queries.rows) + len(pages.rows)
            rows_written = totals_written + query_count + page_count
            await self._repository.complete_sync_run(
                client_id=client_id,
                sync_run_id=sync_run_id,
                status="succeeded" if totals.rows else "partial",
                rows_read=rows_read,
                rows_written=rows_written,
                source_hash=combined_hash,
                warnings=tuple(warnings),
            )
            return SearchConsoleSyncResult(
                sync_run_id=str(sync_run_id),
                client_id=str(client_id),
                site_url=expected_site_url,
                period_start=period_start,
                period_end=period_end,
                status="succeeded" if totals.rows else "partial",
                totals_written=totals_written,
                query_rows_written=query_count,
                page_rows_written=page_count,
                warnings=tuple(warnings),
            )
        except Exception:
            logger.error(
                "GSC sync failed safely",
                extra={"client_id": str(client_id), "sync_run_id": str(sync_run_id)},
            )
            await self._repository.complete_sync_run(
                client_id=client_id,
                sync_run_id=sync_run_id,
                status="failed",
                error_summary="Google Search Console sync failed safely",
            )
            raise
        finally:
            await client.close()

    async def _get_access_token(self, *, client_id: UUID) -> tuple[dict[str, object], str]:
        connection = await self._repository.get_google_connection(client_id=client_id)
        if connection is None:
            raise SearchConsoleConnectionRequiredError
        connection_id = UUID(str(connection["id"]))
        credentials = await self._repository.get_credentials(
            client_id=client_id,
            connection_id=connection_id,
        )
        if credentials is None:
            raise SearchConsoleConnectionRequiredError
        granted_scopes = tuple(credentials.get("granted_scopes") or ())
        if REQUIRED_GSC_SCOPE not in granted_scopes:
            raise SearchConsoleScopeRequiredError
        if credentials["expires_at"] <= datetime.now(UTC):
            refresh_token = credentials.get("refresh_token")
            if refresh_token is None:
                raise SearchConsoleConnectionRequiredError
            refreshed = await refresh_access_token(
                refresh_token=refresh_token,
                settings=self._settings,
            )
            refreshed_scopes = tuple(refreshed.scope.split()) if refreshed.scope else granted_scopes
            if REQUIRED_GSC_SCOPE not in refreshed_scopes:
                raise SearchConsoleScopeRequiredError
            await self._repository.update_access_token(
                client_id=client_id,
                connection_id=connection_id,
                access_token=refreshed.access_token,
                expires_at=refreshed.expires_at,
                granted_scopes=refreshed_scopes,
            )
            return connection, refreshed.access_token.get_secret_value()
        return connection, credentials["access_token"].get_secret_value()
