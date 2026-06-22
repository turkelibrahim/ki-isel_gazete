"""Personalized news feed API endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.database import AsyncSessionLocal
from app.services.recommendation_service import (
    get_personalized_feed,
    get_recommendation_debug,
    rebuild_recommendation_index,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/personal", tags=["personal-feed"])


@router.get("/feed")
async def personal_feed(
    user_id: str = Query(..., min_length=1, description="User id for personalized feed"),
    limit: int = Query(default=30, ge=1, le=100),
) -> dict[str, Any]:
    """Return the current user's personalized feed."""
    try:
        async with AsyncSessionLocal() as db:
            return await get_personalized_feed(db, user_id=user_id, limit=limit)
    except Exception as exc:
        logger.exception("Personal feed failed user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/feed/{user_id}")
async def personal_feed_by_user(user_id: str, limit: int = Query(default=30, ge=1, le=100)) -> dict[str, Any]:
    """Return a personalized feed for an explicit user id."""
    try:
        async with AsyncSessionLocal() as db:
            return await get_personalized_feed(db, user_id=user_id, limit=limit)
    except Exception as exc:
        logger.exception("Personal feed failed user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/rebuild-index")
async def rebuild_index(language: str | None = Query(default=None),) -> dict[str, Any]:
    """Rebuild the content-based TF-IDF article index."""
    try:
        async with AsyncSessionLocal() as db:
            return await rebuild_recommendation_index(db, language=language)
    except Exception as exc:
        logger.exception("Recommendation index rebuild failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/recommendation-debug")
async def recommendation_debug(user_id: str | None = Query(default=None)) -> dict[str, Any]:
    """Return diagnostic information about the recommender configuration."""
    try:
        async with AsyncSessionLocal() as db:
            return await get_recommendation_debug(db, user_id=user_id)
    except Exception as exc:
        logger.exception("Recommendation debug failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
