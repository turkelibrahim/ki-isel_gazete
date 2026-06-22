"""Push notification service for event reminders.

This module intentionally keeps the FCM integration isolated from the rest of
Module 5. If the FCM key or user token is missing, the service logs a warning
and returns ``False`` instead of raising, so email delivery and reminder tasks can
continue independently.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PushService:
    """Send Firebase Cloud Messaging push notifications."""

    FCM_ENDPOINT = "https://fcm.googleapis.com/fcm/send"

    def __init__(self, server_key: str | None = None, timeout_seconds: float = 10.0) -> None:
        """Create a push service.

        Args:
            server_key: Optional FCM server key. Falls back to ``FCM_SERVER_KEY``.
            timeout_seconds: HTTP request timeout for FCM calls.
        """
        self.server_key = server_key if server_key is not None else os.getenv("FCM_SERVER_KEY", "")
        self.timeout_seconds = timeout_seconds

    def send_push(
        self,
        fcm_token: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> bool:
        """Send a raw FCM push notification.

        Args:
            fcm_token: Target device FCM token.
            title: Notification title.
            body: Notification body.
            data: Optional custom data payload.

        Returns:
            ``True`` when FCM accepts the request, otherwise ``False``.
        """
        if not self.server_key:
            logger.warning("FCM_SERVER_KEY is missing; skipping push notification.")
            return False
        if not fcm_token:
            logger.warning("FCM token is missing; skipping push notification.")
            return False

        payload: dict[str, Any] = {
            "to": fcm_token,
            "notification": {"title": title, "body": body},
            "data": data or {},
            "priority": "high",
        }
        headers = {
            "Authorization": f"key={self.server_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(self.FCM_ENDPOINT, headers=headers, json=payload)
                response.raise_for_status()
            logger.info("Push notification sent successfully.")
            return True
        except Exception:
            logger.exception("Failed to send FCM push notification.")
            return False

    def send_event_reminder_push(self, user: Any, event: Any) -> bool:
        """Send a standard event reminder push notification to a user.

        Args:
            user: User-like object. ``fcm_token`` is read with ``getattr``.
            event: Event-like object. ``title``, ``id`` and ``event_date`` are used.

        Returns:
            ``True`` if push is sent successfully; otherwise ``False``.
        """
        fcm_token = getattr(user, "fcm_token", None) or ""
        event_title = getattr(event, "title", "Etkinlik") or "Etkinlik"
        event_id = getattr(event, "id", None)
        event_date = getattr(event, "event_date", None)
        event_category = getattr(event, "category", None)

        title = "Etkinlik Hatırlatması"
        body = f"{event_title} etkinliği yaklaşıyor."
        data = {
            "type": "event_reminder",
            "event_id": str(event_id) if event_id is not None else "",
            "event_title": str(event_title),
            "event_date": event_date.isoformat() if hasattr(event_date, "isoformat") else "",
            "category": str(event_category or ""),
        }
        return self.send_push(fcm_token=fcm_token, title=title, body=body, data=data)
