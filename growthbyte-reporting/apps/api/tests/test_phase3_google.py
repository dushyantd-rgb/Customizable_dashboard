"""Focused acceptance tests for the read-only Google Sheets prototype."""

import base64
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import pytest
from pydantic import SecretStr, ValidationError

from app.integrations.google.client import GoogleSheetsClient
from app.integrations.google.models import (
    ColumnMapping,
    GoogleSheetConfig,
    SheetHeader,
    SheetRow,
    StatusMapping,
)
from app.integrations.google.oauth import (
    GOOGLE_SCOPES,
    GoogleOAuthStateError,
    generate_oauth_state,
    get_authorization_url,
    validate_oauth_state,
)
from app.integrations.google.repository import (
    GoogleConfigurationError,
    GoogleSheetsRepository,
)
from app.integrations.google.service import GoogleSheetsService
from tests.helpers import SYNTHETIC_CLIENT_A_ID, SYNTHETIC_CLIENT_B_ID
from tests.phase3_helpers import Phase3MemoryClient


def _key() -> SecretStr:
    return SecretStr(base64.b64encode(os.urandom(32)).decode())


class _GoogleSettings:
    def __init__(self, key: SecretStr) -> None:
        self.token_encryption_key = key
        self.google = type(
            "GoogleSettings",
            (),
            {
                "oauth_client_id": SecretStr("synthetic-client-id"),
                "oauth_client_secret": SecretStr("synthetic-client-secret"),
                "oauth_redirect_uri": "http://localhost:8000/api/v1/integrations/google/oauth/callback",
            },
        )()


class _FakeSheets:
    def __init__(self, *, headers: list[str] | None = None) -> None:
        self.headers = headers or ["Lead ID", "Status"]
        self.read_calls: list[str] = []

    async def validate_access(self, _spreadsheet_id: str) -> bool:
        self.read_calls.append("validate_access")
        return True

    async def get_sheet_metadata(self, _spreadsheet_id: str) -> dict[str, str]:
        self.read_calls.append("get_sheet_metadata")
        return {"timezone": "Asia/Kolkata"}

    async def get_headers(
        self, _spreadsheet_id: str, _worksheet_name: str, _header_row: int
    ) -> SheetHeader:
        self.read_calls.append("get_headers")
        return SheetHeader(column_names=self.headers)

    async def get_rows(
        self,
        _spreadsheet_id: str,
        _worksheet_name: str,
        _start_row: int,
        _end_row: int,
    ) -> list[SheetRow]:
        self.read_calls.append("get_rows")
        return [SheetRow(row_number=2, values=["lead-1", "New"])]

    async def close(self) -> None:
        self.read_calls.append("close")


