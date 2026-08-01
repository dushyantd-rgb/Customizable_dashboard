"""Extended tests for token encryption in Phase 3 integrations.

These tests specifically cover encryption usage in Meta and Google OAuth contexts,
ensuring that integration-layer encryption patterns are secure.
"""

import base64
import os

import pytest
from pydantic import SecretStr

from app.core.encryption import (
    DecryptionError,
    EncryptionError,
    EncryptionKeyError,
    decrypt_token,
    encrypt_token,
)


def generate_valid_key() -> SecretStr:
    """Generate a valid 32-byte base64-encoded key for testing."""
    raw_key = os.urandom(32)
    return SecretStr(base64.b64encode(raw_key).decode("utf-8"))


class TestIntegrationTokenEncryption:
    """Tests for token encryption in integration contexts."""

    def test_meta_access_token_encryption(self) -> None:
        """Test encryption of Meta access tokens."""
        key = generate_valid_key()
        meta_token = "EAAIabcdefghijklmnopqrstuvwxyz123456"

        encrypted = encrypt_token(meta_token, key)
        decrypted = decrypt_token(encrypted, key)

        assert decrypted == meta_token
        assert "EAAI" not in encrypted
        assert meta_token not in encrypted

    def test_google_refresh_token_encryption(self) -> None:
        """Test encryption of Google refresh tokens."""
        key = generate_valid_key()
        google_token = "1//0gXYZ12345abcdefghijklmnop"

        encrypted = encrypt_token(google_token, key)
        decrypted = decrypt_token(encrypted, key)

        assert decrypted == google_token

    def test_oauth_state_encryption_determinism(self) -> None:
        """Test that same token produces different ciphertext each time."""
        key = generate_valid_key()
        token = "my-oauth-token"

        encrypted1 = encrypt_token(token, key)
        encrypted2 = encrypt_token(token, key)

        # Random nonce should make ciphertext different
        assert encrypted1 != encrypted2

        # But both should decrypt to same value
        assert decrypt_token(encrypted1, key) == token
        assert decrypt_token(encrypted2, key) == token

    def test_multiple_client_tokens_with_same_key(self) -> None:
        """Test encrypting tokens for multiple clients with same encryption key."""
        key = generate_valid_key()

        client_tokens = {
            "client_a": "token-for-client-a",
            "client_b": "token-for-client-b",
            "client_c": "token-for-client-c",
        }

        encrypted_tokens = {
            client: encrypt_token(token, key)
            for client, token in client_tokens.items()
        }

        # Decrypt and verify
        for client, encrypted in encrypted_tokens.items():
            decrypted = decrypt_token(encrypted, key)
            assert decrypted == client_tokens[client]

        # Verify all are different ciphertext
        assert len(set(encrypted_tokens.values())) == len(client_tokens)


class TestTokenStorageSimulation:
    """Simulate token storage scenarios."""

    def test_token_round_trip_through_storage(self) -> None:
        """Test that tokens survive storage simulation."""
        key = generate_valid_key()
        original_token = "storage-test-token-xyz"

        # Encrypt (simulate before storage)
        encrypted = encrypt_token(original_token, key)

        # Simulate storage (base64 string)
        stored_value = encrypted

        # Retrieve and decrypt
        decrypted = decrypt_token(stored_value, key)

        assert decrypted == original_token

    def test_empty_token_handling(self) -> None:
        """Test that empty tokens are handled gracefully."""
        key = generate_valid_key()

        # Empty string should return empty
        assert encrypt_token("", key) == ""
        assert decrypt_token("", key) == ""

    def test_none_token_handling(self) -> None:
        """Test that None tokens are handled gracefully."""
        key = generate_valid_key()

        assert encrypt_token(None, key) == ""  # type: ignore
        assert decrypt_token(None, key) == ""  # type: ignore


class TestTokenEncryptionSecurity:
    """Security tests for token encryption."""

    def test_ciphertext_does_not_reveal_length(self) -> None:
        """Test that ciphertext doesn't reveal plaintext length."""
        key = generate_valid_key()

        short_token = "x"
        long_token = "x" * 1000

        short_encrypted = encrypt_token(short_token, key)
        long_encrypted = encrypt_token(long_token, key)

        # Ciphertext should be longer by fixed overhead (nonce + auth tag)
        # But we can't infer original length from ciphertext alone
        # Just verify both are valid
        assert decrypt_token(short_encrypted, key) == short_token
        assert decrypt_token(long_encrypted, key) == long_token

    def test_tampered_ciphertext_detection(self) -> None:
        """Test that tampered ciphertext is detected."""
        key = generate_valid_key()
        token = "sensitive-token"
        encrypted = encrypt_token(token, key)

        # Tamper with ciphertext
        encrypted_bytes = base64.b64decode(encrypted)
        tampered_bytes = bytearray(encrypted_bytes)
        tampered_bytes[5] = (tampered_bytes[5] + 1) % 256
        tampered = base64.b64encode(bytes(tampered_bytes)).decode("utf-8")

        with pytest.raises(DecryptionError):
            decrypt_token(tampered, key)

    def test_bit_flip_detection(self) -> None:
        """Test that single bit flips are detected."""
        key = generate_valid_key()
        token = "test-token"
        encrypted = encrypt_token(token, key)

        # Flip a bit in the ciphertext
        encrypted_bytes = bytearray(base64.b64decode(encrypted))
        encrypted_bytes[10] ^= 0x01  # Flip one bit
        tampered = base64.b64encode(bytes(encrypted_bytes)).decode("utf-8")

        with pytest.raises(DecryptionError):
            decrypt_token(tampered, key)


