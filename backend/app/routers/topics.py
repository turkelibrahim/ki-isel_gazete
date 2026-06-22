"""Topic modeling API endpoints for Module 7."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.database import AsyncSessionLocal
from app.services.topic_service import topic_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.post("/train")
async def train_topics(limit: int = Query(default=5000, ge=10, le=20000)) -> dict[str, Any]:
    """Train the LDA topic model from current articles."""
    try:
        async with AsyncSessionLocal() as db:
            return await topic_service.train_topics(db, limit=limit)
    except Exception as exc:
        logger.exception("Topic training endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not train topic model") from exc


@router.get("")
async def list_topics(limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    """List current topics or fallback keyword topics."""
    try:
        async with AsyncSessionLocal() as db:
            return await topic_service.get_topics(db, limit=limit)
    except Exception as exc:
        logger.exception("Topic list endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load topics") from exc


@router.get("/trending")
async def trending_topics(
    days: int = Query(default=7, ge=1, le=30),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[dict[str, Any]]:
    """Return trending topics from recent article trend scores."""
    try:
        async with AsyncSessionLocal() as db:
            return await topic_service.get_trending_topics(db, days=days, limit=limit)
    except Exception as exc:
        logger.exception("Trending topics endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load trending topics") from exc


@router.get("/article/{article_id}")
async def article_topics(article_id: int) -> dict[str, Any]:
    """Return topic distribution for one article."""
    try:
        async with AsyncSessionLocal() as db:
            return await topic_service.get_article_topics(db, article_id=article_id)
    except Exception as exc:
        logger.exception("Article topics endpoint failed article_id=%s", article_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load article topics") from exc


@router.get("/status")
async def topic_status() -> dict[str, Any]:
    """Return topic model status and configuration."""
    return topic_service.get_status()
