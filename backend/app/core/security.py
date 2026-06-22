"""Password hashing and JWT helpers for Module 8 authentication.

Primary implementation uses passlib[bcrypt] and python-jose. Small controlled
fallbacks keep the backend importable in lightweight test environments where the
optional packages have not been installed yet; production should install the
requirements and set SECRET_KEY.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised when optional dependency is installed
    from jose import JWTError, jwt  # type: ignore
except Exception:  # pragma: no cover - fallback is covered by smoke tests here
    JWTError = Exception  # type: ignore
    jwt = None  # type: ignore

try:  # pragma: no cover - exercised when optional dependency is installed
    from passlib.context import CryptContext  # type: ignore
except Exception:  # pragma: no cover - fallback is covered by smoke tests here
    CryptContext = None  # type: ignore

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
_DEV_SECRET = "dev-only-change-me-smart-newspaper-secret"

if CryptContext is not None:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
else:
    pwd_context = None
    logger.warning("passlib[bcrypt] is not installed; using PBKDF2 fallback until dependencies are installed")


def _secret_key() -> str:
    """Return JWT secret, warning in development when SECRET_KEY is absent."""
    secret = os.getenv("SECRET_KEY")
    if secret:
        if len(secret) < 32:
            logger.warning("SECRET_KEY should be at least 32 characters long")
        return secret
    env = (os.getenv("ENV") or os.getenv("APP_ENV") or "development").lower()
    if env in {"prod", "production"}:
        raise RuntimeError("SECRET_KEY is required in production")
    logger.warning("SECRET_KEY is missing; using development-only fallback secret")
    return _DEV_SECRET


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt via passlib, or PBKDF2 fallback."""
    if not password or len(password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 8 characters")
    if pwd_context is not None:
        return pwd_context.hash(password)
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 390_000)
    return f"pbkdf2_sha256$390000${salt}${digest.hex()}"


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Verify a plaintext password against a stored hash."""
    if not plain_password or not hashed_password:
        return False
    if pwd_context is not None and not hashed_password.startswith("pbkdf2_sha256$"):
        try:
            return bool(pwd_context.verify(plain_password, hashed_password))
        except Exception:
            logger.exception("Password verification failed")
            return False
    try:
        algorithm, iterations, salt, expected_hex = hashed_password.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), expected_hex)
    except Exception:
        logger.exception("Fallback password verification failed")
        return False


def create_access_token(user_id: int | str, role: str) -> str:
    """Create a short-lived JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": str(role).upper(), "type": "access", "exp": expire}
    return _encode_token(payload)


def create_refresh_token(user_id: int | str, role: str) -> str:
    """Create a long-lived JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "role": str(role).upper(), "type": "refresh", "exp": expire}
    return _encode_token(payload)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """Decode and validate a JWT token type, signature and expiration."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = _decode_token(token)
        token_type = payload.get("type")
        user_id = payload.get("sub")
        if token_type != expected_type or user_id is None:
            raise credentials_exception
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Token decode failed: %s", exc)
        raise credentials_exception from exc


def _encode_token(payload: dict[str, Any]) -> str:
    secret = _secret_key()
    if jwt is not None:  # pragma: no cover - depends on python-jose installation
        return str(jwt.encode(payload, secret, algorithm=ALGORITHM))
    serializable = payload.copy()
    exp = serializable.get("exp")
    if isinstance(exp, datetime):
        serializable["exp"] = int(exp.timestamp())
    header = {"alg": ALGORITHM, "typ": "JWT"}
    signing_input = f"{_b64json(header)}.{_b64json(serializable)}"
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"


def _decode_token(token: str) -> dict[str, Any]:
    secret = _secret_key()
    if jwt is not None:  # pragma: no cover - depends on python-jose installation
        return dict(jwt.decode(token, secret, algorithms=[ALGORITHM]))
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
        signing_input = f"{header_b64}.{payload_b64}"
        expected = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
        received = _unb64(signature_b64)
        if not hmac.compare_digest(expected, received):
            raise ValueError("invalid signature")
        header = json.loads(_unb64(header_b64).decode("utf-8"))
        if header.get("alg") != ALGORITHM:
            raise ValueError("unsupported algorithm")
        payload = json.loads(_unb64(payload_b64).decode("utf-8"))
        exp = payload.get("exp")
        if exp is not None and datetime.now(timezone.utc).timestamp() > float(exp):
            raise ValueError("token expired")
        return payload
    except Exception as exc:
        raise ValueError("invalid token") from exc


def _b64json(value: dict[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _b64(raw)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
