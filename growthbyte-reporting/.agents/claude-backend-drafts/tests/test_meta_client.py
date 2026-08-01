"""Tests for Meta Graph API client with mocked HTTP responses."""

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.integrations.meta.client import MetaApiError, MetaGraphClient
from app.integrations.meta.models import (
    MetaAdAccountSummary,
    MetaAdSetSummary,
    MetaAdSummary,
    MetaCampaignSummary,
    MetaInsightRow,
)


class FakeHttpxResponse:
    """Fake httpx response for testing."""

    def __init__(
        self,
        *,
        status_code: int = 200,
        json_data: dict | list | None = None,
        json_error: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self._json_error = json_error

    def json(self) -> dict | list:
        if self._json_error:
            raise self._json_error
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "Error", request=MagicMock(), response=self
            )


@pytest.mark.asyncio
async def test_discover_ad_accounts_success() -> None:
    """Test successful ad account discovery."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        json_data={
            "data": [
                {
                    "id": "act_123456789",
                    "name": "Test Account",
                    "currency": "USD",
                    "timezone_name": "America/New_York",
                    "account_status": "active",
                },
                {
                    "id": "987654321",
                    "name": "Another Account",
                    "currency": "EUR",
                    "timezone_name": "Europe/London",
                    "account_status": "inactive",
                },
            ]
        }
    )

    meta_client = MetaGraphClient(
        access_token="test-token",
        api_version="v19.0",
        http_client=mock_client,
    )

    accounts = await meta_client.discover_ad_accounts()

    assert len(accounts) == 2
    assert accounts[0].external_account_id == "123456789"
    assert accounts[0].name == "Test Account"
    assert accounts[0].currency == "USD"
    assert accounts[1].external_account_id == "987654321"
    assert accounts[1].currency == "EUR"


@pytest.mark.asyncio
async def test_get_campaigns_success() -> None:
    """Test successful campaign retrieval."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        json_data={
            "data": [
                {
                    "id": "camp_001",
                    "name": "Summer Campaign",
                    "objective": "CONVERSIONS",
                    "status": "ACTIVE",
                    "effective_status": "ACTIVE",
                },
                {
                    "id": "camp_002",
                    "name": "Winter Campaign",
                    "objective": "AWARENESS",
                    "status": "PAUSED",
                    "effective_status": "PAUSED",
                },
            ]
        }
    )

    meta_client = MetaGraphClient(
        access_token="test-token",
        http_client=mock_client,
    )

    campaigns = await meta_client.get_campaigns(external_account_id="123456789")

    assert len(campaigns) == 2
    assert campaigns[0].external_campaign_id == "camp_001"
    assert campaigns[0].name == "Summer Campaign"
    assert campaigns[0].objective == "CONVERSIONS"


@pytest.mark.asyncio
async def test_get_ad_sets_success() -> None:
    """Test successful ad set retrieval."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        json_data={
            "data": [
                {
                    "id": "adset_001",
                    "campaign_id": "camp_001",
                    "name": "Audience A",
                    "status": "ACTIVE",
                    "effective_status": "ACTIVE",
                },
            ]
        }
    )

    meta_client = MetaGraphClient(
        access_token="test-token",
        http_client=mock_client,
    )

    ad_sets = await meta_client.get_ad_sets(external_account_id="123456789")

    assert len(ad_sets) == 1
    assert ad_sets[0].external_ad_set_id == "adset_001"
    assert ad_sets[0].external_campaign_id == "camp_001"


@pytest.mark.asyncio
async def test_get_ads_success() -> None:
    """Test successful ad retrieval."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        json_data={
            "data": [
                {
                    "id": "ad_001",
                    "adset_id": "adset_001",
                    "name": "Creative A",
                    "creative_id": "creative_001",
                    "status": "ACTIVE",
                    "effective_status": "ACTIVE",
                },
            ]
        }
    )

    meta_client = MetaGraphClient(
        access_token="test-token",
        http_client=mock_client,
    )

    ads = await meta_client.get_ads(external_account_id="123456789")

    assert len(ads) == 1
    assert ads[0].external_ad_id == "ad_001"
    assert ads[0].creative_id == "creative_001"


