"""Adaptive ranking API endpoints for online user interest learning."""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Article
from app.services.adaptive_ranking_service import AdaptiveRankingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/adaptive-ranking", tags=["adaptive-ranking"])
service = AdaptiveRankingService()


class AdaptiveUpdateRequest(BaseModel):
    """Payload for manual adaptive update testing."""

    user_id: str = Field(..., min_length=1)
    event_type: Literal["READ", "BOOKMARKED", "SHARED", "SKIPPED", "UNBOOKMARKED"]
    article_id: int | None = Field(default=None, ge=1)
    category_id: int | None = Field(default=None, ge=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class RankPreviewRequest(BaseModel):
    """Payload for ranking preview."""

    article_ids: list[int] | None = None
    limit: int = Field(default=20, ge=1, le=100)


@router.get("/interests/{user_id}")
async def get_interests(user_id: str) -> dict[str, Any]:
    """Return the learned category interest vector for a user."""
    try:
        async with AsyncSessionLocal() as db:
            return await service.get_user_interest_vector(db, user_id=user_id)
    except Exception as exc:
        logger.exception("Could not load adaptive interests user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load interests") from exc


@router.post("/update")
async def update_interests(payload: AdaptiveUpdateRequest) -> dict[str, Any]:
    """Manually update adaptive weights by article or direct category.

    TODO(auth): replace body user_id with current_user.id and restrict admin-only
    direct category updates when auth middleware is connected.
    """
    if payload.article_id is None and payload.category_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="article_id or category_id is required")
    try:
        async with AsyncSessionLocal() as db:
            if payload.category_id is not None:
                return await service.update_category_weight(
                    db=db,
                    user_id=payload.user_id,
                    category_id=payload.category_id,
                    event_type=payload.event_type,
                    confidence=payload.confidence,
                )
            return await service.update_weights_from_event(
                db=db,
                user_id=payload.user_id,
                article_id=int(payload.article_id),
                event_type=payload.event_type,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not update adaptive ranking payload=%s", payload.model_dump())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update adaptive ranking") from exc


@router.post("/reset/{user_id}")
async def reset_interests(user_id: str) -> dict[str, Any]:
    """Reset all learned interests for a user."""
    try:
        async with AsyncSessionLocal() as db:
            return await service.reset_user_interests(db, user_id=user_id)
    except Exception as exc:
        logger.exception("Could not reset adaptive interests user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not reset interests") from exc


@router.post("/rank-preview/{user_id}")
async def rank_preview(user_id: str, payload: RankPreviewRequest | None = None) -> dict[str, Any]:
    """Preview adaptive ranking for selected or recent articles."""
    payload = payload or RankPreviewRequest()
    try:
        async with AsyncSessionLocal() as db:
            query = select(Article).where(Article.is_duplicate == False)  # noqa: E712
            if payload.article_ids:
                query = query.where(Article.id.in_(payload.article_ids))
            query = query.order_by(Article.published_at.desc()).limit(payload.limit)
            result = await db.execute(query)
            articles = list(result.scalars().all())
            ranked = await service.rank_articles_with_interests(db, user_id=user_id, articles=articles)
            return {"user_id": str(user_id), "items": ranked, "total": len(ranked)}
    except Exception as exc:
        logger.exception("Could not preview adaptive ranking user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not rank preview") from exc
