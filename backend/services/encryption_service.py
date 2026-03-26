"""
AES-256-GCM encryption service for sensitive data (connector configs, PII).
Key derivation uses PBKDF2-HMAC-SHA256 from the master key.
"""
import os
import base64
import hashlib
import json
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

# Salt for key derivation (fixed but not secret — the master key is the secret)
_PBKDF2_SALT = b"antigravity_v2_encryption_2024"
_PBKDF2_ITERATIONS = 100_000


def _derive_key(master_key_hex: str) -> bytes:
    """Derive a 32-byte AES key from the master key hex string using PBKDF2."""
    try:
        master_key_bytes = bytes.fromhex(master_key_hex)
    except ValueError:
        # Fallback to UTF-8 encoding if not valid hex
        master_key_bytes = master_key_hex.encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_PBKDF2_SALT,
        iterations=_PBKDF2_ITERATIONS,
        backend=default_backend(),
    )
    return kdf.derive(master_key_bytes)


def _get_aes_key() -> bytes:
    master_key = os.environ.get("AES_MASTER_KEY", "")
    if not master_key or len(master_key) < 32:
        # In development, use a fixed dev key
        logger.warning("AES_MASTER_KEY not set or too short — using dev key. DO NOT use in production!")
        master_key = "dev_key_change_me_32_chars_minxx"
    return _derive_key(master_key.ljust(64, "0")[:64])


def encrypt(plaintext: str) -> dict:
    """
    Encrypt a string using AES-256-GCM.
    Returns a dict with: ciphertext (base64), nonce (base64), tag (base64).
    The nonce is randomly generated per encryption.
    """
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM

    data = plaintext.encode("utf-8")
    # AESGCM.encrypt() returns ciphertext + 16-byte auth tag appended
    ciphertext_with_tag = aesgcm.encrypt(nonce, data, None)

    return {
        "ciphertext": base64.b64encode(ciphertext_with_tag[:-16]).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "tag": base64.b64encode(ciphertext_with_tag[-16:]).decode(),
    }


def decrypt(encrypted: dict) -> str:
    """
    Decrypt an AES-256-GCM encrypted dict.
    Input: {ciphertext, nonce, tag} as base64 strings.
    """
    key = _get_aes_key()
    aesgcm = AESGCM(key)

    nonce = base64.b64decode(encrypted["nonce"])
    ciphertext = base64.b64decode(encrypted["ciphertext"])
    tag = base64.b64decode(encrypted["tag"])

    # Reassemble ciphertext + tag (as AESGCM expects)
    ciphertext_with_tag = ciphertext + tag

    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    return plaintext_bytes.decode("utf-8")


def encrypt_dict(data: dict) -> dict:
    """Encrypt an entire dict by serializing to JSON first."""
    return encrypt(json.dumps(data, sort_keys=True))


def decrypt_dict(encrypted: dict) -> dict:
    """Decrypt and deserialize a dict."""
    plaintext = decrypt(encrypted)
    return json.loads(plaintext)


def hash_api_key(raw_key: str) -> str:
    """Hash an API key using SHA-256 (for storage)."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key.
    Returns (raw_key, key_hash) — only return raw_key to user once.
    """
    raw_key = f"ag_{base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip('=')}"
    key_hash = hash_api_key(raw_key)
    return raw_key, key_hash
