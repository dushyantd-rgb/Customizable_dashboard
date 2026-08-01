"""Client-scoped persistence for Google Search Console data."""

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from pydantic import SecretStr

from app.core.encryption import decrypt_token, encrypt_token
from app.core.errors import SafeApplicationError
from app.data.supabase import ReportingSupabaseClientProtocol
from app.integrations.google.search_console.models import SearchConsoleQueryResult


class SearchConsoleConfigurationError(SafeApplicationError):
    code = "invalid_gsc_configuration"
    safe_message = "The Google Search Console configuration is invalid"
    status_code = 422


class SearchConsoleConnectionRequiredError(SafeApplicationError):
    code = "gsc_connection_required"
    safe_message = "Connect Google with Search Console access first"
    status_code = 409


class SearchConsoleRepository:
    def __init__(
        self,
        client: ReportingSupabaseClientProtocol,
        encryption_key: SecretStr,
    ) -> None:
        self._client = client
        self._encryption_key = encryption_key

    async def get_google_connection(self, *, client_id: UUID) -> dict[str, Any] | None:
        for provider in ("google", "google_sheets"):
            rows = await self._client.select(
                table="integration_connections",
                columns=(
                    "id",
                    "client_id",
                    "provider",
                    "source_identifier",
                    "display_name",
                    "status",
                ),
                filters={"client_id": str(client_id), "provider": provider},
                limit=1,
            )
            if rows:
                return rows[0]
        return None

    async def get_credentials(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
    ) -> dict[str, Any] | None:
        rows = await self._client.select(
            table="google_oauth_credentials",
            columns=(
                "access_ciphertext",
                "refresh_ciphertext",
                "expires_at",
                "granted_scopes",
            ),
            filters={
                "client_id": str(client_id),
                "integration_connection_id": str(connection_id),
            },
            limit=1,
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "access_token": SecretStr(
                decrypt_token(str(row["access_ciphertext"]), self._encryption_key)
            ),
            "refresh_token": (
                SecretStr(decrypt_token(str(row["refresh_ciphertext"]), self._encryption_key))
                if row.get("refresh_ciphertext")
                else None
            ),
            "expires_at": _as_datetime(row["expires_at"]),
            "granted_scopes": tuple(str(item) for item in row.get("granted_scopes") or []),
        }

    async def update_access_token(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
        access_token: SecretStr,
        expires_at: datetime,
        granted_scopes: tuple[str, ...] | None = None,
    ) -> None:
        values: dict[str, Any] = {
            "access_ciphertext": encrypt_token(
                access_token.get_secret_value(), self._encryption_key
            ),
            "expires_at": expires_at.isoformat(),
        }
        if granted_scopes is not None:
            values["granted_scopes"] = sorted(set(granted_scopes))
        rows = await self._client.update(
            table="google_oauth_credentials",
            values=values,
            filters={
                "client_id": str(client_id),
                "integration_connection_id": str(connection_id),
            },
        )
        if len(rows) != 1:
            raise SearchConsoleConfigurationError

    async def get_property(
        self,
        *,
        client_id: UUID,
        vertical: str,
    ) -> dict[str, Any] | None:
        rows = await self._client.select(
            table="gsc_properties",
            columns=(
                "id",
                "client_id",
                "vertical",
                "integration_connection_id",
                "site_url",
                "permission_level",
                "connection_status",
                "last_verified_at",
            ),
            filters={"client_id": str(client_id), "vertical": vertical},
            limit=1,
        )
        return rows[0] if rows else None

    async def save_property(
        self,
        *,
        client_id: UUID,
        vertical: str,
        connection_id: UUID,
        site_url: str,
        permission_level: str | None,
    ) -> dict[str, Any]:
        rows = await self._client.upsert(
            table="gsc_properties",
            rows=(
                {
                    "client_id": str(client_id),
                    "vertical": vertical,
                    "integration_connection_id": str(connection_id),
                    "site_url": site_url,
                    "permission_level": permission_level,
                    "connection_status": "verified",
                    "last_verified_at": _utc_now(),
                },
            ),
            on_conflict=("client_id", "vertical"),
        )
        if len(rows) != 1:
            raise SearchConsoleConfigurationError
        return rows[0]

    async def create_sync_run(
        self,
        *,
        client_id: UUID,
        vertical: str,
        connection_id: UUID,
        site_url: str,
        period_start: date,
        period_end: date,
    ) -> dict[str, Any]:
        return await self._client.insert(
            table="sync_runs",
            row={
                "client_id": str(client_id),
                "integration_connection_id": str(connection_id),
                "source_type": "google_search_console",
                "vertical": vertical,
                "source_identifier": site_url,
                "status": "running",
                "started_at": _utc_now(),
                "watermark_from": f"{period_start.isoformat()}T00:00:00+00:00",
                "watermark_to": f"{period_end.isoformat()}T23:59:59.999999+00:00",
                "initiated_by_label": "superk_monthly_report",
            },
        )

    async def save_period_totals(
        self,
        *,
        client_id: UUID,
        vertical: str,
        property_id: UUID,
        sync_run_id: UUID,
        period_start: date,
        period_end: date,
        result: SearchConsoleQueryResult,
    ) -> tuple[int, str | None]:
        if not result.rows:
            return 0, None
        metric = result.rows[0]
        payload = {
            "keys": metric.keys,
            "clicks": metric.clicks,
            "impressions": metric.impressions,
            "ctr": metric.ctr,
            "average_position": metric.average_position,
            "aggregation": result.response_aggregation_type,
        }
        source_hash = _stable_hash(payload)
        rows = await self._client.upsert(
            table="gsc_period_totals",
            rows=(
                {
                    "client_id": str(client_id),
                    "vertical": vertical,
                    "gsc_property_id": str(property_id),
                    "sync_run_id": str(sync_run_id),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "clicks": _value(metric.clicks),
                    "impressions": _value(metric.impressions),
                    "ctr": _value(metric.ctr),
                    "average_position": _value(metric.average_position),
                    "response_aggregation_type": result.response_aggregation_type,
                    "data_state": "final",
                    "source_hash": source_hash,
                    "synced_at": _utc_now(),
                },
            ),
            on_conflict=(
                "client_id",
                "vertical",
                "gsc_property_id",
                "period_start",
                "period_end",
                "source_hash",
            ),
        )
        return len(rows), source_hash

    async def save_dimension_metrics(
        self,
        *,
        client_id: UUID,
        vertical: str,
        property_id: UUID,
        sync_run_id: UUID,
        period_start: date,
        period_end: date,
        dimension_type: str,
        result: SearchConsoleQueryResult,
    ) -> tuple[int, tuple[str, ...]]:
        rows_to_store: list[dict[str, Any]] = []
        hashes: list[str] = []
        for metric in result.rows:
            if not metric.keys or not metric.keys[0].strip():
                continue
            dimension_value = metric.keys[0].strip()
            source_hash = _stable_hash(
                {
                    "dimension_type": dimension_type,
                    "dimension_value": dimension_value,
                    "clicks": metric.clicks,
                    "impressions": metric.impressions,
                    "ctr": metric.ctr,
                    "average_position": metric.average_position,
                }
            )
            hashes.append(source_hash)
            rows_to_store.append(
                {
                    "client_id": str(client_id),
                    "vertical": vertical,
                    "gsc_property_id": str(property_id),
                    "sync_run_id": str(sync_run_id),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "dimension_type": dimension_type,
                    "dimension_value": dimension_value,
                    "clicks": _value(metric.clicks),
                    "impressions": _value(metric.impressions),
                    "ctr": _value(metric.ctr),
                    "average_position": _value(metric.average_position),
                    "source_hash": source_hash,
                    "synced_at": _utc_now(),
                }
            )
        if not rows_to_store:
            return 0, ()
        rows = await self._client.upsert(
            table="gsc_dimension_metrics",
            rows=rows_to_store,
            on_conflict=(
                "client_id",
                "vertical",
                "gsc_property_id",
                "period_start",
                "period_end",
                "dimension_type",
                "dimension_value",
                "source_hash",
            ),
        )
        return len(rows), tuple(hashes)

    async def get_period_totals(
        self,
        *,
        client_id: UUID,
        vertical: str,
        period_start: date,
        period_end: date,
    ) -> dict[str, Any] | None:
        """Return the newest separately queried total for an exact client period."""

        rows = await self._client.select(
            table="gsc_period_totals",
            columns=(
                "id",
                "client_id",
                "vertical",
                "gsc_property_id",
                "sync_run_id",
                "period_start",
                "period_end",
                "clicks",
                "impressions",
                "ctr",
                "average_position",
                "source_hash",
                "synced_at",
            ),
            filters={
                "client_id": str(client_id),
                "vertical": vertical,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
            limit=1000,
        )
        if not rows:
            return None
        return max(rows, key=lambda row: str(row.get("synced_at") or ""))

    async def list_dimension_metrics(
        self,
        *,
        client_id: UUID,
        vertical: str,
        period_start: date,
        period_end: date,
        dimension_type: str,
    ) -> list[dict[str, Any]]:
        """Read exact-period query or page rows for report context."""

        return await self._client.select(
            table="gsc_dimension_metrics",
            columns=(
                "id",
                "dimension_type",
                "dimension_value",
                "clicks",
                "impressions",
                "ctr",
                "average_position",
                "source_hash",
                "synced_at",
            ),
            filters={
                "client_id": str(client_id),
                "vertical": vertical,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "dimension_type": dimension_type,
            },
            limit=1000,
        )

    async def complete_sync_run(
        self,
        *,
        client_id: UUID,
        sync_run_id: UUID,
        status: str,
        rows_read: int = 0,
        rows_written: int = 0,
        source_hash: str | None = None,
        warnings: tuple[str, ...] = (),
        error_summary: str | None = None,
    ) -> None:
        rows = await self._client.update(
            table="sync_runs",
            values={
                "status": status,
                "finished_at": _utc_now(),
                "rows_read": rows_read,
                "rows_written": rows_written,
                "rows_rejected": len(warnings),
                "source_hash": source_hash,
                "warnings": list(warnings),
                "error_summary": error_summary,
            },
            filters={"client_id": str(client_id), "id": str(sync_run_id)},
        )
        if len(rows) != 1:
            raise SearchConsoleConfigurationError


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _as_datetime(value: Any) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _value(value: Any) -> str | None:
    return str(value) if value is not None else None


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
