"""Citation API routes for article source transparency."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Article, Source
from app.services.source_tracker import MetadataExtractor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/articles", tags=["citations"])
extractor = MetadataExtractor()


@router.get("/{article_id}/citation")
async def get_article_citation(article_id: int) -> dict[str, Any]:
    """Return source, publisher, author, date, URL, and trust badge data."""
    try:
        async with AsyncSessionLocal() as db:
            article = await db.get(Article, article_id)
            if article is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Article not found",
                )

            source = None
            if getattr(article, "source_id", None) is not None:
                source_result = await db.execute(select(Source).where(Source.id == article.source_id))
                source = source_result.scalar_one_or_none()

        metadata = extractor.extract(article.content or "", article.url or "")
        source_name = getattr(source, "name", None) or metadata["publisher"]
        trust_score = float(getattr(source, "trust_score", 0.5) or 0.5)
        published_at = metadata.get("published_at") or getattr(article, "published_at", None)
        published_human = metadata.get("published_human") or extractor.humanize_date(published_at)

        return {
            "article_id": article.id,
            "title": article.title,
            "source_name": source_name,
            "publisher": metadata["publisher"],
            "author": metadata["author"],
            "published_at": _serialize_datetime(published_at),
            "published_human": published_human,
            "url": article.url,
            "trust_score": trust_score,
            "trust_badge": extractor.trust_badge(trust_score),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Citation lookup failed for article_id=%s", article_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Citation lookup failed",
        ) from exc


def _serialize_datetime(value: Any) -> str | None:
    """Serialize datetime-like values for JSON responses."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