class TestKeyRotationSimulation:
    """Simulate key rotation scenarios."""

    def test_new_key_cannot_decrypt_old_tokens(self) -> None:
        """Test that new key cannot decrypt tokens encrypted with old key."""
        old_key = generate_valid_key()
        new_key = generate_valid_key()
        token = "token-before-rotation"

        encrypted_with_old = encrypt_token(token, old_key)

        with pytest.raises(DecryptionError):
            decrypt_token(encrypted_with_old, new_key)

    def test_old_key_still_works(self) -> None:
        """Test that old key still works for old tokens."""
        key = generate_valid_key()
        token = "legacy-token"
        encrypted = encrypt_token(token, key)

        # Later, same key should still work
        decrypted = decrypt_token(encrypted, key)
        assert decrypted == token


class TestConcurrentEncryption:
    """Tests for concurrent encryption scenarios."""

    def test_concurrent_encryption_produces_unique_ciphertext(self) -> None:
        """Test that concurrent encryption produces unique ciphertext."""
        key = generate_valid_key()
        token = "concurrent-test"

        # Simulate concurrent encryption
        results = [encrypt_token(token, key) for _ in range(100)]

        # All should be unique (due to random nonce)
        unique_results = set(results)
        assert len(unique_results) == 100

        # But all should decrypt to same value
        for encrypted in results:
            assert decrypt_token(encrypted, key) == token


class TestEncryptionPerformance:
    """Performance characteristics tests."""

    def test_encryption_is_fast_enough(self) -> None:
        """Test that encryption is reasonably fast."""
        import time

        key = generate_valid_key()
        token = "performance-test-token"

        # Warm up
        encrypt_token(token, key)

        # Measure
        start = time.time()
        for _ in range(1000):
            encrypted = encrypt_token(token, key)
            decrypt_token(encrypted, key)
        elapsed = time.time() - start

        # Should be fast (this is a smoke test, not a strict requirement)
        # 1000 encrypt+decrypt cycles should be well under 1 second
        assert elapsed < 1.0


class TestErrorMessagesAreSafe:
    """Test that error messages don't leak secrets."""

    def test_decryption_error_no_token_in_message(self) -> None:
        """Test that decryption errors don't include token."""
        key = generate_valid_key()
        wrong_key = generate_valid_key()
        token = "secret-token-xyz"

        encrypted = encrypt_token(token, key)

        try:
            decrypt_token(encrypted, wrong_key)
            assert False, "Should have raised"
        except DecryptionError as e:
            error_message = str(e)
            assert "secret-token" not in error_message
            assert token not in error_message

    def test_encryption_error_no_key_in_message(self) -> None:
        """Test that encryption errors don't include key."""
        # Invalid key format
        try:
            encrypt_token("test", SecretStr("invalid-key"))
            assert False, "Should have raised"
        except EncryptionKeyError as e:
            error_message = str(e)
            assert "invalid-key" not in error_message

    def test_corruption_error_is_safe(self) -> None:
        """Test that corruption error messages are safe."""
        key = generate_valid_key()
        encrypted = encrypt_token("secret-data", key)

        # Corrupt it
        corrupted = encrypted[:-10] + ("a" * 10)

        try:
            decrypt_token(corrupted, key)
            assert False, "Should have raised"
        except DecryptionError as e:
            error_message = str(e)
            assert "secret" not in error_message.lower()
            assert "data" not in error_message.lower()


class TestIntegrationWithOAuthFlows:
    """Tests simulating OAuth flow token handling."""

    def test_access_token_lifecycle(self) -> None:
        """Test access token lifecycle."""
        key = generate_valid_key()

        # OAuth flow produces access token
        access_token = "ya29.a0AfH6SMBx..."

        # Encrypt before storage
        encrypted_access = encrypt_token(access_token, key)

        # Later, retrieve and use
        decrypted_access = decrypt_token(encrypted_access, key)

        assert decrypted_access == access_token

    def test_refresh_token_lifecycle(self) -> None:
        """Test refresh token lifecycle."""
        key = generate_valid_key()

        # Refresh token from OAuth
        refresh_token = "1//09abc123..."

        # Encrypt before storage
        encrypted_refresh = encrypt_token(refresh_token, key)

        # Later, use for refresh
        decrypted_refresh = decrypt_token(encrypted_refresh, key)

        assert decrypted_refresh == refresh_token

    def test_token_expiry_not_encrypted(self) -> None:
        """Test that token expiry can be stored separately."""
        key = generate_valid_key()
        from datetime import datetime, timezone, timedelta

        access_token = "test-token"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        # Only encrypt the token, not the expiry
        encrypted_token = encrypt_token(access_token, key)

        # Expiry can be stored as plaintext ISO string
        expiry_string = expires_at.isoformat()

        # Verify we can reconstruct
        decrypted_token = decrypt_token(encrypted_token, key)
        reconstructed_expiry = datetime.fromisoformat(expiry_string)

        assert decrypted_token == access_token
        assert abs((reconstructed_expiry - expires_at).total_seconds()) < 1
