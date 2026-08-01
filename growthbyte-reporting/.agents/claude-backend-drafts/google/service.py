"""Google Sheets synchronization service."""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.integrations.google.client import GoogleSheetsClient, GoogleSheetsApiError
from app.integrations.google.models import (
    ColumnMapping,
    GoogleSheetConfig,
    GoogleSyncRequest,
    GoogleSyncResult,
    SheetConfigurationResponse,
    SpreadsheetSummary,
    StatusMapping,
)
from app.integrations.google.oauth import (
    GoogleOAuthError,
    get_authorization_url,
    exchange_code_for_tokens,
    refresh_access_token,
    validate_oauth_state,
)
from app.integrations.google.repository import GoogleSheetsRepository

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Service for Google Sheets integration and synchronization."""

    def __init__(
        self,
        *,
        repository: GoogleSheetsRepository,
        settings: Any,
    ) -> None:
        """Initialize the service.

        Args:
            repository: Google Sheets repository.
            settings: Application settings.
        """
        self._repository = repository
        self._settings = settings

    async def start_oauth_flow(self, *, client_id: str) -> str:
        """Start the OAuth 2.0 authorization flow.

        Generates an authorization URL for the user to grant access.

        Args:
            client_id: The client identifier.

        Returns:
            Authorization URL to redirect the user to.

        Raises:
            GoogleOAuthError: If OAuth not configured.
        """
        if not self._settings.google.oauth_redirect_uri:
            raise GoogleOAuthError("Google OAuth redirect URI not configured")

        return get_authorization_url(
            client_id=client_id,
            redirect_uri=self._settings.google.oauth_redirect_uri,
            settings=self._settings,
        )

    async def complete_oauth_flow(
        self,
        *,
        client_id: str,
        code: str,
        state: str,
    ) -> dict[str, str]:
        """Complete the OAuth 2.0 authorization flow.

        Validates state, exchanges code for tokens, and stores them.

        Args:
            client_id: The client identifier.
            code: Authorization code from Google.
            state: State parameter from Google callback.

        Returns:
            Success dict with connection details.

        Raises:
            GoogleOAuthError: If flow fails.
        """
        # Validate state parameter
        if not self._settings.token_encryption_key:
            raise GoogleOAuthError("Token encryption key not configured")

        validated_client_id = validate_oauth_state(
            state=state,
            state_hmac_key=self._settings.token_encryption_key,
        )

        if validated_client_id != client_id:
            raise GoogleOAuthError("OAuth state client mismatch")

        # Exchange code for tokens
        if not self._settings.google.oauth_redirect_uri:
            raise GoogleOAuthError("Google OAuth redirect URI not configured")

        token_response = await exchange_code_for_tokens(
            code=code,
            redirect_uri=self._settings.google.oauth_redirect_uri,
            settings=self._settings,
        )

        # Create or update connection
        client_uuid = UUID(client_id)
        connection = await self._repository.upsert_connection(
            client_id=client_uuid,
            source_identifier="google_sheets",
            display_name="Google Sheets",
        )

        connection_id = UUID(connection["id"])

        # Store encrypted tokens
        await self._repository.store_encrypted_token(
            client_id=client_uuid,
            connection_id=connection_id,
            encrypted_access_token=token_response.access_token,
            encrypted_refresh_token=token_response.refresh_token,
            expires_at=token_response.expires_at,
        )

        return {
            "connection_id": str(connection_id),
            "status": "success",
        }

    async def discover_spreadsheets(self, *, client_id: str) -> list[SpreadsheetSummary]:
        """Discover spreadsheets accessible to the client.

        Args:
            client_id: The client identifier.

        Returns:
            List of accessible spreadsheets.

        Raises:
            ValueError: If no connection configured.
            GoogleSheetsApiError: If API request fails.
        """
        client_uuid = UUID(client_id)

        # Get connection and tokens
        connection = await self._repository.get_connection(client_id=client_uuid)
        if not connection:
            raise ValueError("No Google Sheets connection configured")

        connection_id = UUID(connection["id"])
        token_data = await self._repository.get_decrypted_token(
            client_id=client_uuid,
            connection_id=connection_id,
        )

        if not token_data:
            raise ValueError("No Google OAuth tokens found")

        # Check if token needs refresh
        access_token = token_data["access_token"]
        expires_at = datetime.fromisoformat(token_data["expires_at"])

        if expires_at <= datetime.now(timezone.utc):
            # Token expired, refresh it
            if not token_data.get("refresh_token"):
                raise ValueError("Token expired and no refresh token available")

            new_tokens = await refresh_access_token(
                refresh_token=token_data["refresh_token"],
                settings=self._settings,
            )

            await self._repository.update_encrypted_token(
                client_id=client_uuid,
                connection_id=connection_id,
                encrypted_access_token=new_tokens.access_token,
                expires_at=new_tokens.expires_at,
            )

            access_token = new_tokens.access_token

        # Create client and discover spreadsheets
        sheets_client = GoogleSheetsClient(access_token=access_token)

        try:
            spreadsheets = await sheets_client.list_spreadsheets()
            return spreadsheets
        finally:
            await sheets_client.close()

    async def get_worksheets(
        self,
        *,
        client_id: str,
        spreadsheet_id: str,
    ) -> list[dict[str, Any]]:
        """Get worksheets for a spreadsheet.

        Args:
            client_id: The client identifier.
            spreadsheet_id: Google Spreadsheet ID.

        Returns:
            List of worksheet summaries.
        """
        client_uuid = UUID(client_id)
        access_token = await self._get_access_token(client_id=client_uuid)

        sheets_client = GoogleSheetsClient(access_token=access_token)

        try:
            worksheets = await sheets_client.get_worksheets(spreadsheet_id=spreadsheet_id)
            return [
                {
                    "name": ws.name,
                    "sheet_id": ws.sheet_id,
                    "row_count": ws.row_count,
                }
                for ws in worksheets
            ]
        finally:
            await sheets_client.close()

    async def get_headers(
        self,
        *,
        client_id: str,
        spreadsheet_id: str,
        worksheet_name: str,
        header_row: int = 1,
    ) -> list[str]:
        """Get column headers from a worksheet.

        Args:
            client_id: The client identifier.
            spreadsheet_id: Google Spreadsheet ID.
            worksheet_name: Name of the worksheet.
            header_row: Row number containing headers.

        Returns:
            List of column names.
        """
        access_token = await self._get_access_token(client_id=UUID(client_id))
        sheets_client = GoogleSheetsClient(access_token=access_token)

        try:
            header = await sheets_client.get_headers(
                spreadsheet_id=spreadsheet_id,
                worksheet_name=worksheet_name,
                header_row=header_row,
            )
            return header.column_names
        finally:
            await sheets_client.close()

    async def configure_sheet(
        self,
        *,
        client_id: str,
        config: GoogleSheetConfig,
        column_mappings: list[ColumnMapping],
        status_mappings: list[StatusMapping],
    ) -> SheetConfigurationResponse:
        """Configure a Google Sheet for data import.

        Args:
            client_id: The client identifier.
            config: Sheet configuration.
            column_mappings: Column mappings.
            status_mappings: Status mappings.

        Returns:
            Configuration response with IDs.

        Raises:
            ValueError: If no connection configured.
        """
        client_uuid = UUID(client_id)

        # Verify client exists
        if not await self._repository.client_exists(client_id=client_uuid):
            raise ValueError(f"Client {client_id} does not exist")

        # Get connection
        connection = await self._repository.get_connection(client_id=client_uuid)
        if not connection:
            raise ValueError("No Google Sheets connection configured")

        connection_id = UUID(connection["id"])

        # Save configuration
        config_record = await self._repository.save_sheet_config(
            client_id=client_uuid,
            config=config,
            connection_id=connection_id,
        )

        config_id = UUID(config_record["id"])

        # Save mappings
        if column_mappings:
            await self._repository.save_column_mappings(
                client_id=client_uuid,
                config_id=config_id,
                mappings=column_mappings,
            )

        if status_mappings:
            await self._repository.save_status_mappings(
                client_id=client_uuid,
                config_id=config_id,
                mappings=status_mappings,
            )

        return SheetConfigurationResponse(
            config_id=str(config_id),
            spreadsheet_id=config.spreadsheet_id,
            worksheet_name=config.worksheet_name,
            header_row=config.header_row,
            data_start_row=config.data_start_row,
            column_mappings=column_mappings,
            status_mappings=status_mappings,
        )

    async def test_connection(self, *, client_id: str) -> bool:
        """Test the Google Sheets connection for a client.

        Args:
            client_id: The client identifier.

        Returns:
            True if connection is valid.
        """
        try:
            client_uuid = UUID(client_id)

            connection = await self._repository.get_connection(client_id=client_uuid)
            if not connection:
                return False

            token_data = await self._repository.get_decrypted_token(
                client_id=client_uuid,
                connection_id=UUID(connection["id"]),
            )

            return bool(token_data and token_data.get("access_token"))

        except Exception:
            return False

    async def sync_sheet_data(
        self,
        *,
        client_id: str,
        request: GoogleSyncRequest | None = None,
    ) -> GoogleSyncResult:
        """Synchronize data from a configured Google Sheet.

        Reads all rows from the configured sheet and stores them.
        Uses row hashes for idempotency - duplicate rows are skipped.

        Args:
            client_id: The client identifier.
            request: Optional sync request with date range.

        Returns:
            Sync result with statistics.

        Raises:
            ValueError: If no configuration found.
        """
        client_uuid = UUID(client_id)

        # Get configuration
        config_record = await self._repository.get_sheet_config(client_id=client_uuid)
        if not config_record:
            raise ValueError("No Google Sheet configuration found")

        config_id = UUID(config_record["id"])
        connection_id = UUID(config_record["connection_id"])

        config = GoogleSheetConfig(
            spreadsheet_id=config_record["spreadsheet_id"],
            worksheet_name=config_record["worksheet_name"],
            header_row=config_record["header_row"],
            data_start_row=config_record["data_start_row"],
        )

        # Get access token
        access_token = await self._get_access_token(client_id=client_uuid)

        # Create sync run
        sync_run = await self._repository.create_sync_run(
            client_id=client_uuid,
            integration_connection_id=connection_id,
            config_id=config_id,
            watermark_from=request.date_from if request else None,
            watermark_to=request.date_to if request else None,
            initiated_by="manual",
        )
        sync_run_id = UUID(sync_run["id"])

        try:
            # Fetch rows from Google Sheets
            sheets_client = GoogleSheetsClient(access_token=access_token)

            try:
                # Calculate row range (we don't know total rows, so fetch reasonable batch)
                start_row = config.data_start_row
                end_row = start_row + 999  # Max 1000 rows per sync

                rows = await sheets_client.get_rows(
                    spreadsheet_id=config.spreadsheet_id,
                    worksheet_name=config.worksheet_name,
                    start_row=start_row,
                    end_row=end_row,
                )
            finally:
                await sheets_client.close()

            # Calculate row hashes for deduplication
            rows_with_hashes = []
            for row in rows:
                # Create hash from row values
                row_values_str = str(row.values)
                row_hash = hashlib.sha256(row_values_str.encode()).hexdigest()
                rows_with_hashes.append((row, row_hash))

            # Save raw rows
            saved_rows = await self._repository.save_raw_rows(
                client_id=client_uuid,
                config_id=config_id,
                sync_run_id=sync_run_id,
                rows=rows,
            )

            # Calculate statistics
            rows_read = len(rows)
            rows_written = len(saved_rows)
            rows_skipped = rows_read - rows_written

            # Complete sync run
            await self._repository.complete_sync_run(
                client_id=client_uuid,
                sync_run_id=sync_run_id,
                status="succeeded",
                rows_read=rows_read,
                rows_written=rows_written,
                rows_skipped=rows_skipped,
            )

            return GoogleSyncResult(
                sync_run_id=str(sync_run_id),
                client_id=client_id,
                spreadsheet_id=config.spreadsheet_id,
                worksheet_name=config.worksheet_name,
                status="succeeded",
                rows_read=rows_read,
                rows_written=rows_written,
                rows_skipped=rows_skipped,
            )

        except Exception as error:
            logger.error(
                "Google Sheets sync failed",
                extra={
                    "client_id": client_id,
                    "sync_run_id": str(sync_run_id),
                    "error_type": type(error).__name__,
                },
                exc_info=True,
            )

            # Safe error message (never expose tokens)
            safe_error = "Sync failed without exposing credentials"

            await self._repository.complete_sync_run(
                client_id=client_uuid,
                sync_run_id=sync_run_id,
                status="failed",
                error_summary=safe_error,
            )

            raise

    async def _get_access_token(self, *, client_id: UUID) -> str:
        """Get a valid access token for a client.

        Refreshes token if expired.

        Args:
            client_id: The client UUID.

        Returns:
            Valid access token (decrypted).

        Raises:
            ValueError: If no valid token available.
        """
        connection = await self._repository.get_connection(client_id=client_id)
        if not connection:
            raise ValueError("No Google Sheets connection configured")

        connection_id = UUID(connection["id"])
        token_data = await self._repository.get_decrypted_token(
            client_id=client_id,
            connection_id=connection_id,
        )

        if not token_data:
            raise ValueError("No Google OAuth tokens found")

        access_token = token_data["access_token"]
        expires_at = datetime.fromisoformat(token_data["expires_at"])

        # Check if token needs refresh
        if expires_at <= datetime.now(timezone.utc):
            if not token_data.get("refresh_token"):
                raise ValueError("Token expired and no refresh token available")

            new_tokens = await refresh_access_token(
                refresh_token=token_data["refresh_token"],
                settings=self._settings,
            )

            # Decrypt new access token for use
            from app.core.encryption import decrypt_token
            decrypted_access_token = decrypt_token(
                new_tokens.access_token,
                self._settings.token_encryption_key,
            )

            await self._repository.update_encrypted_token(
                client_id=client_id,
                connection_id=connection_id,
                encrypted_access_token=new_tokens.access_token,
                expires_at=new_tokens.expires_at,
            )

            return decrypted_access_token

        return access_token
