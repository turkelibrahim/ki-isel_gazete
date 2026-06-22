"""Pydantic schemas for user behavior tracking."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

TrackableEventType = Literal["VIEWED", "READ", "BOOKMARKED", "SHARED", "SKIPPED", "UNBOOKMARKED"]


class TrackEventRequest(BaseModel):
    """Request payload for generic event tracking."""

    user_id: str = Field(..., min_length=1, max_length=255, description="TODO(auth): replace with current_user.id")
    article_id: int = Field(..., ge=1)
    event_type: TrackableEventType
    duration_seconds: int | None = Field(default=None, ge=0)
    scroll_percent: float | None = Field(default=None, ge=0, le=100)


class TrackEventResponse(BaseModel):
    """Response returned after a user event is stored."""

    status: str
    event_id: int
    user_id: str
    article_id: int
    event_type: str
    duration_seconds: float | None = None
    scroll_percent: float | None = None
    implicit_rating: float
    view_count: int
    created_at: str | None = None


class UserRatingResponse(BaseModel):
    """Aggregated implicit ratings for one user."""

    user_id: str
    items: list[dict[str, Any]]
    total: int
    event_weights: dict[str, float]
    aggregation: str


class ArticleStatsResponse(BaseModel):
    """Aggregated tracking stats for one article."""

    article_id: int
    title: str
    view_count: int
    event_counts: dict[str, int]
    total_events: int
    unique_users: int
