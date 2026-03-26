"""
Helper functions extending the encryption service.
generate_api_key, hash_api_key, encrypt_dict, decrypt_dict shims.
"""
import hashlib
import secrets
import base64
import json
import os


# ── AES-256-GCM implementation reuse ─────────────────────────────────────────
# These thin wrappers ensure the models module can call encrypt/decrypt without
# circular imports.

def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash an API key for storage (non-reversible)."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key with prefix.
    Returns (raw_key, key_hash). Store only the hash.
    """
    raw = f"ag_{''.join(secrets.token_urlsafe(32).replace('-', '').replace('_', '')[:48])}"
    key_hash = hash_api_key(raw)
    return raw, key_hash


def encrypt_dict(data: dict) -> dict:
    """
    Encrypt all string values in a flat dict using AES-256-GCM.
    Returns a dict with encrypted string values.
    """
    from services.encryption_service import encrypt

    if not data:
        return {}

    result = {}
    for k, v in data.items():
        if isinstance(v, str) and v:
            result[k] = encrypt(v)
        else:
            result[k] = str(v) if v is not None else None
    return result


def decrypt_dict(data: dict) -> dict:
    """
    Decrypt all string values in a flat dict.
    """
    from services.encryption_service import decrypt

    if not data:
        return {}

    result = {}
    for k, v in data.items():
        if isinstance(v, str) and v and v.startswith("ag_enc:"):
            try:
                result[k] = decrypt(v)
            except Exception:
                result[k] = v  # Return as-is if decrypt fails
        else:
            result[k] = v
    return result
