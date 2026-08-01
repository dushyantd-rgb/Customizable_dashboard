"""Google Sheets OAuth, configuration, preview, and manual sync orchestration."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.integrations.google.client import GoogleSheetsClient
from app.integrations.google.models import (
    GoogleSheetConfig,
    GoogleSyncResult,
    SheetPreviewResponse,
    SpreadsheetSummary,
    WorksheetSummary,
)
from app.integrations.google.oauth import (
    GoogleOAuthError,
    exchange_code_for_tokens,
    get_authorization_url,
    refresh_access_token,
    validate_oauth_state,
)
from app.integrations.google.repository import (
    GoogleConfigurationError,
    GoogleConnectionRequiredError,
    GoogleSheetsRepository,
)

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    def __init__(
        self,
        *,
        repository: GoogleSheetsRepository,
        settings: Any,
        client_factory: Callable[[str], GoogleSheetsClient] | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._client_factory = client_factory or (
            lambda token: GoogleSheetsClient(access_token=token)
        )

    async def start_oauth_flow(self, *, client_id: UUID) -> str:
        if not await self._repository.client_exists(client_id=client_id):
            raise GoogleConfigurationError
        redirect_uri = self._settings.google.oauth_redirect_uri
        if not redirect_uri:
            raise GoogleOAuthError
        return get_authorization_url(
            client_id=str(client_id),
            redirect_uri=redirect_uri,
            settings=self._settings,
        )

    async def complete_oauth_flow(self, *, code: str, state: str) -> UUID:
        state_key = self._settings.token_encryption_key
        redirect_uri = self._settings.google.oauth_redirect_uri
        if state_key is None or not redirect_uri:
            raise GoogleOAuthError
        try:
            client_id = UUID(validate_oauth_state(state, state_key))
        except ValueError as error:
            raise GoogleOAuthError from error
        if not await self._repository.client_exists(client_id=client_id):
            raise GoogleConfigurationError
        tokens = await exchange_code_for_tokens(
            code=code,
            redirect_uri=redirect_uri,
            settings=self._settings,
        )
        connection = await self._repository.upsert_connection(client_id=client_id)
        await self._repository.store_tokens(
            client_id=client_id,
            connection_id=UUID(str(connection["id"])),
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_at=tokens.expires_at,
            scope=tokens.scope,
        )
        return client_id

    async def discover_spreadsheets(self, *, client_id: UUID) -> list[SpreadsheetSummary]:
        sheets = self._client_factory(await self._get_access_token(client_id=client_id))
        try:
            return await sheets.list_spreadsheets()
        finally:
            await sheets.close()

    async def get_worksheets(
        self,
        *,
        client_id: UUID,
        spreadsheet_id: str,
    ) -> list[WorksheetSummary]:
        sheets = self._client_factory(await self._get_access_token(client_id=client_id))
        try:
            return await sheets.get_worksheets(spreadsheet_id)
        finally:
            await sheets.close()

    async def preview_sheet(
        self,
        *,
        client_id: UUID,
        spreadsheet_id: str,
        worksheet_name: str,
        header_row: int,
        data_start_row: int,
    ) -> SheetPreviewResponse:
        if data_start_row <= header_row:
            raise GoogleConfigurationError
        sheets = self._client_factory(await self._get_access_token(client_id=client_id))
        try:
            header = await sheets.get_headers(spreadsheet_id, worksheet_name, header_row)
            rows = await sheets.get_rows(
                spreadsheet_id,
                worksheet_name,
                data_start_row,
                data_start_row + 2,
            )
        finally:
            await sheets.close()
        return SheetPreviewResponse(headers=header.column_names, sample_rows=rows)

    async def configure_sheet(
        self,
        *,
        client_id: UUID,
        config: GoogleSheetConfig,
    ) -> dict[str, Any]:
        connection = await self._require_connection(client_id=client_id)
        sheets = self._client_factory(await self._get_access_token(client_id=client_id))
        try:
            if not await sheets.validate_access(config.spreadsheet_id):
                raise GoogleConfigurationError
            metadata = await sheets.get_sheet_metadata(config.spreadsheet_id)
        finally:
            await sheets.close()
        source_timezone = metadata.get("timezone")
        resolved_config = config
        if config.source_timezone == "UTC" and isinstance(source_timezone, str) and source_timezone:
            resolved_config = config.model_copy(update={"source_timezone": source_timezone})
        saved = await self._repository.save_sheet_config(
            client_id=client_id,
            connection_id=UUID(str(connection["id"])),
            config=resolved_config,
        )
        return saved

    async def test_connection(self, *, client_id: UUID) -> bool:
        try:
            config = await self._repository.get_sheet_config(client_id=client_id)
            if config is None:
                return False
            mappings = await self._repository.get_mappings(
                client_id=client_id,
                config_id=UUID(str(config["id"])),
                mapping_version=int(config["mapping_version"]),
            )
            if not mappings["column_mappings"]:
                return False
            sheets = self._client_factory(await self._get_access_token(client_id=client_id))
            try:
                if not await sheets.validate_access(str(config["spreadsheet_id"])):
                    return False
                header = await sheets.get_headers(
                    str(config["spreadsheet_id"]),
                    str(config["worksheet_name"]),
                    int(config["header_row"]),
                )
            finally:
                await sheets.close()
            self._validate_required_headers(
                headers=header.column_names,
                column_mappings=mappings["column_mappings"],
            )
            return True
        except Exception:
            return False

    async def sync_sheet_data(self, *, client_id: UUID) -> GoogleSyncResult:
        config = await self._repository.get_sheet_config(client_id=client_id)
        if config is None:
            raise GoogleConnectionRequiredError
        config_id = UUID(str(config["id"]))
        connection_id = UUID(str(config["integration_connection_id"]))
        sync_run = await self._repository.create_sync_run(
            client_id=client_id,
            connection_id=connection_id,
            config_id=config_id,
        )
        sync_run_id = UUID(str(sync_run["id"]))
        try:
            mappings = await self._repository.get_mappings(
                client_id=client_id,
                config_id=config_id,
                mapping_version=int(config["mapping_version"]),
            )
            if not mappings["column_mappings"]:
                raise GoogleConfigurationError
            sheets = self._client_factory(await self._get_access_token(client_id=client_id))
            try:
                header = await sheets.get_headers(
                    str(config["spreadsheet_id"]),
                    str(config["worksheet_name"]),
                    int(config["header_row"]),
                )
                self._validate_required_headers(
                    headers=header.column_names,
                    column_mappings=mappings["column_mappings"],
                )
                rows = await sheets.get_rows(
                    str(config["spreadsheet_id"]),
                    str(config["worksheet_name"]),
                    int(config["data_start_row"]),
                    int(config["data_start_row"]) + 999,
                )
            finally:
                await sheets.close()
            inserted = await self._repository.save_raw_rows(
                client_id=client_id,
                config_id=config_id,
                sync_run_id=sync_run_id,
                worksheet_name=str(config["worksheet_name"]),
                rows=rows,
            )
            skipped = len(rows) - len(inserted)
            await self._repository.complete_sync_run(
                client_id=client_id,
                sync_run_id=sync_run_id,
                status="succeeded",
                rows_read=len(rows),
                rows_written=len(inserted),
                warning_count=skipped,
            )
            return GoogleSyncResult(
                sync_run_id=str(sync_run_id),
                client_id=str(client_id),
                spreadsheet_id=str(config["spreadsheet_id"]),
                worksheet_name=str(config["worksheet_name"]),
                status="succeeded",
                rows_read=len(rows),
                rows_written=len(inserted),
                rows_skipped=skipped,
            )
        except Exception:
            logger.error(
                "Google Sheet sync failed",
                extra={
                    "client_id": str(client_id),
                    "sync_run_id": str(sync_run_id),
                },
            )
            await self._repository.complete_sync_run(
                client_id=client_id,
                sync_run_id=sync_run_id,
                status="failed",
                error_summary="Google Sheet sync failed safely",
            )
            raise

    async def _get_access_token(self, *, client_id: UUID) -> str:
        connection = await self._require_connection(client_id=client_id)
        connection_id = UUID(str(connection["id"]))
        tokens = await self._repository.get_tokens(
            client_id=client_id,
            connection_id=connection_id,
        )
        if tokens is None:
            raise GoogleConnectionRequiredError
        if tokens["expires_at"] <= datetime.now(UTC):
            refresh_token = tokens.get("refresh_token")
            if refresh_token is None:
                raise GoogleConnectionRequiredError
            refreshed = await refresh_access_token(
                refresh_token=refresh_token,
                settings=self._settings,
            )
            await self._repository.update_access_token(
                client_id=client_id,
                connection_id=connection_id,
                access_token=refreshed.access_token,
                expires_at=refreshed.expires_at,
                scope=refreshed.scope,
            )
            return refreshed.access_token.get_secret_value()
        return tokens["access_token"].get_secret_value()

    async def _require_connection(self, *, client_id: UUID) -> dict[str, Any]:
        connection = await self._repository.get_connection(client_id=client_id)
        if connection is None:
            raise GoogleConnectionRequiredError
        return connection

    @staticmethod
    def _validate_required_headers(
        *,
        headers: list[str],
        column_mappings: list[dict[str, Any]],
    ) -> None:
        header_set = set(headers)
        missing = [
            str(mapping["source_header"])
            for mapping in column_mappings
            if mapping.get("required") and mapping.get("source_header") not in header_set
        ]
        if missing:
            raise GoogleConfigurationError
