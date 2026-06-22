"""Bookmark CRUD API with optimistic upsert behavior."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, status

from app.database import AsyncSessionLocal
from app.schemas.bookmarks import BookmarkCreate, BookmarkListResponse, BookmarkResponse, BookmarkStatusResponse
from app.services.bookmark_service import BookmarkService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])
bookmark_service = BookmarkService()


@router.get("", response_model=BookmarkListResponse)
async def list_bookmarks(
    user_id: str = Query(..., min_length=1, description="TODO(auth): replace with current_user.id"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """List bookmarks for the current temporary user_id."""
    try:
        async with AsyncSessionLocal() as db:
            return await bookmark_service.list_bookmarks(db, user_id=user_id, page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not list bookmarks user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list bookmarks") from exc


@router.post("/{article_id}", response_model=BookmarkResponse, status_code=status.HTTP_201_CREATED)
async def add_bookmark(
    article_id: int,
    user_id: str | None = Query(default=None, min_length=1, description="TODO(auth): replace with current_user.id"),
    payload: BookmarkCreate | None = Body(default=None),
) -> dict[str, Any]:
    """Add a bookmark with optimistic INSERT + IntegrityError duplicate handling."""
    resolved_user_id = _resolve_user_id(user_id, payload)
    try:
        async with AsyncSessionLocal() as db:
            return await bookmark_service.add_bookmark(db, user_id=resolved_user_id, article_id=article_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not add bookmark user_id=%s article_id=%s", resolved_user_id, article_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not add bookmark") from exc


@router.delete("/{article_id}", response_model=BookmarkResponse)
async def remove_bookmark(
    article_id: int,
    user_id: str = Query(..., min_length=1, description="TODO(auth): replace with current_user.id"),
) -> dict[str, Any]:
    """Remove a bookmark; missing rows return not_found instead of raising."""
    try:
        async with AsyncSessionLocal() as db:
            return await bookmark_service.remove_bookmark(db, user_id=user_id, article_id=article_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not remove bookmark user_id=%s article_id=%s", user_id, article_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not remove bookmark") from exc


@router.post("/{article_id}/toggle", response_model=BookmarkResponse)
async def toggle_bookmark(
    article_id: int,
    user_id: str | None = Query(default=None, min_length=1, description="TODO(auth): replace with current_user.id"),
    payload: BookmarkCreate | None = Body(default=None),
) -> dict[str, Any]:
    """Toggle a bookmark on/off for the current temporary user_id."""
    resolved_user_id = _resolve_user_id(user_id, payload)
    try:
        async with AsyncSessionLocal() as db:
            return await bookmark_service.toggle_bookmark(db, user_id=resolved_user_id, article_id=article_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not toggle bookmark user_id=%s article_id=%s", resolved_user_id, article_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not toggle bookmark") from exc


@router.get("/{article_id}/status", response_model=BookmarkStatusResponse)
async def bookmark_status(
    article_id: int,
    user_id: str = Query(..., min_length=1, description="TODO(auth): replace with current_user.id"),
) -> dict[str, Any]:
    """Return true/false bookmark status for an article."""
    try:
        async with AsyncSessionLocal() as db:
            bookmarked = await bookmark_service.is_bookmarked(db, user_id=user_id, article_id=article_id)
            return {"user_id": str(user_id), "article_id": article_id, "bookmarked": bookmarked}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not check bookmark status user_id=%s article_id=%s", user_id, article_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not check bookmark status") from exc


def _resolve_user_id(user_id: str | None, payload: BookmarkCreate | None) -> str:
    """Resolve user_id from query first, then optional JSON body."""
    resolved = user_id or (payload.user_id if payload else None)
    if not resolved or not str(resolved).strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")
    return str(resolved).strip()
