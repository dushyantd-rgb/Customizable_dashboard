"""Google OAuth 2.0 flow implementation."""

import base64
import hashlib
import hmac
import logging
import os
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import SecretStr

from app.core.encryption import decrypt_token, encrypt_token
from app.integrations.google.models import (
    GoogleOAuthState,
    GoogleTokenResponse,
)

logger = logging.getLogger(__name__)

# OAuth endpoints for Google
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Required scopes for Google Sheets (read-only)
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]


class GoogleOAuthError(Exception):
    """Error during Google OAuth flow."""

    def __init__(self, message: str = "Google OAuth failed") -> None:
        super().__init__(message)


class GoogleOAuthStateError(GoogleOAuthError):
    """Invalid or expired OAuth state."""

    def __init__(self) -> None:
        super().__init__("Invalid OAuth state")


class GoogleTokenExchangeError(GoogleOAuthError):
    """Failed to exchange authorization code for tokens."""

    def __init__(self) -> None:
        super().__init__("Failed to exchange authorization code")


def generate_oauth_state(client_id: str, state_hmac_key: SecretStr) -> str:
    """Generate a URL-safe OAuth state parameter.

    Creates a state containing client_id and a random nonce,
    signed with HMAC-SHA256 for validation.

    Args:
        client_id: The client identifier.
        state_hmac_key: HMAC key for signing state (from settings).

    Returns:
        URL-safe base64-encoded state string.
    """
    # Generate random nonce for CSRF protection
    nonce = secrets.token_urlsafe(16)

    # Create HMAC signature
    message = f"{client_id}:{nonce}"
    hmac_key = state_hmac_key.get_secret_value().encode("utf-8")
    signature = hmac.new(
        hmac_key,
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # Create state object
    state_obj = GoogleOAuthState(
        client_id=client_id,
        nonce=nonce,
        hmac=signature,
    )

    # Encode as URL-safe base64
    state_json = state_obj.model_dump_json()
    state_bytes = state_json.encode("utf-8")
    return base64.urlsafe_b64encode(state_bytes).decode("utf-8")


def validate_oauth_state(state: str, state_hmac_key: SecretStr) -> str:
    """Validate and decode an OAuth state parameter.

    Verifies HMAC signature and returns the client_id.

    Args:
        state: URL-safe base64-encoded state string.
        state_hmac_key: HMAC key for validation (from settings).

    Returns:
        The client_id from the state.

    Raises:
        GoogleOAuthStateError: If state is invalid.
    """
    try:
        # Decode base64
        state_bytes = base64.urlsafe_b64decode(state.encode("utf-8"))
        state_json = state_bytes.decode("utf-8")

        # Parse state object
        state_obj = GoogleOAuthState.model_validate_json(state_json)

        # Verify HMAC
        message = f"{state_obj.client_id}:{state_obj.nonce}"
        hmac_key = state_hmac_key.get_secret_value().encode("utf-8")
        expected_hmac = hmac.new(
            hmac_key,
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(state_obj.hmac, expected_hmac):
            logger.warning("OAuth state HMAC verification failed")
            raise GoogleOAuthStateError

        return state_obj.client_id

    except Exception as error:
        logger.warning("OAuth state validation failed: %s", type(error).__name__)
        raise GoogleOAuthStateError from error


def get_authorization_url(
    client_id: str,
    redirect_uri: str,
    settings: Any,
) -> str:
    """Generate the Google OAuth authorization URL.

    Args:
        client_id: The application client ID.
        redirect_uri: Callback URL after authorization.
        settings: Application settings with Google OAuth config.

    Returns:
        Full authorization URL to redirect user to.
    """
    if (
        not settings.google.oauth_client_id
        or not settings.google.oauth_client_id.get_secret_value()
    ):
        raise GoogleOAuthError("Google OAuth client ID not configured")

    # Generate state parameter
    if not settings.token_encryption_key:
        raise GoogleOAuthError("Token encryption key not configured")

    state = generate_oauth_state(
        client_id=client_id,
        state_hmac_key=settings.token_encryption_key,
    )

    # Build authorization URL
    params = {
        "client_id": settings.google.oauth_client_id.get_secret_value(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",  # Request refresh token
        "prompt": "consent",  # Force consent screen for refresh token
        "state": state,
    }

    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(
    code: str,
    redirect_uri: str,
    settings: Any,
    http_client: httpx.AsyncClient | None = None,
) -> GoogleTokenResponse:
    """Exchange authorization code for access tokens.

    Args:
        code: Authorization code from Google.
        redirect_uri: Same redirect URI used in authorization.
        settings: Application settings.
        http_client: Optional HTTP client for testing.

    Returns:
        GoogleTokenResponse with encrypted tokens.

    Raises:
        GoogleTokenExchangeError: If exchange fails.
    """
    if (
        not settings.google.oauth_client_id
        or not settings.google.oauth_client_secret
    ):
        raise GoogleOAuthError("Google OAuth credentials not configured")

    client_id = settings.google.oauth_client_id.get_secret_value()
    client_secret = settings.google.oauth_client_secret.get_secret_value()

    # Prepare token request
    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    owned_client = False
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
        owned_client = True

    try:
        response = await http_client.post(
            GOOGLE_TOKEN_URL,
            data=token_data,
            headers={"Accept": "application/json"},
        )

        if response.status_code >= 400:
            logger.warning(
                "Google token exchange failed: status=%d",
                response.status_code,
            )
            raise GoogleTokenExchangeError

        payload = response.json()

        if "error" in payload:
            logger.warning("Google token exchange error: %s", payload.get("error"))
            raise GoogleTokenExchangeError

        # Calculate expiration time
        expires_in = payload.get("expires_in", 3600)
        from datetime import datetime, timezone, timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Encrypt tokens before returning
        if not settings.token_encryption_key:
            raise GoogleOAuthError("Token encryption key not configured")

        encrypted_access_token = encrypt_token(
            payload["access_token"],
            settings.token_encryption_key,
        )
        encrypted_refresh_token = None
        if payload.get("refresh_token"):
            encrypted_refresh_token = encrypt_token(
                payload["refresh_token"],
                settings.token_encryption_key,
            )

        return GoogleTokenResponse(
            access_token=encrypted_access_token,
            refresh_token=encrypted_refresh_token,
            expires_at=expires_at,
            token_type=payload.get("token_type", "Bearer"),
            scope=payload.get("scope"),
        )

    except (httpx.TimeoutException, httpx.TransportError) as error:
        logger.warning("Google token exchange network error: %s", type(error).__name__)
        raise GoogleTokenExchangeError from error

    finally:
        if owned_client:
            await http_client.aclose()


async def refresh_access_token(
    refresh_token: str,
    settings: Any,
    http_client: httpx.AsyncClient | None = None,
) -> GoogleTokenResponse:
    """Refresh an expired access token.

    Args:
        refresh_token: Encrypted refresh token.
        settings: Application settings.
        http_client: Optional HTTP client for testing.

    Returns:
        GoogleTokenResponse with new access token.

    Raises:
        GoogleTokenExchangeError: If refresh fails.
    """
    if (
        not settings.google.oauth_client_id
        or not settings.google.oauth_client_secret
    ):
        raise GoogleOAuthError("Google OAuth credentials not configured")

    if not settings.token_encryption_key:
        raise GoogleOAuthError("Token encryption key not configured")

    # Decrypt refresh token
    decrypted_refresh_token = decrypt_token(
        refresh_token,
        settings.token_encryption_key,
    )

    client_id = settings.google.oauth_client_id.get_secret_value()
    client_secret = settings.google.oauth_client_secret.get_secret_value()

    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": decrypted_refresh_token,
        "grant_type": "refresh_token",
    }

    owned_client = False
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
        owned_client = True

    try:
        response = await http_client.post(
            GOOGLE_TOKEN_URL,
            data=token_data,
            headers={"Accept": "application/json"},
        )

        if response.status_code >= 400:
            logger.warning("Google token refresh failed: status=%d", response.status_code)
            raise GoogleTokenExchangeError

        payload = response.json()

        if "error" in payload:
            logger.warning("Google token refresh error: %s", payload.get("error"))
            raise GoogleTokenExchangeError

        # Calculate expiration time
        expires_in = payload.get("expires_in", 3600)
        from datetime import datetime, timezone, timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Encrypt new access token
        encrypted_access_token = encrypt_token(
            payload["access_token"],
            settings.token_encryption_key,
        )

        return GoogleTokenResponse(
            access_token=encrypted_access_token,
            refresh_token=refresh_token,  # Keep original refresh token
            expires_at=expires_at,
            token_type=payload.get("token_type", "Bearer"),
            scope=payload.get("scope"),
        )

    except (httpx.TimeoutException, httpx.TransportError) as error:
        logger.warning("Google token refresh network error: %s", type(error).__name__)
        raise GoogleTokenExchangeError from error

    finally:
        if owned_client:
            await http_client.aclose()
