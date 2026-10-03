"""Symmetric encryption for stored provider API keys."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_ENC_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.ai_master_encryption_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if value.startswith(_ENC_PREFIX):
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_ENC_PREFIX}{token}"


def decrypt_secret(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if value.startswith("MOCK_ENC:"):
        return value.removeprefix("MOCK_ENC:")
    if not value.startswith(_ENC_PREFIX):
        return value
    token = value.removeprefix(_ENC_PREFIX)
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None
