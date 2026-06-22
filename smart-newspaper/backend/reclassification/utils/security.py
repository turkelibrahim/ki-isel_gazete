"""Security helpers for passwords and compact signed tokens."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import secrets


def hash_password(password: str, salt: str | None = None) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a PBKDF2 password hash."""
    try:
        _, salt, digest = password_hash.split("$", 2)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt).split("$", 2)[2], digest)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def sign_token(payload: dict, secret: str, expire_hours: int = 8) -> str:
    """Create a compact HMAC signed token for admin API adapters."""
    enriched = dict(payload)
    enriched["exp"] = (datetime.utcnow() + timedelta(hours=expire_hours)).isoformat()
    body = _b64(json.dumps(enriched, separators=(",", ":")).encode())
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_token(token: str, secret: str) -> dict:
    """Verify an HMAC token and return its payload."""
    body, sig = token.split(".", 1)
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Geçersiz token imzası.")
    payload = json.loads(_unb64(body))
    if datetime.fromisoformat(payload["exp"]) < datetime.utcnow():
        raise ValueError("JWT süresi doldu.")
    return payload
