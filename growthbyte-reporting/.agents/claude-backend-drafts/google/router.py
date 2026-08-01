"""API routes for Google Sheets integration."""

from uuid import UUID

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse

from app.api.v1.dependencies import ReportingClientDependency
from app.core.config import get_settings
from app.core.errors import ClientNotFoundError
from app.integrations.google.dependencies import (
    GoogleOAuthDependency,
    GoogleRepositoryDependency,
    GoogleSheetsClientDependency,
    GoogleSheetsServiceDependency,
)
from app.integrations.google.models import (
    ColumnMapping,
    GoogleSheetConfig,
    GoogleSyncRequest,
    GoogleSyncResult,
    SpreadsheetSummary,
    StatusMapping,
    WorksheetSummary,
)

router = APIRouter(prefix="/integrations/google", tags=["google"])


async def _require_client(
    client_id: UUID, client: ReportingClientDependency
) -> None:
    """Verify that a client exists."""
    from app.repositories.clients import ReportingClientRepository

    if not await ReportingClientRepository(client).exists(client_id=client_id):
        raise ClientNotFoundError


@router.get("/connect/{client_id}")
async def start_google_oauth(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    oauth_service: GoogleOAuthDependency,
) -> RedirectResponse:
    """
    Start Google OAuth flow for a client.

    Redirects to Google authorization page.
    OAuth state is bound to client_id for security.
    Uses read-only Sheets scope only.
    """
    await _require_client(client_id, reporting_client)
    settings = get_settings()

    auth_url = oauth_service.get_authorization_url(
        client_id=str(client_id),
        redirect_uri=settings.google.oauth_redirect_uri,
    )

    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def google_oauth_callback(
    code: str,
    state: str,
    request: Request,
    oauth_service: GoogleOAuthDependency,
    service: GoogleSheetsServiceDependency,
) -> dict[str, str]:
    """
    Handle Google OAuth callback.

    Validates state, exchanges code for tokens, encrypts and stores tokens.
    Never returns tokens to the browser.
    """
    settings = get_settings()
    client_id = oauth_service.validate_oauth_state(state)

    await oauth_service.exchange_and_store_tokens(
        client_id=client_id,
        code=code,
        redirect_uri=settings.google.oauth_redirect_uri,
    )

    return {"status": "connected", "client_id": client_id}


@router.get("/spreadsheets/{client_id}", response_model=list[SpreadsheetSummary])
async def discover_spreadsheets(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    service: GoogleSheetsServiceDependency,
) -> list[SpreadsheetSummary]:
    """
    List available Google Sheets for a client.

    Requires valid OAuth connection for the client.
    Returns only spreadsheet IDs and names (no credentials).
    """
    await _require_client(client_id, reporting_client)
    spreadsheets = await service.discover_spreadsheets(client_id=str(client_id))
    return spreadsheets


@router.get(
    "/spreadsheets/{client_id}/{spreadsheet_id}/worksheets",
    response_model=list[WorksheetSummary],
)
async def get_worksheets(
    client_id: UUID,
    spreadsheet_id: str,
    reporting_client: ReportingClientDependency,
    service: GoogleSheetsServiceDependency,
) -> list[WorksheetSummary]:
    """
    List worksheets in a spreadsheet.

    Returns worksheet names and row counts.
    """
    await _require_client(client_id, reporting_client)
    worksheets = await service.get_worksheets(
        client_id=str(client_id),
        spreadsheet_id=spreadsheet_id,
    )
    return worksheets


@router.get(
    "/spreadsheets/{client_id}/{spreadsheet_id}/{worksheet_name}/headers",
)
async def get_worksheet_headers(
    client_id: UUID,
    spreadsheet_id: str,
    worksheet_name: str,
    header_row: int,
    reporting_client: ReportingClientDependency,
    service: GoogleSheetsServiceDependency,
) -> dict[str, list[str]]:
    """
    Get headers and sample rows from a worksheet.

    Returns column headers for mapping configuration.
    """
    await _require_client(client_id, reporting_client)
    headers = await service.get_worksheet_headers(
        client_id=str(client_id),
        spreadsheet_id=spreadsheet_id,
        worksheet_name=worksheet_name,
        header_row=header_row,
    )
    return {"headers": headers}


