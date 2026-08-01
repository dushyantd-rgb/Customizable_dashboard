"""Client-scoped API routes for the read-only Google Sheets connector."""

from uuid import UUID

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import RedirectResponse

from app.api.v1.dependencies import ReportingClientDependency
from app.core.errors import ClientNotFoundError
from app.integrations.google.dependencies import (
    GoogleRepositoryDependency,
    GoogleServiceDependency,
)
from app.integrations.google.models import (
    ColumnMapping,
    GoogleSheetConfig,
    GoogleSyncRequest,
    GoogleSyncResult,
    SheetPreviewResponse,
    SpreadsheetSummary,
    StatusMapping,
    WorksheetSummary,
)

router = APIRouter(prefix="/integrations/google", tags=["google"])


async def _require_client(client_id: UUID, client: ReportingClientDependency) -> None:
    from app.repositories.clients import ReportingClientRepository

    if not await ReportingClientRepository(client).exists(client_id=client_id):
        raise ClientNotFoundError


@router.get("/clients/{client_id}/oauth/start")
async def start_google_oauth(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    service: GoogleServiceDependency,
) -> RedirectResponse:
    await _require_client(client_id, reporting_client)
    return RedirectResponse(await service.start_oauth_flow(client_id=client_id), status_code=302)


@router.get("/callback")
async def google_oauth_callback(
    code: str,
    state: str,
    request: Request,
    service: GoogleServiceDependency,
) -> RedirectResponse:
    client_id = await service.complete_oauth_flow(code=code, state=state)
    destination = (
        f"{request.app.state.settings.web_url.rstrip('/')}/clients/{client_id}/integrations"
        "?google=connected"
    )
    return RedirectResponse(destination, status_code=303)


@router.get(
    "/clients/{client_id}/spreadsheets",
    response_model=list[SpreadsheetSummary],
)
async def discover_spreadsheets(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    service: GoogleServiceDependency,
) -> list[SpreadsheetSummary]:
    await _require_client(client_id, reporting_client)
    return await service.discover_spreadsheets(client_id=client_id)


@router.get(
    "/clients/{client_id}/spreadsheets/{spreadsheet_id}/worksheets",
    response_model=list[WorksheetSummary],
)
async def discover_worksheets(
    client_id: UUID,
    spreadsheet_id: str,
    reporting_client: ReportingClientDependency,
    service: GoogleServiceDependency,
) -> list[WorksheetSummary]:
    await _require_client(client_id, reporting_client)
    return await service.get_worksheets(client_id=client_id, spreadsheet_id=spreadsheet_id)


@router.get(
    "/clients/{client_id}/spreadsheets/{spreadsheet_id}/worksheets/{worksheet_name}/preview",
    response_model=SheetPreviewResponse,
)
async def preview_worksheet(
    client_id: UUID,
    spreadsheet_id: str,
    worksheet_name: str,
    reporting_client: ReportingClientDependency,
    service: GoogleServiceDependency,
    header_row: int = Query(default=1, ge=1, le=100),
    data_start_row: int = Query(default=2, ge=2, le=1000),
) -> SheetPreviewResponse:
    await _require_client(client_id, reporting_client)
    return await service.preview_sheet(
        client_id=client_id,
        spreadsheet_id=spreadsheet_id,
        worksheet_name=worksheet_name,
        header_row=header_row,
        data_start_row=data_start_row,
    )


@router.post("/clients/{client_id}/config", status_code=status.HTTP_200_OK)
async def configure_google_sheet(
    client_id: UUID,
    config: GoogleSheetConfig,
    reporting_client: ReportingClientDependency,
    service: GoogleServiceDependency,
) -> dict[str, str | int]:
    await _require_client(client_id, reporting_client)
    saved = await service.configure_sheet(client_id=client_id, config=config)
    return {
        "config_id": str(saved["id"]),
        "mapping_version": int(saved["mapping_version"]),
        "source_timezone": str(saved["source_timezone"]),
    }


@router.post("/clients/{client_id}/config/{config_id}/column-mappings")
async def save_column_mappings(
    client_id: UUID,
    config_id: UUID,
    mappings: list[ColumnMapping],
    reporting_client: ReportingClientDependency,
    repository: GoogleRepositoryDependency,
) -> dict[str, int]:
    await _require_client(client_id, reporting_client)
    count = await repository.save_column_mappings(
        client_id=client_id,
        config_id=config_id,
        mappings=mappings,
    )
    return {"mappings_saved": count}


@router.post("/clients/{client_id}/config/{config_id}/status-mappings")
async def save_status_mappings(
    client_id: UUID,
    config_id: UUID,
    mappings: list[StatusMapping],
    reporting_client: ReportingClientDependency,
    repository: GoogleRepositoryDependency,
) -> dict[str, int]:
    await _require_client(client_id, reporting_client)
    count = await repository.save_status_mappings(
        client_id=client_id,
        config_id=config_id,
        mappings=mappings,
    )
    return {"mappings_saved": count}


@router.post("/clients/{client_id}/test")
async def test_google_connection(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    service: GoogleServiceDependency,
) -> dict[str, bool]:
    await _require_client(client_id, reporting_client)
    return {"connected": await service.test_connection(client_id=client_id)}


@router.post(
    "/clients/{client_id}/sync",
    response_model=GoogleSyncResult,
)
async def sync_google_sheet(
    client_id: UUID,
    _sync_request: GoogleSyncRequest,
    reporting_client: ReportingClientDependency,
    service: GoogleServiceDependency,
) -> GoogleSyncResult:
    await _require_client(client_id, reporting_client)
    return await service.sync_sheet_data(client_id=client_id)


@router.get("/clients/{client_id}/sync-runs")
async def get_google_sync_runs(
    client_id: UUID,
    reporting_client: ReportingClientDependency,
    repository: GoogleRepositoryDependency,
    limit: int = Query(default=10, ge=1, le=100),
) -> list[dict[str, str | int | None]]:
    await _require_client(client_id, reporting_client)
    return await repository.get_sync_runs(client_id=client_id, limit=limit)
