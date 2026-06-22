"""Role-based access control helpers."""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from backend.reclassification.models.enums import ROLE_PERMISSIONS


class PermissionDenied(PermissionError):
    """Raised when an admin lacks a required permission."""


def ensure_permission(role: str, permission: str) -> None:
    """Raise when a role does not have a permission."""
    if not ROLE_PERMISSIONS.get(role, {}).get(permission):
        raise PermissionDenied(f"Bu işlem için {permission} yetkisi gerekli.")


def require_role(*roles: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a function that receives current_user with a role check."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_user = kwargs.get("current_user")
            if current_user is None or current_user.role not in roles:
                raise PermissionDenied(f"Bu işlem için {list(roles)} rolü gerekli.")
            return func(*args, **kwargs)
        return wrapper
    return decorator
