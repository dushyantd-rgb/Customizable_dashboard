"""Pydantic models for Google Sheets integration."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

APPROVED_CANONICAL_FIELDS = frozenset(
    {
        "source_lead_id",
        "lead_date",
        "lead_identifier",
        "campaign_id",
        "campaign_name",
        "adset_id",
        "adset_name",
        "ad_id",
        "ad_name",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "lead_status",
        "is_qualified",
        "lead_stage",
        "qualification_reason",
        "disqualification_reason",
        "sales_notes",
        "owner",
        "follow_up_status",
        "conversion_status",
        "revenue",
    }
)

CANONICAL_LEAD_STATUSES = frozenset(
    {"qualified", "in_progress", "invalid", "disqualified", "converted", "not_reviewed"}
)


class GoogleOAuthState(BaseModel):
    """OAuth state parameter with HMAC validation.

    Contains client_id and a nonce for CSRF protection.
    The state is URL-safe encoded and HMAC-signed.
    """

    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(..., min_length=1)
    nonce: str = Field(..., min_length=8)
    issued_at: int = Field(..., ge=0)
    hmac: str = Field(..., min_length=1)


class GoogleTokenResponse(BaseModel):
    """Response from Google OAuth token exchange.

    Contains access token, refresh token, and expiration.
    Tokens should be encrypted before storage.
    """

    model_config = ConfigDict(extra="forbid")

    access_token: SecretStr = Field(..., min_length=1, exclude=True, repr=False)
    refresh_token: SecretStr | None = Field(default=None, exclude=True, repr=False)
    expires_at: datetime
    token_type: str = Field(default="Bearer")
    scope: str | None = None


class SpreadsheetSummary(BaseModel):
    """Summary of a Google Spreadsheet accessible via API."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    name: str | None = None
    permissions: str | None = None  # e.g., "edit", "view"


class WorksheetSummary(BaseModel):
    """Summary of a worksheet within a spreadsheet."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    sheet_id: int
    row_count: int = Field(ge=0)


class SheetHeader(BaseModel):
    """Column headers from a worksheet."""

    model_config = ConfigDict(extra="forbid")

    column_names: list[str] = Field(default_factory=list)


class SheetRow(BaseModel):
    """Single row from a worksheet with row number."""

    model_config = ConfigDict(extra="allow")

    row_number: int = Field(ge=1)
    values: list[Any] = Field(default_factory=list)


class ColumnMapping(BaseModel):
    """Mapping from sheet column to canonical field."""

    model_config = ConfigDict(extra="forbid")

    source_header: str = Field(..., min_length=1)
    canonical_field: str = Field(..., min_length=1)
    required: bool = Field(default=False)

    @field_validator("canonical_field")
    @classmethod
    def canonical_field_is_approved(cls, value: str) -> str:
        if value not in APPROVED_CANONICAL_FIELDS:
            raise ValueError("canonical_field is not approved")
        return value


class StatusMapping(BaseModel):
    """Mapping from sheet status value to canonical status."""

    model_config = ConfigDict(extra="forbid")

    source_value: str = Field(..., min_length=1)
    canonical_status: str = Field(..., min_length=1)
    counts_as_reviewed: bool = Field(default=False)

    @field_validator("canonical_status")
    @classmethod
    def canonical_status_is_approved(cls, value: str) -> str:
        if value not in CANONICAL_LEAD_STATUSES:
            raise ValueError("canonical_status is not approved")
        return value


class GoogleSheetConfig(BaseModel):
    """Configuration for a Google Sheet data source."""

    model_config = ConfigDict(extra="forbid")

    spreadsheet_id: str = Field(..., min_length=1)
    worksheet_name: str = Field(..., min_length=1)
    header_row: int = Field(default=1, ge=1, le=100)
    data_start_row: int = Field(default=2, ge=1, le=1000)
    source_timezone: str = Field(default="UTC", min_length=1, max_length=100)

    @field_validator("data_start_row")
    @classmethod
    def data_start_row_after_header(cls, value: int, info: Any) -> int:
        header_row = info.data.get("header_row", 1)
        if value <= header_row:
            raise ValueError("data_start_row must be greater than header_row")
        return value


class GoogleSyncRequest(BaseModel):
    """Request to sync Google Sheet data."""

    model_config = ConfigDict(extra="forbid")

    date_from: datetime | None = None
    date_to: datetime | None = None

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, value: datetime | None, info: Any) -> datetime | None:
        date_from = info.data.get("date_from")
        if date_from is not None and value is not None and value < date_from:
            raise ValueError("date_to must not precede date_from")
        return value


class GoogleSyncResult(BaseModel):
    """Result of a Google Sheets sync operation."""

    model_config = ConfigDict(extra="forbid")

    sync_run_id: str
    client_id: str
    spreadsheet_id: str
    worksheet_name: str
    status: str
    rows_read: int
    rows_written: int
    rows_skipped: int
    error_summary: str | None = None


class SpreadsheetDiscoveryResponse(BaseModel):
    """Response for spreadsheet discovery."""

    model_config = ConfigDict(extra="forbid")

    spreadsheets: list[SpreadsheetSummary]


class WorksheetDiscoveryResponse(BaseModel):
    """Response for worksheet discovery."""

    model_config = ConfigDict(extra="forbid")

    worksheets: list[WorksheetSummary]


class SheetPreviewResponse(BaseModel):
    """Safe worksheet header and small sample preview."""

    model_config = ConfigDict(extra="forbid")

    headers: list[str]
    sample_rows: list[SheetRow]


class SheetConfigurationResponse(BaseModel):
    """Response for sheet configuration."""

    model_config = ConfigDict(extra="forbid")

    config_id: str
    spreadsheet_id: str
    worksheet_name: str
    header_row: int
    data_start_row: int
    column_mappings: list[ColumnMapping]
    status_mappings: list[StatusMapping]
