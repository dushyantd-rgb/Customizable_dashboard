"""Google Sheets connector for GrowthByte Reporting Platform."""

from app.integrations.google.client import GoogleSheetsApiError, GoogleSheetsClient
from app.integrations.google.models import (
    ColumnMapping,
    GoogleOAuthState,
    GoogleSheetConfig,
    GoogleSyncRequest,
    GoogleSyncResult,
    GoogleTokenResponse,
    SheetConfigurationResponse,
    SheetHeader,
    SheetRow,
    SpreadsheetSummary,
    StatusMapping,
    WorksheetSummary,
)
from app.integrations.google.oauth import (
    GoogleOAuthError,
    GoogleOAuthStateError,
    GoogleTokenExchangeError,
    exchange_code_for_tokens,
    generate_oauth_state,
    get_authorization_url,
    refresh_access_token,
    validate_oauth_state,
)
from app.integrations.google.repository import GoogleSheetsRepository
from app.integrations.google.service import GoogleSheetsService

__all__ = [
    # Client
    "GoogleSheetsClient",
    "GoogleSheetsApiError",
    # Models
    "ColumnMapping",
    "GoogleOAuthState",
    "GoogleSheetConfig",
    "GoogleSyncRequest",
    "GoogleSyncResult",
    "GoogleTokenResponse",
    "SheetConfigurationResponse",
    "SheetHeader",
    "SheetRow",
    "SpreadsheetSummary",
    "StatusMapping",
    "WorksheetSummary",
    # OAuth
    "GoogleOAuthError",
    "GoogleOAuthStateError",
    "GoogleTokenExchangeError",
    "exchange_code_for_tokens",
    "generate_oauth_state",
    "get_authorization_url",
    "refresh_access_token",
    "validate_oauth_state",
    # Repository
    "GoogleSheetsRepository",
    # Service
    "GoogleSheetsService",
]
