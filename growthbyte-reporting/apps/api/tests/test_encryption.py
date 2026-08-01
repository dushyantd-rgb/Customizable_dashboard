"""Tests for the encryption service."""

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


class TestEncryptionKeyValidation:
    """Tests for encryption key validation."""

    def test_none_key_raises_error(self) -> None:
        """Test that None key raises EncryptionKeyError."""
        with pytest.raises(EncryptionKeyError, match="cannot be None"):
            encrypt_token("test", None)  # type: ignore

    def test_empty_key_raises_error(self) -> None:
        """Test that empty key raises EncryptionKeyError."""
        with pytest.raises(EncryptionKeyError, match="cannot be empty"):
            encrypt_token("test", SecretStr(""))

    def test_invalid_base64_key_raises_error(self) -> None:
        """Test that non-base64 key raises EncryptionKeyError."""
        with pytest.raises(EncryptionKeyError, match="must be base64-encoded"):
            encrypt_token("test", SecretStr("not-base64!!!"))

    def test_wrong_size_key_raises_error(self) -> None:
        """Test that key with wrong size raises EncryptionKeyError."""
        # 16 bytes instead of 32
        short_key = base64.b64encode(os.urandom(16)).decode("utf-8")
        with pytest.raises(EncryptionKeyError, match="must decode to 32 bytes"):
            encrypt_token("test", SecretStr(short_key))

    def test_valid_key_works(self) -> None:
        """Test that valid key size works."""
        key = generate_valid_key()
        result = encrypt_token("test", key)
        assert result is not None
        assert len(result) > 0


class TestEncryptionDecryption:
    """Tests for encrypt/decrypt round-trip."""

    def test_encrypt_decrypt_round_trip(self) -> None:
        """Test that encryption followed by decryption returns original."""
        key = generate_valid_key()
        plaintext = "my-secret-token-12345"
        ciphertext = encrypt_token(plaintext, key)
        decrypted = decrypt_token(ciphertext, key)
        assert decrypted == plaintext

    def test_encrypt_different_tokens_same_key(self) -> None:
        """Test encrypting different tokens with same key."""
        key = generate_valid_key()
        token1 = "token-one"
        token2 = "token-two"
        ct1 = encrypt_token(token1, key)
        ct2 = encrypt_token(token2, key)
        assert decrypt_token(ct1, key) == token1
        assert decrypt_token(ct2, key) == token2

    def test_encrypt_same_token_produces_different_ciphertext(self) -> None:
        """Test that same token encrypted twice produces different ciphertext (random nonce)."""
        key = generate_valid_key()
        plaintext = "same-token"
        ct1 = encrypt_token(plaintext, key)
        ct2 = encrypt_token(plaintext, key)
        # Different due to random nonce, but both decrypt to same value
        assert ct1 != ct2
        assert decrypt_token(ct1, key) == plaintext
        assert decrypt_token(ct2, key) == plaintext

    def test_empty_string_returns_empty(self) -> None:
        """Test that empty string input returns empty string."""
        key = generate_valid_key()
        assert encrypt_token("", key) == ""
        assert decrypt_token("", key) == ""

    def test_special_characters(self) -> None:
        """Test with special characters."""
        key = generate_valid_key()
        special = "token-with-spaces and-symbols!@#$%^&*()_+-=[]{}|;':\",./<>?"
        ct = encrypt_token(special, key)
        decrypted = decrypt_token(ct, key)
        assert decrypted == special

    def test_unicode_characters(self) -> None:
        """Test with unicode characters."""
        key = generate_valid_key()
        unicode_str = "unicode-あ Ansił-中文-\U0001f600"
        ct = encrypt_token(unicode_str, key)
        decrypted = decrypt_token(ct, key)
        assert decrypted == unicode_str

    def test_long_token(self) -> None:
        """Test with a long token."""
        key = generate_valid_key()
        long_token = "a" * 1000
        ct = encrypt_token(long_token, key)
        decrypted = decrypt_token(ct, key)
        assert decrypted == long_token


class TestDecryptionErrors:
    """Tests for decryption error handling."""

    def test_wrong_key_fails(self) -> None:
        """Test that decrypting with wrong key fails."""
        key1 = generate_valid_key()
        key2 = generate_valid_key()
        ciphertext = encrypt_token("secret", key1)
        with pytest.raises(DecryptionError, match="invalid authentication tag"):
            decrypt_token(ciphertext, key2)

    def test_corrupted_ciphertext_fails(self) -> None:
        """Test that corrupted ciphertext fails."""
        key = generate_valid_key()
        ciphertext = encrypt_token("secret", key)
        # Corrupt the ciphertext
        corrupted = ciphertext[:-5] + ("aaaaa" if ciphertext[-5:] != "aaaaa" else "bbbbb")
        with pytest.raises(DecryptionError):
            decrypt_token(corrupted, key)

    def test_invalid_base64_ciphertext_fails(self) -> None:
        """Test that non-base64 ciphertext fails."""
        key = generate_valid_key()
        with pytest.raises(DecryptionError, match="Invalid ciphertext format"):
            decrypt_token("not-valid-base64!!!", key)

    def test_too_short_ciphertext_fails(self) -> None:
        """Test that too short ciphertext fails."""
        key = generate_valid_key()
        # Less than nonce size (12 bytes)
        short_ct = base64.b64encode(b"short").decode("utf-8")
        with pytest.raises(DecryptionError, match="Ciphertext too short"):
            decrypt_token(short_ct, key)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_type_validation_on_token(self) -> None:
        """Test that non-string token raises EncryptionError."""
        key = generate_valid_key()
        with pytest.raises(EncryptionError, match="Failed to encrypt token"):
            encrypt_token(12345, key)  # type: ignore

    def test_key_from_secret_str(self) -> None:
        """Test that key from SecretStr works correctly."""
        raw_key = base64.b64encode(os.urandom(32)).decode("utf-8")
        key = SecretStr(raw_key)
        plaintext = "test-token"
        ct = encrypt_token(plaintext, key)
        assert decrypt_token(ct, key) == plaintext

    def test_none_key_on_decrypt(self) -> None:
        """Test that None key raises EncryptionKeyError on decrypt."""
        key = generate_valid_key()
        ct = encrypt_token("test", key)
        with pytest.raises(EncryptionKeyError, match="cannot be None"):
            decrypt_token(ct, None)  # type: ignore


class TestIntegration:
    """Integration tests for the encryption service."""

    def test_multi_key_scenario(self) -> None:
        """Test scenario with multiple keys for different tokens."""
        key1 = generate_valid_key()
        key2 = generate_valid_key()

        # Encrypt tokens for different "clients" with different keys
        token1 = encrypt_token("client-a-token", key1)
        token2 = encrypt_token("client-b-token", key2)

        # Verify correct decryption with respective keys
        assert decrypt_token(token1, key1) == "client-a-token"
        assert decrypt_token(token2, key2) == "client-b-token"

        # Verify cross-decryption fails
        with pytest.raises(DecryptionError):
            decrypt_token(token1, key2)
        with pytest.raises(DecryptionError):
            decrypt_token(token2, key1)
