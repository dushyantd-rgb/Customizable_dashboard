"""HTTP client for Google Sheets API (read-only)."""

import logging
from typing import Any

import httpx

from app.core.errors import SafeApplicationError
from app.integrations.google.models import (
    SheetHeader,
    SheetRow,
    SpreadsheetSummary,
    WorksheetSummary,
)

logger = logging.getLogger(__name__)

# Google API endpoints
GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
GOOGLE_SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"


class GoogleSheetsApiError(SafeApplicationError):
    """Error from Google Sheets API with safe public representation."""

    code = "google_sheets_api_error"
    safe_message = "The Google Sheets connection failed"
    status_code = 502


class GoogleSheetsClient:
    """
    HTTP client for Google Sheets API (read-only).

    Provides methods to discover spreadsheets, read headers, and fetch rows.
    Never writes to sheets - all operations are read-only.
    Never exposes tokens in logs or error messages.
    """

    def __init__(
        self,
        *,
        access_token: str,
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize the Google Sheets client.

        Args:
            access_token: OAuth2 access token (decrypted).
            http_client: Optional HTTP client for testing.
            timeout_seconds: Request timeout in seconds.
        """
        self._access_token = access_token
        self._http_client = http_client
        self._timeout = timeout_seconds
        self._owned_client = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=10.0)
            )
            self._owned_client = True
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client if owned."""
        if self._owned_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
            self._owned_client = False

    async def _request(
        self,
        *,
        base_url: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated GET request to Google API.

        Args:
            base_url: API base URL.
            path: API path.
            params: Optional query parameters.

        Returns:
            JSON response payload.

        Raises:
            GoogleSheetsApiError: If request fails.
        """
        client = await self._get_client()
        url = f"{base_url}/{path}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params or {})
        except (httpx.TimeoutException, httpx.TransportError) as error:
            logger.warning(
                "Google API network error",
                extra={"path": path, "error_type": type(error).__name__},
            )
            raise GoogleSheetsApiError from error

        if response.status_code == 401:
            logger.warning("Google API authentication error", extra={"path": path})
            raise GoogleSheetsApiError

        if response.status_code == 403:
            logger.warning("Google API permission denied", extra={"path": path})
            raise GoogleSheetsApiError

        if response.status_code == 404:
            logger.warning("Google API resource not found", extra={"path": path})
            raise GoogleSheetsApiError

        if response.status_code >= 400:
            logger.warning(
                "Google API error response",
                extra={"path": path, "status": response.status_code},
            )
            raise GoogleSheetsApiError

        try:
            payload = response.json()
        except ValueError as error:
            logger.warning("Google API JSON decode error", extra={"path": path})
            raise GoogleSheetsApiError from error

        if "error" in payload:
            logger.warning(
                "Google API returned error",
                extra={"path": path, "error_code": payload["error"].get("code")},
            )
            raise GoogleSheetsApiError

        return payload

    async def list_spreadsheets(self) -> list[SpreadsheetSummary]:
        """
        List spreadsheets accessible to the authenticated user.

        Uses Google Drive API to find spreadsheets with read access.

        Returns:
            List of spreadsheet summaries (never includes tokens).
        """
        try:
            data = await self._request(
                base_url=GOOGLE_DRIVE_API_BASE,
                path="files",
                params={
                    "q": "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
                    "fields": "files(id, name, permissions)",
                    "pageSize": "100",
                },
            )

            files = data.get("files", [])
            spreadsheets = []
            for file in files:
                # Determine permission level safely
                permissions = "unknown"
                if "permissions" in file:
                    for perm in file.get("permissions", []):
                        if perm.get("role") in ("owner", "writer"):
                            permissions = "edit"
                            break
                        elif perm.get("role") == "reader":
                            permissions = "view"

                spreadsheets.append(
                    SpreadsheetSummary(
                        id=file.get("id", ""),
                        name=file.get("name"),
                        permissions=permissions,
                    )
                )

            return spreadsheets

        except KeyError as error:
            logger.warning("Google Drive API response missing key", exc_info=True)
            raise GoogleSheetsApiError from error

    async def get_worksheets(self, spreadsheet_id: str) -> list[WorksheetSummary]:
        """
        Get worksheets for a spreadsheet.

        Args:
            spreadsheet_id: Google Spreadsheet ID.

        Returns:
            List of worksheet summaries.
        """
        try:
            data = await self._request(
                base_url=GOOGLE_SHEETS_API_BASE,
                path=spreadsheet_id,
                params={
                    "fields": "sheets(properties(sheetId,title,gridProperties(rowCount)))",
                },
            )

            sheets = data.get("sheets", [])
            worksheets = []
            for sheet in sheets:
                props = sheet.get("properties", {})
                grid_props = props.get("gridProperties", {})

                worksheets.append(
                    WorksheetSummary(
                        name=props.get("title", ""),
                        sheet_id=props.get("sheetId", 0),
                        row_count=grid_props.get("rowCount", 0),
                    )
                )

            return worksheets

        except KeyError as error:
            logger.warning("Google Sheets API worksheets response missing key", exc_info=True)
            raise GoogleSheetsApiError from error

    async def get_headers(
        self,
        spreadsheet_id: str,
        worksheet_name: str,
        header_row: int,
    ) -> SheetHeader:
        """
        Get column headers from a worksheet.

        Args:
            spreadsheet_id: Google Spreadsheet ID.
            worksheet_name: Name of the worksheet.
            header_row: Row number containing headers (1-indexed).

        Returns:
            SheetHeader with column names.
        """
        try:
            # Build range for header row
            range_notation = f"'{worksheet_name}'!{header_row}:{header_row}"

            data = await self._request(
                base_url=GOOGLE_SHEETS_API_BASE,
                path=f"{spreadsheet_id}/values/{range_notation}",
                params={
                    "majorDimension": "ROWS",
                    "valueRenderOption": "UNFORMATTED_VALUE",
                },
            )

            values = data.get("values", [])
            if not values:
                return SheetHeader(column_names=[])

            # Get first row (header row)
            header_values = values[0] if values else []
            column_names = [str(v) if v is not None else "" for v in header_values]

            return SheetHeader(column_names=column_names)

        except KeyError as error:
            logger.warning("Google Sheets API headers response missing key", exc_info=True)
            raise GoogleSheetsApiError from error

    async def get_rows(
        self,
        spreadsheet_id: str,
        worksheet_name: str,
        start_row: int,
        end_row: int,
    ) -> list[SheetRow]:
        """
        Get rows from a worksheet (read-only).

        Args:
            spreadsheet_id: Google Spreadsheet ID.
            worksheet_name: Name of the worksheet.
            start_row: Starting row number (1-indexed, inclusive).
            end_row: Ending row number (1-indexed, inclusive).

        Returns:
            List of SheetRow objects with row numbers and values.

        Note:
            This method only reads data - it never writes to sheets.
        """
        try:
            # Build range notation
            range_notation = f"'{worksheet_name}'!{start_row}:{end_row}"

            data = await self._request(
                base_url=GOOGLE_SHEETS_API_BASE,
                path=f"{spreadsheet_id}/values/{range_notation}",
                params={
                    "majorDimension": "ROWS",
                    "valueRenderOption": "UNFORMATTED_VALUE",
                },
            )

            values = data.get("values", [])
            rows = []

            for idx, row_values in enumerate(values):
                row_number = start_row + idx
                rows.append(
                    SheetRow(
                        row_number=row_number,
                        values=row_values if row_values else [],
                    )
                )

            return rows

        except KeyError as error:
            logger.warning("Google Sheets API rows response missing key", exc_info=True)
            raise GoogleSheetsApiError from error

    async def validate_access(self, spreadsheet_id: str) -> bool:
        """
        Validate that the client has read access to a spreadsheet.

        Args:
            spreadsheet_id: Google Spreadsheet ID.

        Returns:
            True if accessible, False otherwise.
        """
        try:
            await self._request(
                base_url=GOOGLE_SHEETS_API_BASE,
                path=spreadsheet_id,
                params={"fields": "properties(title)"},
            )
            return True
        except GoogleSheetsApiError:
            return False

    async def get_sheet_metadata(self, spreadsheet_id: str) -> dict[str, Any]:
        """
        Get metadata for a spreadsheet.

        Args:
            spreadsheet_id: Google Spreadsheet ID.

        Returns:
            Spreadsheet metadata (safe subset, no tokens).
        """
        try:
            data = await self._request(
                base_url=GOOGLE_SHEETS_API_BASE,
                path=spreadsheet_id,
                params={
                    "fields": (
                        "properties(title,locale,timeZone),"
                        "sheets(properties(sheetId,title,gridProperties))"
                    ),
                },
            )

            # Extract safe metadata
            props = data.get("properties", {})
            return {
                "title": props.get("title"),
                "locale": props.get("locale"),
                "timezone": props.get("timeZone"),
                "sheets": data.get("sheets", []),
            }

        except KeyError as error:
            logger.warning("Google Sheets metadata response missing key", exc_info=True)
            raise GoogleSheetsApiError from error