async def _configured_google(
    *, headers: list[str] | None = None
) -> tuple[Phase3MemoryClient, GoogleSheetsRepository, GoogleSheetsService, _FakeSheets]:
    store = Phase3MemoryClient()
    key = _key()
    repository = GoogleSheetsRepository(store, key)
    client_id = UUID(SYNTHETIC_CLIENT_A_ID)
    connection = await repository.upsert_connection(client_id=client_id)
    await repository.store_tokens(
        client_id=client_id,
        connection_id=UUID(str(connection["id"])),
        access_token=SecretStr("synthetic-access-token"),
        refresh_token=SecretStr("synthetic-refresh-token"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    sheets = _FakeSheets(headers=headers)
    service = GoogleSheetsService(
        repository=repository,
        settings=_GoogleSettings(key),
        client_factory=lambda _token: sheets,
    )
    config = await service.configure_sheet(
        client_id=client_id,
        config=GoogleSheetConfig(spreadsheet_id="sheet-1", worksheet_name="Leads"),
    )
    config_id = UUID(str(config["id"]))
    await repository.save_column_mappings(
        client_id=client_id,
        config_id=config_id,
        mappings=[
            ColumnMapping(source_header="Lead ID", canonical_field="source_lead_id", required=True),
            ColumnMapping(source_header="Status", canonical_field="lead_status"),
        ],
    )
    await repository.save_status_mappings(
        client_id=client_id,
        config_id=config_id,
        mappings=[
            StatusMapping(
                source_value=" New ",
                canonical_status="not_reviewed",
                counts_as_reviewed=False,
            )
        ],
    )
    return store, repository, service, sheets


def test_oauth_state_is_client_bound_tamper_evident_and_expires() -> None:
    key = _key()
    state = generate_oauth_state(SYNTHETIC_CLIENT_A_ID, key)
    assert validate_oauth_state(state, key) == SYNTHETIC_CLIENT_A_ID

    payload = bytearray(base64.urlsafe_b64decode(state))
    payload[-2] ^= 1
    tampered = base64.urlsafe_b64encode(payload).decode()
    with pytest.raises(GoogleOAuthStateError):
        validate_oauth_state(tampered, key)

    with pytest.raises(GoogleOAuthStateError):
        validate_oauth_state(state, key, now=int(datetime.now(UTC).timestamp()) + 601)


def test_oauth_url_requests_only_read_scopes() -> None:
    settings = _GoogleSettings(_key())
    url = get_authorization_url(
        client_id=SYNTHETIC_CLIENT_A_ID,
        redirect_uri=settings.google.oauth_redirect_uri,
        settings=settings,
    )
    scopes = set(parse_qs(urlparse(url).query)["scope"][0].split())
    assert scopes == set(GOOGLE_SCOPES)
    assert all(scope.endswith(".readonly") for scope in scopes)


@pytest.mark.asyncio
async def test_tokens_are_encrypted_and_client_scoped() -> None:
    store, repository, _service, _sheets = await _configured_google()
    credential = store.rows["google_oauth_credentials"][0]
    serialized = str(credential)
    assert "synthetic-access-token" not in serialized
    assert "synthetic-refresh-token" not in serialized

    connection = store.rows["integration_connections"][0]
    tokens = await repository.get_tokens(
        client_id=UUID(SYNTHETIC_CLIENT_A_ID),
        connection_id=UUID(str(connection["id"])),
    )
    assert tokens is not None
    assert tokens["access_token"].get_secret_value() == "synthetic-access-token"
    assert (
        await repository.get_tokens(
            client_id=UUID(SYNTHETIC_CLIENT_B_ID),
            connection_id=UUID(str(connection["id"])),
        )
        is None
    )


@pytest.mark.asyncio
async def test_google_config_mappings_and_sync_are_client_scoped_and_idempotent() -> None:
    store, repository, service, sheets = await _configured_google()
    client_a = UUID(SYNTHETIC_CLIENT_A_ID)
    client_b = UUID(SYNTHETIC_CLIENT_B_ID)
    config = await repository.get_sheet_config(client_id=client_a)
    assert config is not None
    assert await repository.get_sheet_config(client_id=client_b) is None

    mappings = await repository.get_mappings(
        client_id=client_a,
        config_id=UUID(str(config["id"])),
        mapping_version=int(config["mapping_version"]),
    )
    assert mappings["column_mappings"][0]["canonical_field"] == "source_lead_id"
    assert mappings["status_mappings"][0]["source_value_normalized"] == "new"

    first = await service.sync_sheet_data(client_id=client_a)
    second = await service.sync_sheet_data(client_id=client_a)
    assert (first.rows_written, second.rows_written, second.rows_skipped) == (1, 0, 1)
    assert len(store.rows["raw_sheet_rows"]) == 1
    assert [run["status"] for run in store.rows["sync_runs"]] == [
        "succeeded",
        "succeeded",
    ]
    assert set(sheets.read_calls) <= {
        "validate_access",
        "get_sheet_metadata",
        "get_headers",
        "get_rows",
        "close",
    }


@pytest.mark.asyncio
async def test_missing_required_header_marks_sync_failed_safely() -> None:
    store, _repository, service, _sheets = await _configured_google(headers=["Status"])
    with pytest.raises(GoogleConfigurationError):
        await service.sync_sheet_data(client_id=UUID(SYNTHETIC_CLIENT_A_ID))
    run = store.rows["sync_runs"][-1]
    assert run["status"] == "failed"
    assert run["error_summary"] == "Google Sheet sync failed safely"
    assert "synthetic-access-token" not in str(run)


def test_mapping_models_reject_unapproved_targets() -> None:
    with pytest.raises(ValidationError):
        ColumnMapping(source_header="Email", canonical_field="arbitrary_database_column")
    with pytest.raises(ValidationError):
        StatusMapping(source_value="New", canonical_status="invented")


class _ReadOnlyHttp:
    def __init__(self) -> None:
        self.get_calls = 0

    async def get(self, *_args: object, **_kwargs: object):
        self.get_calls += 1
        return type("Response", (), {"status_code": 200, "json": lambda self: {}})()


@pytest.mark.asyncio
async def test_google_http_client_uses_get_only() -> None:
    http = _ReadOnlyHttp()
    client = GoogleSheetsClient(access_token="synthetic", http_client=http)  # type: ignore[arg-type]
    assert await client.validate_access("sheet-1") is True
    assert http.get_calls == 1
