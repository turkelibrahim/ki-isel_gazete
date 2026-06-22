"""Service layer for creating, detecting, listing, updating, and deleting events."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.event_category_classifier import EventCategoryClassifier
from app.ml.event_detector import EventDetector
from app.models import Event

logger = logging.getLogger(__name__)

MIN_EVENT_CONFIDENCE = 0.65
DEFAULT_REMINDER_HOURS = 24


class EventService:
    """Manage event rows and event extraction workflows.

    The service keeps reminder logic in one place so manually created events
    and automatically detected events behave the same way.
    """

    def __init__(self) -> None:
        """Initialize reusable ML helpers."""
        self.detector = EventDetector()
        self.category_classifier = EventCategoryClassifier()

    async def create_event(self, db: AsyncSession, data: dict[str, Any]) -> Event:
        """Create an event unless an identical active event already exists.

        Args:
            db: Fresh SQLAlchemy async session owned by the caller.
            data: Event fields. ``title`` and ``event_date`` are required.

        Returns:
            The newly created event, or the existing duplicate event for the same
            title and event_date.

        Raises:
            ValueError: If required fields are missing or event_date is in the past.
        """
        title = str(data.get("title") or "").strip()
        if not title:
            raise ValueError("title is required")

        event_date = self._coerce_datetime(data.get("event_date"))
        if event_date is None:
            raise ValueError("event_date is required")

        now = datetime.now(timezone.utc)
        event_date = self._ensure_aware(event_date)
        if event_date < now:
            logger.warning("Past event skipped title=%s event_date=%s", title, event_date.isoformat())
            raise ValueError("event_date cannot be in the past")

        duplicate = await self._find_duplicate(db, title, event_date)
        if duplicate is not None:
            logger.info("Duplicate event skipped title=%s event_date=%s", title, event_date.isoformat())
            return duplicate

        description = self._optional_str(data.get("description"))
        location = self._optional_str(data.get("location"))
        user_id = self._optional_str(data.get("user_id"))
        category = self._optional_str(data.get("category"))
        if category is None:
            category_text = f"{title} {description or ''}"
            category = str(self.category_classifier.classify(category_text)["category"])

        remind_at = self._coerce_datetime(data.get("remind_at")) if data.get("remind_at") is not None else None
        if remind_at is None:
            remind_at = self.calculate_remind_at(event_date)
        else:
            remind_at = self._ensure_aware(remind_at)
            if remind_at < now:
                remind_at = now

        event = Event(
            title=title,
            description=description,
            location=location,
            category=category,
            event_date=event_date,
            remind_at=remind_at,
            user_id=user_id,
            is_notified=False,
            is_active=True,
            created_at=now,
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    async def create_events_from_text(self, db: AsyncSession, text: str) -> list[Event]:
        """Detect event candidates from text and persist high-confidence events.

        Candidates below ``MIN_EVENT_CONFIDENCE`` are skipped. Duplicate title +
        event_date pairs are not inserted again.
        """
        created: list[Event] = []
        if not text or not text.strip():
            return created

        for candidate in self.detector.detect_events(text):
            try:
                confidence = float(candidate.get("confidence") or 0.0)
                if confidence < MIN_EVENT_CONFIDENCE:
                    logger.info("Low-confidence event candidate skipped confidence=%s", confidence)
                    continue

                event = await self.create_event(
                    db,
                    {
                        "title": candidate.get("title"),
                        "description": candidate.get("description") or candidate.get("raw_sentence"),
                        "event_date": candidate.get("event_date"),
                        "category": candidate.get("category"),
                    },
                )
                created.append(event)
            except ValueError:
                logger.warning("Detected event candidate skipped: %s", candidate, exc_info=True)
            except Exception:
                logger.exception("Detected event candidate could not be saved: %s", candidate)
        return created

    async def get_upcoming_events(self, db: AsyncSession, days: int = 7) -> list[Event]:
        """Return active events scheduled between now and ``days`` days ahead."""
        safe_days = max(1, min(int(days or 7), 365))
        now = datetime.now(timezone.utc)
        until = now + timedelta(days=safe_days)
        stmt = (
            select(Event)
            .where(Event.is_active.is_(True))
            .where(Event.event_date >= now)
            .where(Event.event_date <= until)
            .order_by(Event.event_date.asc())
        )
        return list((await db.execute(stmt)).scalars().all())

    async def update_event(self, db: AsyncSession, event_id: int, data: dict[str, Any]) -> Event:
        """Update an event and recalculate remind_at when event_date changes."""
        event = await db.get(Event, event_id)
        if event is None or not getattr(event, "is_active", True):
            raise ValueError("event not found")

        cleaned = {key: value for key, value in data.items() if value is not None}
        event_date_changed = "event_date" in cleaned

        if "title" in cleaned:
            title = str(cleaned["title"]).strip()
            if not title:
                raise ValueError("title cannot be empty")
            event.title = title
        if "description" in cleaned:
            event.description = self._optional_str(cleaned["description"])
        if "location" in cleaned:
            event.location = self._optional_str(cleaned["location"])
        if "category" in cleaned:
            event.category = self._optional_str(cleaned["category"])
        if "user_id" in cleaned:
            event.user_id = self._optional_str(cleaned["user_id"])
        if "is_notified" in cleaned:
            event.is_notified = bool(cleaned["is_notified"])

        if event_date_changed:
            new_date = self._coerce_datetime(cleaned.get("event_date"))
            if new_date is None:
                raise ValueError("event_date is invalid")
            new_date = self._ensure_aware(new_date)
            if new_date < datetime.now(timezone.utc):
                raise ValueError("event_date cannot be in the past")
            event.event_date = new_date

        if "remind_at" in cleaned:
            remind_at = self._coerce_datetime(cleaned.get("remind_at"))
            event.remind_at = self._ensure_aware(remind_at) if remind_at else self.calculate_remind_at(event.event_date)
        elif event_date_changed:
            event.remind_at = self.calculate_remind_at(event.event_date)

        if event.category is None:
            event.category = str(self.category_classifier.classify(f"{event.title} {event.description or ''}")["category"])

        await db.commit()
        await db.refresh(event)
        return event

    async def delete_event(self, db: AsyncSession, event_id: int) -> bool:
        """Soft-delete an event by marking it inactive."""
        event = await db.get(Event, event_id)
        if event is None or not getattr(event, "is_active", True):
            return False
        event.is_active = False
        await db.commit()
        return True

    def calculate_remind_at(self, event_date: datetime) -> datetime:
        """Return default reminder time: 24h before event or now if too close."""
        aware_date = self._ensure_aware(event_date)
        now = datetime.now(timezone.utc)
        remind_at = aware_date - timedelta(hours=DEFAULT_REMINDER_HOURS)
        if remind_at < now:
            return now
        return remind_at

    async def _find_duplicate(self, db: AsyncSession, title: str, event_date: datetime) -> Event | None:
        """Find an active duplicate by exact title and exact event_date."""
        stmt = (
            select(Event)
            .where(
                and_(
                    Event.is_active.is_(True),
                    Event.title == title,
                    Event.event_date == event_date,
                )
            )
            .limit(1)
        )
        return (await db.execute(stmt)).scalars().first()

    def _coerce_datetime(self, value: Any) -> datetime | None:
        """Convert datetime-like values into ``datetime`` objects."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"invalid datetime: {value}") from exc
        raise ValueError(f"invalid datetime value: {value!r}")

    def _ensure_aware(self, value: datetime) -> datetime:
        """Ensure a datetime has timezone information."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _optional_str(self, value: Any) -> str | None:
        """Normalize optional string values."""
        if value is None:
            return None
        text = str(value).strip()
        return text or None