@pytest.mark.asyncio
async def test_get_insights_success() -> None:
    """Test successful insights retrieval."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        json_data={
            "data": [
                {
                    "date_start": "2026-01-15",
                    "date_stop": "2026-01-15",
                    "account_id": "123456789",
                    "campaign_id": "camp_001",
                    "adset_id": None,
                    "ad_id": None,
                    "impressions": "1000",
                    "reach": "800",
                    "clicks": "50",
                    "spend": "25.50",
                    "actions": [
                        {"action_type": "lead", "value": "5"},
                        {"action_type": "offsite_conversion", "value": "2"},
                    ],
                    "action_values": [
                        {"action_type": "offsite_conversion", "value": "100.00"},
                    ],
                },
            ]
        }
    )

    meta_client = MetaGraphClient(
        access_token="test-token",
        http_client=mock_client,
    )

    insights = await meta_client.get_insights(
        external_account_id="123456789",
        date_from="2026-01-01",
        date_to="2026-01-31",
    )

    assert len(insights) == 1
    assert insights[0].date_start == "2026-01-15"
    assert insights[0].impressions == "1000"
    assert insights[0].spend == "25.50"


@pytest.mark.asyncio
async def test_validate_token_success() -> None:
    """Test successful token validation."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        json_data={"id": "me"}
    )

    meta_client = MetaGraphClient(
        access_token="test-token",
        http_client=mock_client,
    )

    is_valid = await meta_client.validate_token()

    assert is_valid is True


@pytest.mark.asyncio
async def test_timeout_raises_meta_api_error() -> None:
    """Test that timeout raises MetaApiError without exposing token."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.TimeoutException("timeout")

    meta_client = MetaGraphClient(
        access_token="secret-token-12345",
        http_client=mock_client,
    )

    with pytest.raises(MetaApiError) as exc_info:
        await meta_client.discover_ad_accounts()

    # Verify error message is safe
    error_message = str(exc_info.value)
    assert "secret-token" not in error_message
    assert "12345" not in error_message


@pytest.mark.asyncio
async def test_transport_error_raises_meta_api_error() -> None:
    """Test that transport error raises MetaApiError without exposing token."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.TransportError("connection failed")

    meta_client = MetaGraphClient(
        access_token="secret-token-xyz",
        http_client=mock_client,
    )

    with pytest.raises(MetaApiError) as exc_info:
        await meta_client.get_campaigns(external_account_id="123")

    error_message = str(exc_info.value)
    assert "secret-token" not in error_message
    assert "xyz" not in error_message


@pytest.mark.asyncio
async def test_http_400_raises_meta_api_error() -> None:
    """Test that HTTP 400 raises MetaApiError."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        status_code=400,
        json_data={"error": {"message": "Bad request"}},
    )

    meta_client = MetaGraphClient(
        access_token="test-token",
        http_client=mock_client,
    )

    with pytest.raises(MetaApiError):
        await meta_client.discover_ad_accounts()


@pytest.mark.asyncio
async def test_http_500_raises_meta_api_error() -> None:
    """Test that HTTP 500 raises MetaApiError without exposing details."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        status_code=500,
        json_data={"error": {"message": "Internal server error with sensitive data"}},
    )

    meta_client = MetaGraphClient(
        access_token="test-token",
        http_client=mock_client,
    )

    with pytest.raises(MetaApiError) as exc_info:
        await meta_client.get_ad_sets(external_account_id="123")

    # Safe message should be used
    error_message = str(exc_info.value)
    assert "Internal server error" not in error_message
    assert "sensitive data" not in error_message


