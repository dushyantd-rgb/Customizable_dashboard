"""Token encryption service using AES-256-GCM."""

import base64
import logging
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr

logger = logging.getLogger(__name__)

# AES-256-GCM requires a 12-byte nonce for optimal performance and security
NONCE_SIZE = 12
# AES-256 requires a 32-byte key
KEY_SIZE = 32


class EncryptionKeyError(ValueError):
    """Raised when the encryption key is invalid."""

    pass


class EncryptionError(Exception):
    """Raised when encryption fails."""

    pass


class DecryptionError(Exception):
    """Raised when decryption fails."""

    pass


def _validate_key(key: SecretStr) -> bytes:
    """Validate and decode the encryption key.

    Args:
        key: The encryption key as a SecretStr.

    Returns:
        The decoded 32-byte key.

    Raises:
        EncryptionKeyError: If the key is None, empty, or not 32 bytes.
    """
    if key is None:
        raise EncryptionKeyError("Encryption key cannot be None")

    raw_key = key.get_secret_value()
    if not raw_key:
        raise EncryptionKeyError("Encryption key cannot be empty")

    try:
        decoded_key = base64.b64decode(raw_key)
    except Exception as e:
        raise EncryptionKeyError("Encryption key must be base64-encoded") from e

    if len(decoded_key) != KEY_SIZE:
        raise EncryptionKeyError(
            f"Encryption key must decode to {KEY_SIZE} bytes, got {len(decoded_key)}"
        )

    return decoded_key


def encrypt_token(plaintext: str, key: SecretStr) -> str:
    """Encrypt a token using AES-256-GCM.

    Args:
        plaintext: The plaintext string to encrypt.
        key: The encryption key as a SecretStr (base64-encoded 32 bytes).

    Returns:
        Base64-encoded ciphertext containing nonce and encrypted data.

    Raises:
        EncryptionKeyError: If the key is invalid.
        EncryptionError: If encryption fails.
    """
    # Handle None/empty gracefully
    if plaintext is None or plaintext == "":
        return ""

    # Validate the key first
    try:
        decoded_key = _validate_key(key)
    except EncryptionKeyError:
        raise

    # Generate a random nonce (12 bytes for AES-GCM)
    nonce = os.urandom(NONCE_SIZE)

    try:
        aesgcm = AESGCM(decoded_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    except Exception as e:
        logger.error("Encryption failed: %s", str(e))
        raise EncryptionError("Failed to encrypt token") from e

    # Combine nonce + ciphertext and encode as base64
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode("utf-8")


def decrypt_token(ciphertext: str, key: SecretStr) -> str:
    """Decrypt a token using AES-256-GCM.

    Args:
        ciphertext: Base64-encoded ciphertext containing nonce and encrypted data.
        key: The encryption key as a SecretStr (base64-encoded 32 bytes).

    Returns:
        The decrypted plaintext string.

    Raises:
        EncryptionKeyError: If the key is invalid.
        DecryptionError: If decryption fails (wrong key, corrupted data, etc.).
    """
    # Handle None/empty gracefully
    if ciphertext is None or ciphertext == "":
        return ""

    # Validate the key first
    try:
        decoded_key = _validate_key(key)
    except EncryptionKeyError:
        raise

    # Decode the combined nonce + ciphertext
    try:
        combined = base64.b64decode(ciphertext)
    except Exception as e:
        logger.error("Failed to base64 decode ciphertext: %s", str(e))
        raise DecryptionError("Invalid ciphertext format") from e

    # Extract nonce (first 12 bytes) and ciphertext (rest)
    if len(combined) < NONCE_SIZE + 1:  # At least nonce + 1 byte of ciphertext
        raise DecryptionError("Ciphertext too short")

    nonce = combined[:NONCE_SIZE]
    encrypted_data = combined[NONCE_SIZE:]

    try:
        aesgcm = AESGCM(decoded_key)
        plaintext = aesgcm.decrypt(nonce, encrypted_data, None)
        return plaintext.decode("utf-8")
    except InvalidTag as e:
        logger.error("Decryption failed: authentication tag verification failed")
        raise DecryptionError("Failed to decrypt token: invalid authentication tag") from e
    except UnicodeDecodeError as e:
        logger.error("Decrypted data is not valid UTF-8: %s", str(e))
        raise DecryptionError("Decrypted data is not valid UTF-8") from e
    except Exception as e:
        logger.error("Decryption failed: %s", str(e))
        raise DecryptionError("Failed to decrypt token") from e
