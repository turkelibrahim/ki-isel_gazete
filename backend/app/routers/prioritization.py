"""Headline prioritization API endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.ml.recommenders.content_based import ContentBasedRecommender
from app.models import Article, Source, User, UserEvent
from app.services.prioritization_service import PrioritizationService
from app.ml.recommenders.user_cf import EVENT_WEIGHTS

logger = logging.getLogger(__name__)
router = APIRouter(tags=["headline-prioritization"])
prioritizer = PrioritizationService()


class RankHeadlinesRequest(BaseModel):
    """Request body for explicit headline prioritization."""

    article_ids: list[int] | None = Field(default=None, description="Optional article ids to rank in priority order")
    user_id: str | None = Field(default=None, min_length=1, description="Optional user for relevance profile")
    language: str | None = Field(default=None, max_length=10)
    limit: int = Field(default=30, ge=1, le=100)


@router.post("/api/newspaper/rank-headlines")
async def rank_headlines(payload: RankHeadlinesRequest) -> dict[str, Any]:
    """Rank candidate articles and return the highest-scored article first."""
    try:
        async with AsyncSessionLocal() as db:
            language = await _resolve_language(db, payload.user_id, payload.language)
            article_rows = await _load_articles(db, article_ids=payload.article_ids, language=language, limit=max(payload.limit, 1))
            relevance_map = await _build_relevance_map(db, payload.user_id, article_rows) if payload.user_id else None

        ranked = prioritizer.rank(article_rows, user_profile=relevance_map)[: payload.limit]
        return _response(ranked, payload.user_id, language, payload.limit, "explicit_rank" if payload.article_ids else "candidate_rank")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Headline ranking failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Headline ranking failed") from exc


@router.get("/api/articles/top-headlines")
async def top_headlines(
    user_id: str | None = Query(default=None, description="Optional user id for relevance profile"),
    language: str | None = Query(default=None, max_length=10),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict[str, Any]:
    """Return duplicate-free top headline candidates ranked by P15 priority score."""
    try:
        async with AsyncSessionLocal() as db:
            resolved_language = await _resolve_language(db, user_id, language)
            article_rows = await _load_articles(db, article_ids=None, language=resolved_language, limit=max(limit * 5, 50))
            relevance_map = await _build_relevance_map(db, user_id, article_rows) if user_id else None

        ranked = prioritizer.rank(article_rows, user_profile=relevance_map)[:limit]
        return _response(ranked, user_id, resolved_language, limit, "top_headlines")
    except Exception as exc:
        logger.exception("Top headlines failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Top headlines failed") from exc


async def _resolve_language(db: AsyncSession, user_id: str | None, language: str | None) -> str | None:
    """Use explicit language first, then user preference, otherwise no language filter."""
    if language:
        return language.strip().lower()
    if not user_id:
        return None
    user = await db.get(User, user_id)
    return (getattr(user, "language_preference", None) or "tr").strip().lower() if user else "tr"


async def _load_articles(
    db: AsyncSession,
    *,
    article_ids: list[int] | None,
    language: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Load duplicate-free articles with source trust metadata."""
    stmt = (
        select(Article, Source.name, Source.trust_score)
        .join(Source, Article.source_id == Source.id, isouter=True)
        .where(Article.is_duplicate.is_(False))
    )
    if article_ids:
        unique_ids = list(dict.fromkeys(article_ids))
        stmt = stmt.where(Article.id.in_(unique_ids))
        rows = (await db.execute(stmt)).all()
        by_id = {int(article.id): _serialize_article(article, source_name, trust_score) for article, source_name, trust_score in rows}
        return [by_id[article_id] for article_id in unique_ids if article_id in by_id]
    if language:
        stmt = stmt.where(Article.language == language)
    stmt = stmt.order_by(desc(Article.published_at)).limit(limit)
    rows = (await db.execute(stmt)).all()
    return [_serialize_article(article, source_name, trust_score) for article, source_name, trust_score in rows]


async def _build_relevance_map(db: AsyncSession, user_id: str | None, article_rows: list[dict[str, Any]]) -> dict[int, float] | None:
    """Build a content-based article relevance map for a user's read history.

    Cold-start users return ``None`` so the prioritization service applies the
    required relevance fallback of 0.5.
    """
    if not user_id or not article_rows:
        return None
    events = list((await db.execute(select(UserEvent).where(UserEvent.user_id == user_id))).scalars().all())
    read_ids = {
        int(event.article_id)
        for event in events
        if EVENT_WEIGHTS.get(str(event.event_type or "").upper(), 0.0) > 0
    }
    if not read_ids:
        return None

    # Build relevance over candidate + read articles so read vectors exist even
    # when already-read items are not in the candidate top-headline list.
    candidate_ids = {int(row["id"]) for row in article_rows if row.get("id") is not None}
    missing_read_ids = sorted(read_ids - candidate_ids)
    extra_rows: list[dict[str, Any]] = []
    if missing_read_ids:
        stmt = select(Article, Source.name, Source.trust_score).join(Source, Article.source_id == Source.id, isouter=True).where(
            Article.id.in_(missing_read_ids)
        )
        rows = (await db.execute(stmt)).all()
        extra_rows = [_serialize_article(article, source_name, trust_score) for article, source_name, trust_score in rows]

    index_rows = article_rows + extra_rows
    recommender = ContentBasedRecommender()
    recommender.index_articles(index_rows)
    profile = recommender.build_profile(list(read_ids))
    cb_scores = recommender.recommend(profile, exclude_ids=set(), limit=max(len(index_rows), 1))
    if not cb_scores:
        return None
    return {int(row["article_id"]): float(row["score"]) for row in cb_scores}


def _serialize_article(article: Article, source_name: str | None, trust_score: float | None) -> dict[str, Any]:
    """Serialize article ORM rows for priority scoring responses."""
    published_at = article.published_at.isoformat() if isinstance(article.published_at, datetime) else article.published_at
    created_at = article.created_at.isoformat() if isinstance(article.created_at, datetime) else article.created_at
    return {
        "id": article.id,
        "article_id": article.id,
        "title": article.title,
        "summary": getattr(article, "summary", None),
        "content": article.content,
        "url": article.url,
        "language": article.language,
        "source_id": article.source_id,
        "source_name": source_name,
        "source_trust_score": float(trust_score if trust_score is not None else 0.5),
        "view_count": int(getattr(article, "view_count", 0) or 0),
        "published_at": published_at,
        "created_at": created_at,
    }


def _response(ranked: list[dict[str, Any]], user_id: str | None, language: str | None, limit: int, mode: str) -> dict[str, Any]:
    """Build the API response envelope."""
    return {
        "items": ranked,
        "headline": ranked[0] if ranked else None,
        "count": len(ranked),
        "limit": limit,
        "user_id": user_id,
        "language": language,
        "mode": mode,
        "scoring": {
            "formula": "0.40*relevance + 0.30*recency + 0.20*popularity + 0.10*trust",
            "recency": "exp(-0.05 * hours_old)",
            "popularity": "log10(1 + view_count) normalized by list maximum",
            "cold_start_relevance": 0.5,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
