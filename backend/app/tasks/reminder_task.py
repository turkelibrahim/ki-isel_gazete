"""Celery polling task for durable event reminders.

This task intentionally uses database polling instead of in-memory timers.  If the
server or worker restarts, pending reminders remain in the database and are picked
up by the next Celery Beat run.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

try:  # Project-root command: celery -A backend.celery_app ...
    from backend.celery_app import celery_app
except ImportError:  # Fallback for running from inside backend/.
    from celery_app import celery_app  # type: ignore[no-redef]

from app.database import AsyncSessionLocal
from app.models import Event, User
from app.services.email_service import EmailService
from app.services.push_service import PushService

logger = logging.getLogger(__name__)

REMINDER_WINDOW_MINUTES = 15


@celery_app.task(
    bind=True,
    name="app.tasks.reminder_task.send_event_reminders",
    max_retries=3,
    default_retry_delay=60,
)
def send_event_reminders(self: Any) -> dict[str, Any]:
    """Send due event reminders every 15 minutes.

    The Celery task is synchronous, so the async SQLAlchemy workflow is bridged
    with ``asyncio.run``.  A failure for one event/user is logged and counted but
    does not stop the rest of the batch.
    """
    task_name = "send_event_reminders"
    logger.info("Starting %s", task_name)
    try:
        result = asyncio.run(run_due_event_reminders())
        logger.info(
            "Finished %s events=%s notified=%s errors=%s",
            task_name,
            result.get("event_count", 0),
            result.get("notified_events", 0),
            result.get("errors", 0),
        )
        return result
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.exception("%s failed permanently after %s retries", task_name, self.max_retries)
            raise exc
        logger.exception(
            "%s failed; retrying in %s seconds attempt=%s/%s",
            task_name,
            self.default_retry_delay,
            self.request.retries + 1,
            self.max_retries,
        )
        raise self.retry(exc=exc) from exc


async def run_due_event_reminders(now: datetime | None = None) -> dict[str, Any]:
    """Find due reminders and send push/email notifications.

    Args:
        now: Optional test clock. UTC now is used by default.

    Returns:
        Batch statistics suitable for API responses and Celery logs.
    """
    clock = _ensure_aware(now or datetime.now(timezone.utc))
    window_end = clock + timedelta(minutes=REMINDER_WINDOW_MINUTES)
    push_service = PushService()
    email_service = EmailService()

    processed = 0
    notified_events = 0
    notified_users = 0
    skipped = 0
    errors = 0
    details: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        events = await _load_due_events(db, clock, window_end)
        users = await _load_users(db)
        users_by_id = {str(user.id): user for user in users}

        for event in events:
            processed += 1
            try:
                targets = _select_targets(event, users, users_by_id)
                if not targets:
                    skipped += 1
                    details.append({"event_id": event.id, "status": "skipped", "reason": "no_targets"})
                    continue

                event_success = False
                target_results: list[dict[str, Any]] = []
                for user in targets:
                    user_success = False
                    push_ok = False
                    email_ok = False
                    try:
                        push_ok = push_service.send_event_reminder_push(user, event)
                    except Exception:
                        errors += 1
                        logger.exception("Push reminder failed event_id=%s user_id=%s", event.id, getattr(user, "id", None))
                    try:
                        email_ok = email_service.send_event_reminder_email(user, event)
                    except Exception:
                        errors += 1
                        logger.exception("Email reminder failed event_id=%s user_id=%s", event.id, getattr(user, "id", None))

                    user_success = bool(push_ok or email_ok)
                    if user_success:
                        event_success = True
                        notified_users += 1
                    target_results.append(
                        {
                            "user_id": str(getattr(user, "id", "")),
                            "push": bool(push_ok),
                            "email": bool(email_ok),
                            "notified": user_success,
                        }
                    )

                if event_success:
                    event.is_notified = True
                    notified_events += 1
                    await db.commit()
                    details.append({"event_id": event.id, "status": "notified", "targets": target_results})
                else:
                    skipped += 1
                    await db.rollback()
                    details.append({"event_id": event.id, "status": "pending", "targets": target_results})
            except Exception:
                errors += 1
                await db.rollback()
                logger.exception("Reminder processing failed for event_id=%s", getattr(event, "id", None))
                details.append({"event_id": getattr(event, "id", None), "status": "error"})
                continue

    return {
        "window_start": clock.isoformat(),
        "window_end": window_end.isoformat(),
        "event_count": processed,
        "notified_events": notified_events,
        "notified_users": notified_users,
        "skipped": skipped,
        "errors": errors,
        "details": details,
    }


async def _load_due_events(db: Any, now: datetime, window_end: datetime) -> list[Event]:
    """Load active, unnotified events whose reminder time is due.

    ``remind_at <= window_end`` also catches reminders that became due during a
    short outage/restart, as long as the actual event has not passed yet.
    """
    stmt = (
        select(Event)
        .where(Event.is_active.is_(True))
        .where(Event.is_notified.is_(False))
        .where(Event.remind_at.is_not(None))
        .where(Event.remind_at <= window_end)
        .where(Event.event_date >= now)
        .order_by(Event.remind_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def _load_users(db: Any) -> list[User]:
    """Load users that may receive reminders in the MVP targeting strategy."""
    return list((await db.execute(select(User))).scalars().all())


def _select_targets(event: Event, users: list[User], users_by_id: dict[str, User]) -> list[User]:
    """Select reminder recipients.

    MVP behavior: user-specific events go only to their owner; global events go
    to all users.  Future personalization can narrow global events by
    ``user_interests`` and event category without changing the task contract.
    """
    event_user_id = getattr(event, "user_id", None)
    if event_user_id:
        user = users_by_id.get(str(event_user_id))
        return [user] if user is not None else []
    return list(users)


def _ensure_aware(value: datetime) -> datetime:
    """Normalize datetimes to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
