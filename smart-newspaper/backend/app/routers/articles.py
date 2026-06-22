"""Language-aware article listing API routes."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.database import AsyncSessionLocal
from app.models import Article
from app.services.language_service import get_articles_by_language, get_articles_by_user_language

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("")
async def list_articles(
    language: str | None = Query(default=None, description="Optional language override, e.g. tr or en"),
    user_id: str | None = Query(default=None, description="Optional user id for language_preference filtering"),
) -> list[dict[str, Any]]:
    """List articles filtered by explicit language or user preference."""
    try:
        async with AsyncSessionLocal() as db:
            if language:
                articles = await get_articles_by_language(db, language)
            elif user_id:
                articles = await get_articles_by_user_language(db, user_id)
            else:
                articles = await get_articles_by_language(db, "tr")
        return [_article_to_dict(article) for article in articles]
    except Exception as exc:
        logger.exception("Article listing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Article listing failed",
        ) from exc


def _article_to_dict(article: Article) -> dict[str, Any]:
    """Serialize an Article ORM object for API responses."""
    published_at = article.published_at.isoformat() if isinstance(article.published_at, datetime) else article.published_at
    created_at = article.created_at.isoformat() if isinstance(article.created_at, datetime) else article.created_at
    return {
        "id": article.id,
        "title": article.title,
        "content": article.content,
        "url": article.url,
        "language": article.language,
        "is_duplicate": bool(getattr(article, "is_duplicate", False)),
        "source_id": article.source_id,
        "published_at": published_at,
        "created_at": created_at,
    }
