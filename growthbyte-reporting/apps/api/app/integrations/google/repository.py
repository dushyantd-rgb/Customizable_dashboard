"""Client-scoped persistence for the Google Sheets prototype."""

import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import SecretStr

from app.core.encryption import decrypt_token, encrypt_token
from app.core.errors import ReportingWriteConflictError, SafeApplicationError
from app.data.supabase import ReportingSupabaseClientProtocol
from app.integrations.google.models import ColumnMapping, GoogleSheetConfig, SheetRow, StatusMapping


class GoogleConfigurationError(SafeApplicationError):
    code = "invalid_google_sheet_configuration"
    safe_message = "The Google Sheet configuration is invalid"
    status_code = 422


class GoogleConnectionRequiredError(SafeApplicationError):
    code = "google_connection_required"
    safe_message = "Connect Google Sheets for this client first"
    status_code = 409


class GoogleSheetsRepository:
    def __init__(
        self,
        client: ReportingSupabaseClientProtocol,
        encryption_key: SecretStr,
    ) -> None:
        self._client = client
        self._encryption_key = encryption_key

    async def client_exists(self, *, client_id: UUID) -> bool:
        rows = await self._client.select(
            table="clients",
            columns=("id",),
            filters={"id": str(client_id)},
            limit=1,
        )
        return bool(rows)

    async def get_connection(self, *, client_id: UUID) -> dict[str, Any] | None:
        rows = await self._client.select(
            table="integration_connections",
            columns=(
                "id",
                "client_id",
                "provider",
                "source_identifier",
                "display_name",
                "status",
                "last_connected_at",
            ),
            filters={"client_id": str(client_id), "provider": "google_sheets"},
            limit=1,
        )
        return rows[0] if rows else None

    async def upsert_connection(self, *, client_id: UUID) -> dict[str, Any]:
        rows = await self._client.upsert(
            table="integration_connections",
            rows=(
                {
                    "client_id": str(client_id),
                    "provider": "google_sheets",
                    "source_identifier": "google_oauth",
                    "display_name": "Google Sheets",
                    "status": "active",
                    "last_connected_at": _utc_now(),
                },
            ),
            on_conflict=("client_id", "provider", "source_identifier"),
        )
        if len(rows) != 1:
            raise GoogleConfigurationError
        return rows[0]

    async def store_tokens(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
        access_token: SecretStr,
        refresh_token: SecretStr | None,
        expires_at: datetime,
    ) -> None:
        access_ciphertext = encrypt_token(access_token.get_secret_value(), self._encryption_key)
        refresh_ciphertext = (
            encrypt_token(refresh_token.get_secret_value(), self._encryption_key)
            if refresh_token is not None
            else None
        )
        rows = await self._client.upsert(
            table="google_oauth_credentials",
            rows=(
                {
                    "client_id": str(client_id),
                    "integration_connection_id": str(connection_id),
                    "access_ciphertext": access_ciphertext,
                    "refresh_ciphertext": refresh_ciphertext,
                    "expires_at": expires_at.isoformat(),
                },
            ),
            on_conflict=("client_id",),
        )
        if len(rows) != 1:
            raise GoogleConfigurationError

    async def get_tokens(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
    ) -> dict[str, Any] | None:
        rows = await self._client.select(
            table="google_oauth_credentials",
            columns=("access_ciphertext", "refresh_ciphertext", "expires_at"),
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
        }

    async def update_access_token(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
        access_token: SecretStr,
        expires_at: datetime,
    ) -> None:
        rows = await self._client.update(
            table="google_oauth_credentials",
            values={
                "access_ciphertext": encrypt_token(
                    access_token.get_secret_value(), self._encryption_key
                ),
                "expires_at": expires_at.isoformat(),
            },
            filters={
                "client_id": str(client_id),
                "integration_connection_id": str(connection_id),
            },
        )
        if len(rows) != 1:
            raise GoogleConfigurationError

    async def save_sheet_config(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
        config: GoogleSheetConfig,
    ) -> dict[str, Any]:
        existing = await self.get_sheet_config(client_id=client_id)
        values = {
            "integration_connection_id": str(connection_id),
            "spreadsheet_id": config.spreadsheet_id,
            "worksheet_name": config.worksheet_name,
            "header_row": config.header_row,
            "data_start_row": config.data_start_row,
            "source_timezone": config.source_timezone,
            "status": "active",
        }
        if existing is not None:
            values["mapping_version"] = int(existing["mapping_version"]) + 1
            rows = await self._client.update(
                table="google_sheet_configs",
                values=values,
                filters={"client_id": str(client_id), "id": str(existing["id"])},
            )
            if len(rows) != 1:
                raise GoogleConfigurationError
            return rows[0]

        inserted = await self._client.insert(
            table="google_sheet_configs",
            row={"client_id": str(client_id), "mapping_version": 1, **values},
        )
        return inserted

    async def get_sheet_config(
        self,
        *,
        client_id: UUID,
        config_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        filters = {"client_id": str(client_id)}
        if config_id is None:
            filters["status"] = "active"
        else:
            filters["id"] = str(config_id)
        rows = await self._client.select(
            table="google_sheet_configs",
            columns=(
                "id",
                "client_id",
                "integration_connection_id",
                "spreadsheet_id",
                "worksheet_name",
                "header_row",
                "data_start_row",
                "source_timezone",
                "status",
                "mapping_version",
            ),
            filters=filters,
            limit=2,
        )
        if len(rows) > 1:
            raise GoogleConfigurationError
        return rows[0] if rows else None

    async def save_column_mappings(
        self,
        *,
        client_id: UUID,
        config_id: UUID,
        mappings: list[ColumnMapping],
    ) -> int:
        config = await self._require_config(client_id=client_id, config_id=config_id)
        if not mappings:
            raise GoogleConfigurationError
        version = int(config["mapping_version"])
        rows = await self._client.upsert(
            table="field_mappings",
            rows=tuple(
                {
                    "client_id": str(client_id),
                    "google_sheet_config_id": str(config_id),
                    "source_header": mapping.source_header,
                    "canonical_field": mapping.canonical_field,
                    "transform": {},
                    "required": mapping.required,
                    "version": version,
                }
                for mapping in mappings
            ),
            on_conflict=(
                "client_id",
                "google_sheet_config_id",
                "source_header",
                "version",
            ),
        )
        return len(rows)

    async def save_status_mappings(
        self,
        *,
        client_id: UUID,
        config_id: UUID,
        mappings: list[StatusMapping],
    ) -> int:
        config = await self._require_config(client_id=client_id, config_id=config_id)
        if not mappings:
            return 0
        version = int(config["mapping_version"])
        rows = await self._client.upsert(
            table="status_mappings",
            rows=tuple(
                {
                    "client_id": str(client_id),
                    "google_sheet_config_id": str(config_id),
                    "source_value_normalized": _normalize_status(mapping.source_value),
                    "canonical_status": mapping.canonical_status,
                    "counts_as_reviewed": mapping.counts_as_reviewed,
                    "mapping_version": version,
                }
                for mapping in mappings
            ),
            on_conflict=(
                "client_id",
                "google_sheet_config_id",
                "source_value_normalized",
                "mapping_version",
            ),
        )
        return len(rows)

    async def get_mappings(
        self,
        *,
        client_id: UUID,
        config_id: UUID,
        mapping_version: int,
    ) -> dict[str, list[dict[str, Any]]]:
        client_filter = {
            "client_id": str(client_id),
            "google_sheet_config_id": str(config_id),
        }
        column_rows = await self._client.select(
            table="field_mappings",
            columns=("source_header", "canonical_field", "required", "version"),
            filters={**client_filter, "version": str(mapping_version)},
            limit=200,
        )
        status_rows = await self._client.select(
            table="status_mappings",
            columns=(
                "source_value_normalized",
                "canonical_status",
                "counts_as_reviewed",
                "mapping_version",
            ),
            filters={**client_filter, "mapping_version": str(mapping_version)},
            limit=200,
        )
        return {"column_mappings": column_rows, "status_mappings": status_rows}

    async def create_sync_run(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
        config_id: UUID,
    ) -> dict[str, Any]:
        return await self._client.insert(
            table="sync_runs",
            row={
                "client_id": str(client_id),
                "integration_connection_id": str(connection_id),
                "google_sheet_config_id": str(config_id),
                "source_type": "google_sheets",
                "status": "running",
                "started_at": _utc_now(),
                "initiated_by_label": "manual",
            },
        )

    async def save_raw_rows(
        self,
        *,
        client_id: UUID,
        config_id: UUID,
        sync_run_id: UUID,
        worksheet_name: str,
        rows: list[SheetRow],
    ) -> list[dict[str, Any]]:
        inserted: list[dict[str, Any]] = []
        for source_row in rows:
            source_row_key = hashlib.sha256(
                f"{client_id}|{config_id}|{worksheet_name}|{source_row.row_number}".encode()
            ).hexdigest()
            raw_values = list(source_row.values)
            row_hash = hashlib.sha256(
                json.dumps(
                    raw_values,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
            ).hexdigest()
            existing = await self._client.select(
                table="raw_sheet_rows",
                columns=("id",),
                filters={
                    "client_id": str(client_id),
                    "google_sheet_config_id": str(config_id),
                    "source_row_key": source_row_key,
                    "row_hash": row_hash,
                },
                limit=1,
            )
            if existing:
                continue
            try:
                stored = await self._client.insert(
                    table="raw_sheet_rows",
                    row={
                        "client_id": str(client_id),
                        "google_sheet_config_id": str(config_id),
                        "sync_run_id": str(sync_run_id),
                        "worksheet_name": worksheet_name,
                        "row_number": source_row.row_number,
                        "source_row_key": source_row_key,
                        "raw_values": raw_values,
                        "row_hash": row_hash,
                        "observed_at": _utc_now(),
                        "is_deleted_at_source": False,
                    },
                )
            except ReportingWriteConflictError:
                continue
            inserted.append(stored)
        return inserted

    async def complete_sync_run(
        self,
        *,
        client_id: UUID,
        sync_run_id: UUID,
        status: str,
        rows_read: int = 0,
        rows_written: int = 0,
        warning_count: int = 0,
        error_summary: str | None = None,
    ) -> None:
        rows = await self._client.update(
            table="sync_runs",
            values={
                "status": status,
                "finished_at": _utc_now(),
                "rows_read": rows_read,
                "rows_written": rows_written,
                "rows_rejected": warning_count,
                "error_summary": error_summary,
            },
            filters={"client_id": str(client_id), "id": str(sync_run_id)},
        )
        if len(rows) != 1:
            raise GoogleConfigurationError

    async def get_sync_runs(
        self,
        *,
        client_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return await self._client.select(
            table="sync_runs",
            columns=(
                "id",
                "client_id",
                "source_type",
                "status",
                "started_at",
                "finished_at",
                "rows_read",
                "rows_written",
                "rows_rejected",
                "error_summary",
                "created_at",
            ),
            filters={"client_id": str(client_id), "source_type": "google_sheets"},
            limit=min(max(limit, 1), 100),
        )

    async def _require_config(self, *, client_id: UUID, config_id: UUID) -> dict[str, Any]:
        config = await self.get_sheet_config(client_id=client_id, config_id=config_id)
        if config is None:
            raise GoogleConfigurationError
        return config


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _as_datetime(value: Any) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _normalize_status(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized = " ".join(normalized.split())
    if not normalized:
        raise GoogleConfigurationError
    return normalized
