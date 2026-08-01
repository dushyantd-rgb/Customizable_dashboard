"""Repository for Google Sheets data persistence."""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import SecretStr

from app.core.encryption import decrypt_token, encrypt_token
from app.data.supabase import ReportingSupabaseClientProtocol
from app.integrations.google.models import (
    ColumnMapping,
    GoogleSheetConfig,
    SheetRow,
    StatusMapping,
)

logger = logging.getLogger(__name__)


class GoogleSheetsRepository:
    """Repository for Google Sheets configuration and data persistence."""

    def __init__(
        self,
        client: ReportingSupabaseClientProtocol,
        encryption_key: SecretStr,
    ) -> None:
        """Initialize the repository.

        Args:
            client: Supabase client for data persistence.
            encryption_key: Key for token encryption (from settings).
        """
        self._client = client
        self._encryption_key = encryption_key

    async def client_exists(self, *, client_id: UUID) -> bool:
        """Check if a client exists.

        Args:
            client_id: The client UUID.

        Returns:
            True if client exists.
        """
        rows = await self._client.select(
            table="clients",
            columns=("id",),
            filters={"id": str(client_id)},
            limit=1,
        )
        return bool(rows)

    async def store_encrypted_token(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
        encrypted_access_token: str,
        encrypted_refresh_token: str | None,
        expires_at: datetime,
    ) -> dict[str, Any]:
        """Store encrypted OAuth tokens for a connection.

        Args:
            client_id: The client UUID.
            connection_id: The integration connection UUID.
            encrypted_access_token: Encrypted access token.
            encrypted_refresh_token: Encrypted refresh token.
            expires_at: Token expiration timestamp.

        Returns:
            Stored token record.
        """
        # Upsert token storage
        rows = await self._client.upsert(
            table="google_oauth_tokens",
            rows=[
                {
                    "client_id": str(client_id),
                    "connection_id": str(connection_id),
                    "encrypted_access_token": encrypted_access_token,
                    "encrypted_refresh_token": encrypted_refresh_token,
                    "expires_at": expires_at.isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }
            ],
            on_conflict=["client_id", "connection_id"],
        )
        return rows[0] if rows else {}

    async def get_decrypted_token(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
    ) -> dict[str, Any] | None:
        """Get and decrypt OAuth tokens for a connection.

        Args:
            client_id: The client UUID.
            connection_id: The integration connection UUID.

        Returns:
            Dict with decrypted access_token, refresh_token, and expires_at,
            or None if not found.
        """
        rows = await self._client.select(
            table="google_oauth_tokens",
            columns=(
                "id",
                "encrypted_access_token",
                "encrypted_refresh_token",
                "expires_at",
                "updated_at",
            ),
            filters={
                "client_id": str(client_id),
                "connection_id": str(connection_id),
            },
            limit=1,
        )

        if not rows:
            return None

        row = rows[0]

        # Decrypt tokens
        try:
            access_token = decrypt_token(
                row["encrypted_access_token"],
                self._encryption_key,
            )
            refresh_token = None
            if row.get("encrypted_refresh_token"):
                refresh_token = decrypt_token(
                    row["encrypted_refresh_token"],
                    self._encryption_key,
                )

            return {
                "id": row["id"],
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": row["expires_at"],
            }
        except Exception as error:
            logger.error(
                "Failed to decrypt Google OAuth token",
                extra={"client_id": str(client_id), "error_type": type(error).__name__},
            )
            raise

    async def update_encrypted_token(
        self,
        *,
        client_id: UUID,
        connection_id: UUID,
        encrypted_access_token: str,
        expires_at: datetime,
    ) -> dict[str, Any]:
        """Update encrypted access token after refresh.

        Args:
            client_id: The client UUID.
            connection_id: The integration connection UUID.
            encrypted_access_token: New encrypted access token.
            expires_at: New expiration timestamp.

        Returns:
            Updated token record.
        """
        rows = await self._client.update(
            table="google_oauth_tokens",
            values={
                "encrypted_access_token": encrypted_access_token,
                "expires_at": expires_at.isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            },
            filters={
                "client_id": str(client_id),
                "connection_id": str(connection_id),
            },
        )
        return rows[0] if rows else {}

    async def save_sheet_config(
        self,
        *,
        client_id: UUID,
        config: GoogleSheetConfig,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Save Google Sheet configuration.

        Args:
            client_id: The client UUID.
            config: Sheet configuration.
            connection_id: The integration connection UUID.

        Returns:
            Saved configuration record with ID.
        """
        rows = await self._client.upsert(
            table="google_sheet_configs",
            rows=[
                {
                    "client_id": str(client_id),
                    "connection_id": str(connection_id),
                    "spreadsheet_id": config.spreadsheet_id,
                    "worksheet_name": config.worksheet_name,
                    "header_row": config.header_row,
                    "data_start_row": config.data_start_row,
                    "status": "active",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }
            ],
            on_conflict=["client_id", "spreadsheet_id", "worksheet_name"],
        )
        return rows[0] if rows else {}

    async def get_sheet_config(
        self,
        *,
        client_id: UUID,
        config_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        """Get Google Sheet configuration.

        Args:
            client_id: The client UUID.
            config_id: Optional specific config ID. If None, gets the active config.

        Returns:
            Configuration record or None.
        """
        filters: dict[str, str] = {"client_id": str(client_id)}
        if config_id:
            filters["id"] = str(config_id)
        else:
            filters["status"] = "active"

        rows = await self._client.select(
            table="google_sheet_configs",
            columns=(
                "id",
                "client_id",
                "connection_id",
                "spreadsheet_id",
                "worksheet_name",
                "header_row",
                "data_start_row",
                "status",
                "created_at",
                "updated_at",
            ),
            filters=filters,
            limit=1,
        )
        return rows[0] if rows else None

    async def save_column_mappings(
        self,
        *,
        client_id: UUID,
        config_id: UUID,
        mappings: list[ColumnMapping],
    ) -> list[dict[str, Any]]:
        """Save column mappings for a sheet configuration.

        Args:
            client_id: The client UUID.
            config_id: The sheet configuration UUID.
            mappings: List of column mappings.

        Returns:
            Saved mapping records.
        """
        if not mappings:
            return []

        rows = await self._client.upsert(
            table="google_column_mappings",
            rows=[
                {
                    "client_id": str(client_id),
                    "config_id": str(config_id),
                    "source_header": mapping.source_header,
                    "canonical_field": mapping.canonical_field,
                    "required": mapping.required,
                    "updated_at": datetime.utcnow().isoformat(),
                }
                for mapping in mappings
            ],
            on_conflict=["config_id", "source_header"],
        )
        return rows

    async def save_status_mappings(
        self,
        *,
        client_id: UUID,
        config_id: UUID,
        mappings: list[StatusMapping],
    ) -> list[dict[str, Any]]:
        """Save status mappings for a sheet configuration.

        Args:
            client_id: The client UUID.
            config_id: The sheet configuration UUID.
            mappings: List of status mappings.

        Returns:
            Saved mapping records.
        """
        if not mappings:
            return []

        rows = await self._client.upsert(
            table="google_status_mappings",
            rows=[
                {
                    "client_id": str(client_id),
                    "config_id": str(config_id),
                    "source_value": mapping.source_value,
                    "canonical_status": mapping.canonical_status,
                    "counts_as_reviewed": mapping.counts_as_reviewed,
                    "updated_at": datetime.utcnow().isoformat(),
                }
                for mapping in mappings
            ],
            on_conflict=["config_id", "source_value"],
        )
        return rows

    async def get_mappings(
        self,
        *,
        client_id: UUID,
        config_id: UUID,
    ) -> dict[str, Any]:
        """Get all mappings for a configuration.

        Args:
            client_id: The client UUID.
            config_id: The sheet configuration UUID.

        Returns:
            Dict with "column_mappings" and "status_mappings" lists.
        """
        # Get column mappings
        column_rows = await self._client.select(
            table="google_column_mappings",
            columns=(
                "id",
                "config_id",
                "source_header",
                "canonical_field",
                "required",
            ),
            filters={"config_id": str(config_id)},
            limit=100,
        )

        # Get status mappings
        status_rows = await self._client.select(
            table="google_status_mappings",
            columns=(
                "id",
                "config_id",
                "source_value",
                "canonical_status",
                "counts_as_reviewed",
            ),
            filters={"config_id": str(config_id)},
            limit=100,
        )

        return {
            "column_mappings": column_rows,
            "status_mappings": status_rows,
        }

    async def get_connection(
        self,
        *,
        client_id: UUID,
        provider: str = "google_sheets",
    ) -> dict[str, Any] | None:
        """Get an integration connection for a client.

        Args:
            client_id: The client UUID.
            provider: Provider name.

        Returns:
            Connection record or None.
        """
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
                "created_at",
                "updated_at",
            ),
            filters={"client_id": str(client_id), "provider": provider},
            limit=1,
        )
        return rows[0] if rows else None

    async def upsert_connection(
        self,
        *,
        client_id: UUID,
        source_identifier: str,
        display_name: str | None,
    ) -> dict[str, Any]:
        """Create or update an integration connection.

        Args:
            client_id: The client UUID.
            source_identifier: Source identifier (e.g., Google user ID).
            display_name: Display name for the connection.

        Returns:
            Connection record.
        """
        rows = await self._client.upsert(
            table="integration_connections",
            rows=[
                {
                    "client_id": str(client_id),
                    "provider": "google_sheets",
                    "source_identifier": source_identifier,
                    "display_name": display_name,
                    "status": "active",
                    "last_connected_at": datetime.utcnow().isoformat(),
                }
            ],
            on_conflict=["client_id", "provider"],
        )
        return rows[0]

    async def create_sync_run(
        self,
        *,
        client_id: UUID,
        integration_connection_id: UUID,
        config_id: UUID,
        watermark_from: datetime | None = None,
        watermark_to: datetime | None = None,
        initiated_by: str | None = None,
    ) -> dict[str, Any]:
        """Create a new sync run record.

        Args:
            client_id: The client UUID.
            integration_connection_id: Connection UUID.
            config_id: Sheet configuration UUID.
            watermark_from: Optional start timestamp.
            watermark_to: Optional end timestamp.
            initiated_by: Who initiated the sync.

        Returns:
            Sync run record with ID.
        """
        row = {
            "client_id": str(client_id),
            "integration_connection_id": str(integration_connection_id),
            "config_id": str(config_id),
            "source_type": "google_sheets",
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "watermark_from": watermark_from.isoformat() if watermark_from else None,
            "watermark_to": watermark_to.isoformat() if watermark_to else None,
            "initiated_by_label": initiated_by,
        }
        inserted = await self._client.insert(table="google_sync_runs", row=row)
        return inserted

    async def save_raw_rows(
        self,
        *,
        client_id: UUID,
        config_id: UUID,
        sync_run_id: UUID,
        rows: list[SheetRow],
    ) -> list[dict[str, Any]]:
        """Save raw rows from Google Sheets with idempotency.

        Each row is hashed for deduplication. Existing rows are skipped.

        Args:
            client_id: The client UUID.
            config_id: The sheet configuration UUID.
            sync_run_id: The sync run UUID.
            rows: List of sheet rows.

        Returns:
            Saved row records.
        """
        if not rows:
            return []

        rows_to_insert = []
        for row in rows:
            # Create deterministic hash for idempotency
            row_hash = hashlib.sha256(
                f"{client_id}|{config_id}|{row.row_number}".encode()
            ).hexdigest()

            rows_to_insert.append(
                {
                    "client_id": str(client_id),
                    "config_id": str(config_id),
                    "sync_run_id": str(sync_run_id),
                    "row_number": row.row_number,
                    "row_hash": row_hash,
                    "raw_values": json.dumps(row.values),
                    "created_at": datetime.utcnow().isoformat(),
                }
            )

        rows_inserted = await self._client.upsert(
            table="google_raw_rows",
            rows=rows_to_insert,
            on_conflict=["config_id", "row_number"],
        )
        return rows_inserted

    async def complete_sync_run(
        self,
        *,
        client_id: UUID,
        sync_run_id: UUID,
        status: str,
        rows_read: int = 0,
        rows_written: int = 0,
        rows_skipped: int = 0,
        error_summary: str | None = None,
    ) -> dict[str, Any]:
        """Mark a sync run as complete.

        Args:
            client_id: The client UUID.
            sync_run_id: The sync run UUID.
            status: Final status ("succeeded", "failed", "cancelled").
            rows_read: Number of rows read.
            rows_written: Number of rows written.
            rows_skipped: Number of rows skipped (duplicates).
            error_summary: Optional error summary.

        Returns:
            Updated sync run record.
        """
        rows = await self._client.update(
            table="google_sync_runs",
            values={
                "status": status,
                "finished_at": datetime.utcnow().isoformat(),
                "rows_read": rows_read,
                "rows_written": rows_written,
                "rows_skipped": rows_skipped,
                "error_summary": error_summary,
            },
            filters={"client_id": str(client_id), "id": str(sync_run_id)},
        )
        return rows[0] if rows else {}

    async def get_sync_runs(
        self,
        *,
        client_id: UUID,
        config_id: UUID | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get recent sync runs for a client.

        Args:
            client_id: The client UUID.
            config_id: Optional specific config ID.
            limit: Maximum number of runs to return.

        Returns:
            List of sync run records.
        """
        filters: dict[str, str] = {"client_id": str(client_id)}
        if config_id:
            filters["config_id"] = str(config_id)

        rows = await self._client.select(
            table="google_sync_runs",
            columns=(
                "id",
                "client_id",
                "config_id",
                "source_type",
                "status",
                "started_at",
                "finished_at",
                "rows_read",
                "rows_written",
                "rows_skipped",
                "error_summary",
                "created_at",
            ),
            filters=filters,
            limit=limit,
        )
        return rows
