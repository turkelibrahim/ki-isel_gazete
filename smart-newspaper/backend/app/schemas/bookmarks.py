"""Pydantic schemas for bookmark APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BookmarkCreate(BaseModel):
    """Optional request body for clients that prefer JSON user_id transport."""

    user_id: str = Field(..., min_length=1, max_length=255)


class BookmarkResponse(BaseModel):
    """Response returned by add/remove/toggle bookmark operations."""

    status: str
    bookmarked: bool
    article_id: int
    user_id: str
    bookmark_id: int | None = None
    created_at: str | None = None


class BookmarkListResponse(BaseModel):
    """Paginated bookmark list response."""

    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int
    has_next: bool
    user_id: str


class BookmarkStatusResponse(BaseModel):
    """Bookmark boolean status response."""

    user_id: str
    article_id: int
    bookmarked: bool
