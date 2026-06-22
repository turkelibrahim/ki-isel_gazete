"""User behavior tracking endpoints for implicit feedback."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.database import AsyncSessionLocal
from app.schemas.tracking import ArticleStatsResponse, TrackEventRequest, TrackEventResponse, UserRatingResponse
from app.services.tracking_service import TrackingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tracking", tags=["tracking"])
tracking_service = TrackingService()


@router.post("/event", response_model=TrackEventResponse, status_code=status.HTTP_201_CREATED)
async def track_event(payload: TrackEventRequest) -> dict[str, Any]:
    """Store a generic user event and return its implicit rating."""
    try:
        async with AsyncSessionLocal() as db:
            return await tracking_service.track_event(
                db=db,
                user_id=payload.user_id,
                article_id=payload.article_id,
                event_type=payload.event_type,
                duration_seconds=payload.duration_seconds,
                scroll_percent=payload.scroll_percent,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not track event payload=%s", payload.model_dump())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not track event") from exc


@router.post("/view/{article_id}", response_model=TrackEventResponse, status_code=status.HTTP_201_CREATED)
async def track_view(
    article_id: int,
    user_id: str = Query(..., min_length=1, description="TODO(auth): replace with current_user.id"),
    duration_seconds: int | None = Query(default=None, ge=0),
    scroll_percent: float | None = Query(default=None, ge=0, le=100),
) -> dict[str, Any]:
    """Shortcut endpoint for VIEWED events."""
    return await _track_shortcut(user_id, article_id, "VIEWED", duration_seconds, scroll_percent)


@router.post("/read/{article_id}", response_model=TrackEventResponse, status_code=status.HTTP_201_CREATED)
async def track_read(
    article_id: int,
    user_id: str = Query(..., min_length=1, description="TODO(auth): replace with current_user.id"),
    duration_seconds: int | None = Query(default=None, ge=0),
    scroll_percent: float | None = Query(default=None, ge=0, le=100),
) -> dict[str, Any]:
    """Shortcut endpoint for READ events."""
    return await _track_shortcut(user_id, article_id, "READ", duration_seconds, scroll_percent)


@router.post("/skip/{article_id}", response_model=TrackEventResponse, status_code=status.HTTP_201_CREATED)
async def track_skip(
    article_id: int,
    user_id: str = Query(..., min_length=1, description="TODO(auth): replace with current_user.id"),
    duration_seconds: int | None = Query(default=None, ge=0),
    scroll_percent: float | None = Query(default=None, ge=0, le=100),
) -> dict[str, Any]:
    """Shortcut endpoint for SKIPPED events."""
    return await _track_shortcut(user_id, article_id, "SKIPPED", duration_seconds, scroll_percent)


@router.get("/user/{user_id}/ratings", response_model=UserRatingResponse)
async def user_ratings(user_id: str) -> dict[str, Any]:
    """Return max-signal implicit ratings for a user."""
    try:
        async with AsyncSessionLocal() as db:
            return await tracking_service.get_user_ratings(db, user_id=user_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not load user ratings user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load user ratings") from exc


@router.get("/article/{article_id}/stats", response_model=ArticleStatsResponse)
async def article_stats(article_id: int) -> dict[str, Any]:
    """Return aggregate tracking stats for an article."""
    try:
        async with AsyncSessionLocal() as db:
            return await tracking_service.get_article_stats(db, article_id=article_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not load article stats article_id=%s", article_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load article stats") from exc


async def _track_shortcut(
    user_id: str,
    article_id: int,
    event_type: str,
    duration_seconds: int | None,
    scroll_percent: float | None,
) -> dict[str, Any]:
    """Shared implementation for shortcut tracking routes."""
    try:
        async with AsyncSessionLocal() as db:
            return await tracking_service.track_event(
                db=db,
                user_id=user_id,
                article_id=article_id,
                event_type=event_type,
                duration_seconds=duration_seconds,
                scroll_percent=scroll_percent,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not track %s user_id=%s article_id=%s", event_type, user_id, article_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not track event") from exc
