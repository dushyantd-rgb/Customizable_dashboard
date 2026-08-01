"""Secret-safe Google OAuth helpers for the read-only Sheets connector."""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import SecretStr

from app.core.errors import SafeApplicationError
from app.integrations.google.models import GoogleOAuthState, GoogleTokenResponse

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
)
STATE_MAX_AGE_SECONDS = 600


class GoogleOAuthError(SafeApplicationError):
    code = "google_oauth_error"
    safe_message = "The Google connection could not be completed"
    status_code = 502


class GoogleOAuthStateError(GoogleOAuthError):
    code = "invalid_google_oauth_state"
    safe_message = "The Google connection request is invalid or expired"
    status_code = 400


class GoogleTokenExchangeError(GoogleOAuthError):
    code = "google_token_exchange_failed"
    safe_message = "Google did not accept the connection request"


def generate_oauth_state(client_id: str, state_hmac_key: SecretStr) -> str:
    issued_at = int(time.time())
    nonce = secrets.token_urlsafe(24)
    signature = _state_signature(
        client_id=client_id,
        nonce=nonce,
        issued_at=issued_at,
        key=state_hmac_key,
    )
    payload = GoogleOAuthState(
        client_id=client_id,
        nonce=nonce,
        issued_at=issued_at,
        hmac=signature,
    ).model_dump_json()
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def validate_oauth_state(
    state: str,
    state_hmac_key: SecretStr,
    *,
    now: int | None = None,
) -> str:
    try:
        padded = state + "=" * (-len(state) % 4)
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
        state_value = GoogleOAuthState.model_validate_json(decoded)
        current_time = int(time.time()) if now is None else now
        if state_value.issued_at > current_time + 30:
            raise GoogleOAuthStateError
        if current_time - state_value.issued_at > STATE_MAX_AGE_SECONDS:
            raise GoogleOAuthStateError
        expected = _state_signature(
            client_id=state_value.client_id,
            nonce=state_value.nonce,
            issued_at=state_value.issued_at,
            key=state_hmac_key,
        )
        if not hmac.compare_digest(state_value.hmac, expected):
            raise GoogleOAuthStateError
        return state_value.client_id
    except GoogleOAuthStateError:
        raise
    except Exception as error:
        logger.warning("Google OAuth state validation failed")
        raise GoogleOAuthStateError from error


def get_authorization_url(*, client_id: str, redirect_uri: str, settings: Any) -> str:
    oauth_client_id = settings.google.oauth_client_id
    state_key = settings.token_encryption_key
    if oauth_client_id is None or state_key is None:
        raise GoogleOAuthError
    params = {
        "client_id": oauth_client_id.get_secret_value(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "false",
        "state": generate_oauth_state(client_id, state_key),
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(
    *,
    code: str,
    redirect_uri: str,
    settings: Any,
    http_client: httpx.AsyncClient | None = None,
) -> GoogleTokenResponse:
    oauth_client_id = settings.google.oauth_client_id
    oauth_client_secret = settings.google.oauth_client_secret
    if oauth_client_id is None or oauth_client_secret is None:
        raise GoogleOAuthError
    payload = await _token_request(
        {
            "client_id": oauth_client_id.get_secret_value(),
            "client_secret": oauth_client_secret.get_secret_value(),
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        http_client=http_client,
    )
    refresh = payload.get("refresh_token")
    return GoogleTokenResponse(
        access_token=SecretStr(_required_token(payload, "access_token")),
        refresh_token=SecretStr(refresh) if isinstance(refresh, str) and refresh else None,
        expires_at=_expiry(payload),
        token_type=str(payload.get("token_type", "Bearer")),
        scope=str(payload["scope"]) if payload.get("scope") is not None else None,
    )


async def refresh_access_token(
    *,
    refresh_token: SecretStr,
    settings: Any,
    http_client: httpx.AsyncClient | None = None,
) -> GoogleTokenResponse:
    oauth_client_id = settings.google.oauth_client_id
    oauth_client_secret = settings.google.oauth_client_secret
    if oauth_client_id is None or oauth_client_secret is None:
        raise GoogleOAuthError
    payload = await _token_request(
        {
            "client_id": oauth_client_id.get_secret_value(),
            "client_secret": oauth_client_secret.get_secret_value(),
            "refresh_token": refresh_token.get_secret_value(),
            "grant_type": "refresh_token",
        },
        http_client=http_client,
    )
    return GoogleTokenResponse(
        access_token=SecretStr(_required_token(payload, "access_token")),
        refresh_token=refresh_token,
        expires_at=_expiry(payload),
        token_type=str(payload.get("token_type", "Bearer")),
        scope=str(payload["scope"]) if payload.get("scope") is not None else None,
    )


def _state_signature(*, client_id: str, nonce: str, issued_at: int, key: SecretStr) -> str:
    message = f"{client_id}:{nonce}:{issued_at}".encode()
    return hmac.new(
        key.get_secret_value().encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


async def _token_request(
    data: dict[str, str],
    *,
    http_client: httpx.AsyncClient | None,
) -> dict[str, Any]:
    owned_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
    try:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data=data,
            headers={"Accept": "application/json"},
        )
        if response.status_code >= 400:
            logger.warning("Google token request failed", extra={"status": response.status_code})
            raise GoogleTokenExchangeError
        result = response.json()
        if not isinstance(result, dict) or result.get("error"):
            raise GoogleTokenExchangeError
        return result
    except GoogleOAuthError:
        raise
    except (
        httpx.TimeoutException,
        httpx.TransportError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        logger.warning("Google token request was unavailable")
        raise GoogleTokenExchangeError from error
    finally:
        if owned_client:
            await client.aclose()


def _required_token(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise GoogleTokenExchangeError
    return value


def _expiry(payload: dict[str, Any]) -> datetime:
    try:
        expires_in = max(1, int(payload.get("expires_in", 3600)))
    except (TypeError, ValueError) as error:
        raise GoogleTokenExchangeError from error
    return datetime.now(UTC) + timedelta(seconds=expires_in)
