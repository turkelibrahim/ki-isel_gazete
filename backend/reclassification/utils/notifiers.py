"""Notification stubs for admin/security events."""
from __future__ import annotations

from datetime import datetime
from typing import Any

_NOTIFICATIONS: list[dict[str, Any]] = []


def notify_super_admin(event_type: str, message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record a super-admin notification without requiring external services."""
    notification = {"event_type": event_type, "message": message, "payload": payload or {}, "created_at": datetime.utcnow().isoformat()}
    _NOTIFICATIONS.append(notification)
    return notification


def get_notifications() -> list[dict[str, Any]]:
    """Return recorded notifications."""
    return list(_NOTIFICATIONS)
