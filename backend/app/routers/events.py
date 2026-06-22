"""CRUD and text-detection APIs for events."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select

from app.database import AsyncSessionLocal
from app.models import Event
from app.schemas.events import EventCreate, EventDetectionRequest, EventDetectionResponse, EventResponse, EventUpdate
from app.services.event_service import EventService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])
event_service = EventService()


@router.get("", response_model=dict[str, Any])
async def list_events(
    limit: int = Query(default=50, ge=1, le=200),
    include_inactive: bool = Query(default=False),
) -> dict[str, Any]:
    """List events ordered by event date."""
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(Event).order_by(Event.event_date.asc()).limit(limit)
            if not include_inactive:
                stmt = stmt.where(Event.is_active.is_(True))
            events = list((await db.execute(stmt)).scalars().all())
            return {"count": len(events), "items": [_serialize_event(event) for event in events]}
    except Exception as exc:
        logger.exception("Could not list events")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list events") from exc


@router.get("/upcoming", response_model=dict[str, Any])
async def upcoming_events(days: int = Query(default=7, ge=1, le=365)) -> dict[str, Any]:
    """Return active upcoming events for the next N days."""
    try:
        async with AsyncSessionLocal() as db:
            events = await event_service.get_upcoming_events(db, days=days)
            return {"days": days, "count": len(events), "items": [_serialize_event(event) for event in events]}
    except Exception as exc:
        logger.exception("Could not list upcoming events days=%s", days)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list upcoming events") from exc


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(payload: EventCreate) -> dict[str, Any]:
    """Create a manual event and calculate remind_at automatically when omitted."""
    try:
        async with AsyncSessionLocal() as db:
            event = await event_service.create_event(db, payload.model_dump())
            return _serialize_event(event)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not create event title=%s", payload.title)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create event") from exc


@router.post("/detect-from-text", response_model=EventDetectionResponse)
async def detect_events_from_text(payload: EventDetectionRequest) -> dict[str, Any]:
    """Detect high-confidence events from text and persist them."""
    try:
        async with AsyncSessionLocal() as db:
            events = await event_service.create_events_from_text(db, payload.text)
            return {
                "created_count": len(events),
                "items": [_serialize_event(event) for event in events],
                "status": "processed",
                "meta": {"min_confidence": 0.65},
            }
    except Exception as exc:
        logger.exception("Could not detect events from text")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not detect events from text") from exc


@router.post("/reminders/run-now", response_model=dict[str, Any])
async def run_reminders_now() -> dict[str, Any]:
    """Manually run the due-reminder polling logic for operational tests.

    TODO(auth): Require ADMIN role once the FastAPI authentication dependency is
    connected.  The task itself remains DB-backed and safe across restarts.
    """
    try:
        from app.tasks.reminder_task import run_due_event_reminders

        return await run_due_event_reminders()
    except Exception as exc:
        logger.exception("Could not run event reminders manually")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not run event reminders",
        ) from exc


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(event_id: int, payload: EventUpdate) -> dict[str, Any]:
    """Partially update an event."""
    try:
        async with AsyncSessionLocal() as db:
            event = await event_service.update_event(db, event_id, payload.model_dump(exclude_unset=True))
            return _serialize_event(event)
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=detail) from exc
    except Exception as exc:
        logger.exception("Could not update event_id=%s", event_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update event") from exc


@router.delete("/{event_id}")
async def delete_event(event_id: int) -> dict[str, Any]:
    """Soft-delete an event."""
    try:
        async with AsyncSessionLocal() as db:
            deleted = await event_service.delete_event(db, event_id)
            if not deleted:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
            return {"event_id": event_id, "deleted": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not delete event_id=%s", event_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete event") from exc


def _serialize_event(event: Event) -> dict[str, Any]:
    """Serialize an Event ORM row into API response format."""
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "category": event.category,
        "event_date": _dt_to_iso(event.event_date),
        "remind_at": _dt_to_iso(event.remind_at),
        "user_id": event.user_id,
        "is_notified": bool(getattr(event, "is_notified", False)),
        "is_active": bool(getattr(event, "is_active", True)),
        "created_at": _dt_to_iso(getattr(event, "created_at", None)),
    }


def _dt_to_iso(value: Any) -> str | None:
    """Return datetime-like values as ISO text."""
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)
