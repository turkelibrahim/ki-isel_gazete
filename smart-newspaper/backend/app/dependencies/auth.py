"""JWT authentication and RBAC dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_token
from app.database import AsyncSessionLocal
from app.models import User
from app.services.auth_service import AuthService

RBAC_MATRIX: dict[str, set[str]] = {
    "ADMIN": {"read", "write", "delete", "admin", "manage_sources", "view_reports", "moderate"},
    "EDITOR": {"read", "write", "manage_sources", "moderate"},
    "USER": {"read", "write_own"},
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
auth_service = AuthService()


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Decode an access token and load the current user from the database."""
    payload = decode_token(token, expected_type="access")
    user_id = str(payload.get("sub"))
    async with AsyncSessionLocal() as db:
        user = await auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*roles: str) -> Callable[[User], User]:
    """Return a dependency that allows only users with one of the roles."""
    allowed = {role.strip().upper() for role in roles if role and role.strip()}
    if not allowed:
        allowed = {"USER", "EDITOR", "ADMIN"}

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        role = str(getattr(current_user, "role", "USER") or "USER").upper()
        if role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yetkiniz yok")
        return current_user

    return dependency


def user_has_permission(user: User | dict[str, Any], permission: str) -> bool:
    """Check a permission name against the static RBAC matrix."""
    role = user.get("role") if isinstance(user, dict) else getattr(user, "role", "USER")
    return permission in RBAC_MATRIX.get(str(role or "USER").upper(), set())