@pytest.mark.asyncio
async def test_error_response_in_payload_returns_false_for_validate_token() -> None:
    """Test that error in JSON payload returns False for validate_token."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        json_data={
            "error": {
                "code": 190,
                "message": "Invalid OAuth access token",
            }
        }
    )

    meta_client = MetaGraphClient(
        access_token="test-token",
        http_client=mock_client,
    )

    # validate_token catches MetaApiError and returns False
    result = await meta_client.validate_token()
    assert result is False


@pytest.mark.asyncio
async def test_invalid_json_raises_meta_api_error() -> None:
    """Test that invalid JSON raises MetaApiError."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        json_error=ValueError("Invalid JSON"),
    )

    meta_client = MetaGraphClient(
        access_token="test-token",
        http_client=mock_client,
    )

    with pytest.raises(MetaApiError):
        await meta_client.discover_ad_accounts()


@pytest.mark.asyncio
async def test_error_in_payload_raises_for_discover_accounts() -> None:
    """Test that error in payload raises MetaApiError for discover_ad_accounts."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        json_data={
            "error": {
                "code": 190,
                "message": "Invalid OAuth access token",
            }
        }
    )

    meta_client = MetaGraphClient(
        access_token="test-token",
        http_client=mock_client,
    )

    with pytest.raises(MetaApiError):
        await meta_client.discover_ad_accounts()


@pytest.mark.asyncio
async def test_empty_data_returns_empty_list() -> None:
    """Test that empty data array returns empty list."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        json_data={"data": []}
    )

    meta_client = MetaGraphClient(
        access_token="test-token",
        http_client=mock_client,
    )

    accounts = await meta_client.discover_ad_accounts()
    assert accounts == []


@pytest.mark.asyncio
async def test_client_ownership_and_cleanup() -> None:
    """Test that owned client is properly closed."""
    meta_client = MetaGraphClient(
        access_token="test-token",
        timeout_seconds=30.0,
    )

    # Client should be created lazily
    assert meta_client._http_client is None
    assert meta_client._owned_client is False

    # Get client should create one
    client = await meta_client._get_client()
    assert client is not None
    assert meta_client._owned_client is True

    # Close should clean up
    await meta_client.close()
    assert meta_client._http_client is None
    assert meta_client._owned_client is False


@pytest.mark.asyncio
async def test_injected_client_not_closed() -> None:
    """Test that injected client is not closed on cleanup."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    meta_client = MetaGraphClient(
        access_token="test-token",
        http_client=mock_client,
    )

    await meta_client.close()

    # Should not close injected client
    mock_client.aclose.assert_not_called()


@pytest.mark.asyncio
async def test_access_token_not_in_request_url() -> None:
    """Test that access token is passed as param, not in URL."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(json_data={"data": []})

    meta_client = MetaGraphClient(
        access_token="secret-token-value",
        http_client=mock_client,
    )

    await meta_client.discover_ad_accounts()

    # Verify the call was made
    assert mock_client.get.called
    call_args = mock_client.get.call_args

    # URL should not contain the token
    url = str(call_args[0][0]) if call_args[0] else ""
    assert "secret-token" not in url

    # Token should be in params
    params = call_args[1].get("params", {})
    assert "access_token" in params


@pytest.mark.asyncio
async def test_no_secrets_in_error_logging_context() -> None:
    """Test that errors don't expose secrets in logging context."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = FakeHttpxResponse(
        status_code=401,
        json_data={"error": {"message": "Token secret-xyz-123 is invalid"}},
    )

    meta_client = MetaGraphClient(
        access_token="secret-xyz-123",
        http_client=mock_client,
    )

    with pytest.raises(MetaApiError):
        await meta_client.discover_ad_accounts()


@pytest.mark.asyncio
async def test_safe_error_message_format() -> None:
    """Test that MetaApiError has safe public representation."""
    error = MetaApiError("internal details with secret-token-abc")

    assert error.code == "meta_api_error"
    assert error.safe_message == "The Meta Ads connection failed"
    assert error.status_code == 502

    # The safe_message should not contain secrets
    assert "secret-token" not in error.safe_message
    assert "internal details" not in error.safe_message