@router.post(
    "/config/{client_id}",
    status_code=status.HTTP_201_CREATED,
)
async def configure_google_sheet(
    client_id: UUID,
    config: GoogleSheetConfig,
    reporting_client: ReportingClientDependency,
    service: GoogleSheetsServiceDependency,
) -> dict[str, str]:
    """
    Save Google Sheet configuration with column and status mappings.

    Configures which spreadsheet/worksheet to sync and how to map columns.
    """
    await _require_client(client_id, reporting_client)
    config_id = await service.configure_sheet(
        client_id=str(client_id),
        config=config,
    )
    return {"config_id": config_id}


@router.post("/mapping/columns/{client_id}/{config_id}")
async def save_column_mappings(
    client_id: UUID,
    config_id: UUID,
    mappings: list[ColumnMapping],
    reporting_client: ReportingClientDependency,
    repository: GoogleRepositoryDependency,
) -> dict[str, int]:
    """
    Save column mappings for a sheet configuration.

    Maps source headers to canonical lead fields.
    """
    await _require_client(client_id, reporting_client)
    count = await repository.save_column_mappings(
        client_id=str(client_id),
        config_id=config_id,
        mappings=mappings,
    )
    return {"mappings_saved": count}


@router.post("/mapping/status/{client_id}/{config_id}")
async def save_status_mappings(
    client_id: UUID,
    config_id: UUID,
    mappings: list[StatusMapping],
    reporting_client: ReportingClientDependency,
    repository: GoogleRepositoryDependency,
) -> dict[str, int]:
    """
    Save status mappings for a sheet configuration.

    Maps source status values to canonical lead statuses.
    """
    await _require_client(client_id, reporting_client)
    count = await repository.save_status_mappings(
        client_id=str(client_id),
        config_id=config_id,
        mappings=mappings,
    )
    return {"mappings_saved": count}


@router.post("/test/{client_id}", status_code=status.HTTP_200_OK)
async def test_google_connection(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    service: GoogleSheetsServiceDependency,
) -> dict[str, bool]:
    """
    Test Google Sheets connection for a client.

    Verifies OAuth token and configuration without syncing.
    """
    await _require_client(client_id, reporting_client)
    connected = await service.test_connection(client_id=str(client_id))
    return {"connected": connected}


@router.post(
    "/sync/{client_id}",
    response_model=GoogleSyncResult,
    status_code=status.HTTP_200_OK,
)
async def sync_google_sheet(
    client_id: UUID,
    request: GoogleSyncRequest,
    reporting_client: ReportingClientDependency,
    service: GoogleSheetsServiceDependency,
) -> GoogleSyncResult:
    """
    Manually sync Google Sheet data for a client.

    Reads rows from configured sheet, applies mappings, stores raw data.
    Never writes to Google Sheets.
    Idempotent - repeated syncs don't create duplicates.
    """
    await _require_client(client_id, reporting_client)
    result = await service.sync_sheet_data(
        client_id=str(client_id),
        request=request,
    )
    return result


@router.get("/sync-runs/{client_id}")
async def get_google_sync_runs(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    repository: GoogleRepositoryDependency,
    limit: int = 10,
) -> list[dict[str, str | int | None]]:
    """
    Get recent Google Sheets sync runs for a client.

    Returns sync history with status, counts, and safe error summaries.
    """
    await _require_client(client_id, reporting_client)
    runs = await repository.get_sync_runs(
        client_id=str(client_id),
        source_type="google_sheets",
        limit=limit,
    )
    return runs
