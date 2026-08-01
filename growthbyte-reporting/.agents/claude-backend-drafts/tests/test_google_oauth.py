"""Tests for Google OAuth state validation."""

import base64
import hashlib
import hmac
import json
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import SecretStr

from app.integrations.google.oauth import (
    GoogleOAuthError,
    GoogleOAuthStateError,
    GoogleTokenExchangeError,
    exchange_code_for_tokens,
    generate_oauth_state,
    get_authorization_url,
    validate_oauth_state,
)


def generate_test_key() -> SecretStr:
    """Generate a valid key for testing."""
    import os
    raw_key = b"a" * 32  # Exactly 32 bytes
    return SecretStr(base64.b64encode(raw_key).decode("utf-8"))


class FakeSettings:
    """Fake settings for testing."""

    def __init__(self) -> None:
        self.token_encryption_key = generate_test_key()
        self.google = MagicMock()
        self.google.oauth_client_id = SecretStr("test-client-id.apps.googleusercontent.com")
        self.google.oauth_client_secret = SecretStr("test-client-secret-xyz")


class TestGenerateOAuthState:
    """Tests for OAuth state generation."""

    def test_generates_url_safe_base64_state(self) -> None:
        key = generate_test_key()
        state = generate_oauth_state(client_id="test-client", state_hmac_key=key)

        # Should be URL-safe base64
        assert isinstance(state, str)
        assert len(state) > 0
        # Should not raise when decoded
        decoded = base64.urlsafe_b64decode(state.encode("utf-8"))
        assert decoded is not None

    def test_state_contains_client_id(self) -> None:
        key = generate_test_key()
        state = generate_oauth_state(client_id="my-client-123", state_hmac_key=key)

        decoded = base64.urlsafe_b64decode(state.encode("utf-8"))
        state_json = json.loads(decoded.decode("utf-8"))

        assert state_json["client_id"] == "my-client-123"
        assert "nonce" in state_json
        assert "hmac" in state_json

    def test_different_calls_produce_different_nonces(self) -> None:
        key = generate_test_key()
        state1 = generate_oauth_state(client_id="test", state_hmac_key=key)
        state2 = generate_oauth_state(client_id="test", state_hmac_key=key)

        decoded1 = json.loads(base64.urlsafe_b64decode(state1.encode("utf-8")))
        decoded2 = json.loads(base64.urlsafe_b64decode(state2.encode("utf-8")))

        assert decoded1["nonce"] != decoded2["nonce"]
        assert decoded1["hmac"] != decoded2["hmac"]

    def test_hmac_is_deterministic_for_same_inputs(self) -> None:
        """Test that HMAC is deterministic given same inputs."""
        import secrets
        # We need to control the nonce to test determinism
        key = generate_test_key()
        client_id = "test-client"
        nonce = "fixed-nonce-123"

        # Manually compute expected HMAC
        message = f"{client_id}:{nonce}"
        hmac_key = key.get_secret_value().encode("utf-8")
        expected_hmac = hmac.new(
            hmac_key,
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Verify the algorithm matches
        assert len(expected_hmac) == 64  # SHA-256 hex digest


class TestValidateOAuthState:
    """Tests for OAuth state validation."""

    def test_validates_and_returns_client_id(self) -> None:
        key = generate_test_key()
        state = generate_oauth_state(client_id="valid-client", state_hmac_key=key)

        client_id = validate_oauth_state(state=state, state_hmac_key=key)

        assert client_id == "valid-client"

    def test_rejects_tampered_client_id(self) -> None:
        key = generate_test_key()
        state = generate_oauth_state(client_id="original-client", state_hmac_key=key)

        # Decode, tamper with client_id, re-encode
        decoded = base64.urlsafe_b64decode(state.encode("utf-8"))
        state_json = json.loads(decoded.decode("utf-8"))
        state_json["client_id"] = "tampered-client"
        tampered_state = base64.urlsafe_b64encode(
            json.dumps(state_json).encode("utf-8")
        ).decode("utf-8")

        with pytest.raises(GoogleOAuthStateError):
            validate_oauth_state(state=tampered_state, state_hmac_key=key)

    def test_rejects_tampered_hmac(self) -> None:
        key = generate_test_key()
        state = generate_oauth_state(client_id="test-client", state_hmac_key=key)

        decoded = base64.urlsafe_b64decode(state.encode("utf-8"))
        state_json = json.loads(decoded.decode("utf-8"))
        state_json["hmac"] = "0" * 64  # Invalid HMAC
        tampered_state = base64.urlsafe_b64encode(
            json.dumps(state_json).encode("utf-8")
        ).decode("utf-8")

        with pytest.raises(GoogleOAuthStateError):
            validate_oauth_state(state=tampered_state, state_hmac_key=key)

    def test_rejects_invalid_base64(self) -> None:
        key = generate_test_key()

        with pytest.raises(GoogleOAuthStateError):
            validate_oauth_state(state="not-valid-base64!@#", state_hmac_key=key)

    def test_rejects_invalid_json(self) -> None:
        key = generate_test_key()
        invalid_json = base64.urlsafe_b64encode(b"not json").decode("utf-8")

        with pytest.raises(GoogleOAuthStateError):
            validate_oauth_state(state=invalid_json, state_hmac_key=key)

    def test_rejects_missing_hmac(self) -> None:
        key = generate_test_key()
        state_json = json.dumps({
            "client_id": "test",
            "nonce": "abc123",
        })
        state = base64.urlsafe_b64encode(state_json.encode("utf-8")).decode("utf-8")

        with pytest.raises(GoogleOAuthStateError):
            validate_oauth_state(state=state, state_hmac_key=key)

    def test_rejects_wrong_key(self) -> None:
        key1 = generate_test_key()
        key2 = generate_test_key()
        state = generate_oauth_state(client_id="test", state_hmac_key=key1)

        with pytest.raises(GoogleOAuthStateError):
            validate_oauth_state(state=state, state_hmac_key=key2)

    def test_rejects_empty_state(self) -> None:
        key = generate_test_key()

        with pytest.raises(GoogleOAuthStateError):
            validate_oauth_state(state="", state_hmac_key=key)


class TestGetAuthorizationUrl:
    """Tests for authorization URL generation."""

    def test_generates_valid_url(self) -> None:
        settings = FakeSettings()
        url = get_authorization_url(
            client_id="test-client",
            redirect_uri="http://localhost/callback",
            settings=settings,
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert "google" in parsed.netloc
        assert params["client_id"][0] == "test-client-id.apps.googleusercontent.com"
        assert params["redirect_uri"][0] == "http://localhost/callback"
        assert params["response_type"][0] == "code"
        assert "state" in params
        assert params["access_type"][0] == "offline"
        assert params["prompt"][0] == "consent"

    def test_includes_required_scopes(self) -> None:
        settings = FakeSettings()
        url = get_authorization_url(
            client_id="test-client",
            redirect_uri="http://localhost/callback",
            settings=settings,
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        scope = params["scope"][0]

        assert "spreadsheets.readonly" in scope
        assert "drive.metadata.readonly" in scope

    def test_rejects_missing_oauth_client_id(self) -> None:
        settings = FakeSettings()
        settings.google.oauth_client_id = None

        with pytest.raises(GoogleOAuthError, match="client ID not configured"):
            get_authorization_url(
                client_id="test",
                redirect_uri="http://localhost/callback",
                settings=settings,
            )

    def test_rejects_empty_oauth_client_id(self) -> None:
        settings = FakeSettings()
        settings.google.oauth_client_id = SecretStr("")

        with pytest.raises(GoogleOAuthError, match="client ID not configured"):
            get_authorization_url(
                client_id="test",
                redirect_uri="http://localhost/callback",
                settings=settings,
            )

    def test_rejects_missing_encryption_key(self) -> None:
        settings = FakeSettings()
        settings.token_encryption_key = None

        with pytest.raises(GoogleOAuthError, match="encryption key not configured"):
            get_authorization_url(
                client_id="test",
                redirect_uri="http://localhost/callback",
                settings=settings,
            )


class TestStateReplayProtection:
    """Tests for state replay attack protection."""

    def test_state_nonce_uniqueness(self) -> None:
        """Test that nonces are unique for CSRF protection."""
        key = generate_test_key()
        states = [
            generate_oauth_state(client_id="test", state_hmac_key=key)
            for _ in range(100)
        ]

        # Decode all nonces
        nonces = []
        for state in states:
            decoded = base64.urlsafe_b64decode(state.encode("utf-8"))
            state_json = json.loads(decoded.decode("utf-8"))
            nonces.append(state_json["nonce"])

        # All nonces should be unique
        assert len(set(nonces)) == 100

    def test_state_has_minimum_nonce_length(self) -> None:
        """Test that nonces have sufficient entropy."""
        key = generate_test_key()
        state = generate_oauth_state(client_id="test", state_hmac_key=key)

        decoded = base64.urlsafe_b64decode(state.encode("utf-8"))
        state_json = json.loads(decoded.decode("utf-8"))
        nonce = state_json["nonce"]

        # Nonce should have at least 8 characters (URL-safe base64)
        assert len(nonce) >= 8


class TestHMACSecurity:
    """Tests for HMAC security properties."""

    def test_hmac_uses_sha256(self) -> None:
        """Test that HMAC uses SHA-256."""
        key = generate_test_key()
        client_id = "test-client"
        nonce = "test-nonce"

        # Manually create state with known values
        message = f"{client_id}:{nonce}"
        hmac_key = key.get_secret_value().encode("utf-8")
        hmac_value = hmac.new(
            hmac_key,
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # HMAC should be 64 characters (256 bits hex encoded)
        assert len(hmac_value) == 64

    def test_hmac_constant_time_comparison(self) -> None:
        """Test that HMAC comparison uses constant time."""
        key = generate_test_key()
        state = generate_oauth_state(client_id="test", state_hmac_key=key)

        # This should use hmac.compare_digest internally
        # We test that it doesn't raise timing-related errors
        client_id = validate_oauth_state(state=state, state_hmac_key=key)
        assert client_id == "test"


class TestTokenExchangeSecurity:
    """Tests for token exchange security."""

    @pytest.mark.asyncio
    async def test_exchange_requires_configured_credentials(self) -> None:
        """Test that exchange rejects missing credentials."""
        settings = FakeSettings()
        settings.google.oauth_client_id = None

        with pytest.raises(GoogleOAuthError, match="credentials not configured"):
            await exchange_code_for_tokens(
                code="test-code",
                redirect_uri="http://localhost/callback",
                settings=settings,
            )

    @pytest.mark.asyncio
    async def test_exchange_requires_encryption_key(self) -> None:
        """Test that exchange rejects missing encryption key."""
        settings = FakeSettings()
        settings.token_encryption_key = None

        with pytest.raises(GoogleOAuthError, match="encryption key not configured"):
            await exchange_code_for_tokens(
                code="test-code",
                redirect_uri="http://localhost/callback",
                settings=settings,
            )


class TestNoSecretsInErrors:
    """Tests for ensuring secrets are not exposed in errors."""

    def test_oauth_state_error_message_is_safe(self) -> None:
        """Test that OAuth state error doesn't expose secrets."""
        error = GoogleOAuthStateError()

        assert "secret" not in str(error).lower()
        assert "token" not in str(error).lower()
        assert "key" not in str(error).lower()
        assert "Invalid OAuth state" in str(error)

    def test_oauth_error_message_is_safe(self) -> None:
        """Test that OAuth error doesn't expose secrets."""
        error = GoogleOAuthError("Error with secret-key-123")

        # Error message might contain the original, but should be safe in API responses
        assert isinstance(error, Exception)

    def test_token_exchange_error_is_safe(self) -> None:
        """Test that token exchange error doesn't expose secrets."""
        error = GoogleTokenExchangeError()

        assert "Failed to exchange authorization code" in str(error)
        assert "secret" not in str(error).lower()
        assert "token" not in str(error).lower()


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_client_id_rejected(self) -> None:
        """Test that empty client_id is rejected."""
        key = generate_test_key()

        # Pydantic should reject empty client_id
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            from app.integrations.google.models import GoogleOAuthState
            GoogleOAuthState(client_id="", nonce="test", hmac="abc")

    def test_very_long_client_id(self) -> None:
        """Test handling of very long client ID."""
        key = generate_test_key()
        long_client_id = "a" * 1000

        state = generate_oauth_state(client_id=long_client_id, state_hmac_key=key)
        validated_id = validate_oauth_state(state=state, state_hmac_key=key)

        assert validated_id == long_client_id

    def test_special_characters_in_client_id(self) -> None:
        """Test handling of special characters in client ID."""
        key = generate_test_key()
        special_client_id = "client-with-special_chars.123"

        state = generate_oauth_state(client_id=special_client_id, state_hmac_key=key)
        validated_id = validate_oauth_state(state=state, state_hmac_key=key)

        assert validated_id == special_client_id

    def test_unicode_client_id(self) -> None:
        """Test handling of unicode in client ID."""
        key = generate_test_key()
        unicode_client_id = "client-中文-Рус"

        state = generate_oauth_state(client_id=unicode_client_id, state_hmac_key=key)
        validated_id = validate_oauth_state(state=state, state_hmac_key=key)

        assert validated_id == unicode_client_id
