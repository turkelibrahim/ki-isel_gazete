"""Preview endpoint for Jinja2 personal newspaper HTML layouts."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Article, Source, User
from app.services.citation_service import CitationService
from app.services.layout_service import LayoutService
from app.services.prioritization_service import PrioritizationService
from app.services.recommendation_service import get_personalized_feed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/newspaper", tags=["newspaper-layout"])
layout_service = LayoutService()
citation_service = CitationService()
prioritization_service = PrioritizationService()


class PreviewHtmlRequest(BaseModel):
    """Request body for personal newspaper HTML preview generation."""

    user_id: str = Field(..., min_length=1)
    article_ids: list[int] | None = Field(default=None, description="Optional explicit article ordering")
    date: datetime | None = Field(default=None, description="Optional edition date")
    events: list[dict[str, Any]] | None = Field(default=None, description="Optional event cards")
    edition_title: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=30, ge=1, le=100)


@router.post("/preview-html")
async def preview_newspaper_html(payload: PreviewHtmlRequest) -> dict[str, Any]:
    """Render a PDF-ready newspaper HTML preview from explicit articles or personal feed."""
    try:
        async with AsyncSessionLocal() as db:
            user_obj = await db.get(User, payload.user_id)
            user = _serialize_user(user_obj, payload.user_id)

            if payload.article_ids:
                articles = await _load_articles_by_ids(db, payload.article_ids)
            else:
                feed = await get_personalized_feed(db, user_id=payload.user_id, limit=payload.limit)
                articles = [dict(item) for item in feed.get("items", [])]

        citations = citation_service.build_citations(articles)
        ranked_articles = prioritization_service.rank(articles)
        html = layout_service.render_daily(
            articles=ranked_articles,
            events=payload.events or [],
            user=user,
            edition_date=payload.date,
            edition_title=payload.edition_title or "Kişisel Gazete",
            citations=citations,
        )
        return {
            "html": html,
            "article_count": len(ranked_articles),
            "headline": ranked_articles[0] if ranked_articles else None,
            "event_count": len(payload.events or []),
            "user_id": payload.user_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Newspaper HTML preview failed user_id=%s", payload.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Newspaper HTML preview failed",
        ) from exc


async def _load_articles_by_ids(db, article_ids: list[int]) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    """Load duplicate-free articles in the same order as requested ids."""
    if not article_ids:
        return []
    unique_ids = list(dict.fromkeys(article_ids))
    stmt = (
        select(Article, Source.name, Source.base_url, Source.trust_score)
        .join(Source, Article.source_id == Source.id, isouter=True)
        .where(Article.id.in_(unique_ids))
        .where(Article.is_duplicate.is_(False))
    )
    rows = (await db.execute(stmt)).all()
    by_id = {int(article.id): _serialize_article(article, source_name, source_url, trust_score) for article, source_name, source_url, trust_score in rows}
    return [by_id[article_id] for article_id in unique_ids if article_id in by_id]


def _serialize_article(article: Article, source_name: str | None, source_url: str | None, trust_score: float | None) -> dict[str, Any]:
    """Convert an Article ORM row into a template-friendly dictionary."""
    published_at = article.published_at.isoformat() if isinstance(article.published_at, datetime) else article.published_at
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
        "source_url": source_url or "#",
        "source_trust_score": float(trust_score if trust_score is not None else 0.5),
        "view_count": int(getattr(article, "view_count", 0) or 0),
        "published_at": published_at,
    }


def _serialize_user(user: User | None, fallback_user_id: str) -> dict[str, Any]:
    """Return safe user metadata for the newspaper masthead."""
    if user is None:
        return {"id": fallback_user_id, "name": fallback_user_id, "email": None}
    email = getattr(user, "email", None)
    name = str(email).split("@")[0] if email else str(getattr(user, "id", fallback_user_id))
    return {"id": getattr(user, "id", fallback_user_id), "name": name, "email": email}

