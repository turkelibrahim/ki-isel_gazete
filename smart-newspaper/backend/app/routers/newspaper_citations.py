"""Citation endpoints for the personal newspaper module."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Article, Source
from app.services.citation_service import CitationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/newspaper", tags=["newspaper-citations"])
citation_service = CitationService()


class BatchCitationRequest(BaseModel):
    """Request body for batch citation generation."""

    article_ids: list[int] = Field(..., min_length=1, max_length=100)


@router.get("/articles/{article_id}/citation")
async def get_newspaper_article_citation(article_id: int) -> dict[str, Any]:
    """Return personal-newspaper citation metadata for one article."""
    try:
        async with AsyncSessionLocal() as db:
            article = await _load_article_with_source(db, article_id)
        if article is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        return citation_service.build_article_citation(article)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Newspaper citation lookup failed article_id=%s", article_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Newspaper citation lookup failed",
        ) from exc


@router.post("/citations/batch")
async def get_newspaper_citations_batch(payload: BatchCitationRequest) -> dict[str, Any]:
    """Return article_id keyed citation metadata for multiple articles."""
    try:
        article_ids = list(dict.fromkeys(payload.article_ids))
        async with AsyncSessionLocal() as db:
            rows = await _load_articles_with_sources(db, article_ids)
        citations = citation_service.build_citations(rows)
        return {
            "items": citations,
            "requested": len(article_ids),
            "found": len(citations),
            "missing_ids": [article_id for article_id in article_ids if article_id not in citations],
        }
    except Exception as exc:
        logger.exception("Batch newspaper citation lookup failed ids=%s", payload.article_ids)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch newspaper citation lookup failed",
        ) from exc


async def _load_article_with_source(db, article_id: int) -> dict[str, Any] | None:  # type: ignore[no-untyped-def]
    """Load one article with flattened source metadata."""
    rows = await _load_articles_with_sources(db, [article_id])
    return rows[0] if rows else None


async def _load_articles_with_sources(db, article_ids: list[int]) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    """Load articles and source fields while preserving requested order."""
    if not article_ids:
        return []
    stmt = (
        select(Article, Source.name, Source.base_url, Source.trust_score)
        .join(Source, Article.source_id == Source.id, isouter=True)
        .where(Article.id.in_(article_ids))
    )
    rows = (await db.execute(stmt)).all()
    by_id = {
        int(article.id): _serialize_article_for_citation(article, source_name, source_url, trust_score)
        for article, source_name, source_url, trust_score in rows
    }
    return [by_id[article_id] for article_id in article_ids if article_id in by_id]


def _serialize_article_for_citation(
    article: Article,
    source_name: str | None,
    source_url: str | None,
    trust_score: float | None,
) -> dict[str, Any]:
    """Convert an ORM row into CitationService input."""
    published_at = article.published_at.isoformat() if isinstance(article.published_at, datetime) else article.published_at
    return {
        "id": article.id,
        "article_id": article.id,
        "title": article.title,
        "url": article.url,
        "article_url": article.url,
        "source_id": article.source_id,
        "source_name": source_name or None,
        "source_url": source_url or "#",
        "source_trust_score": float(trust_score if trust_score is not None else 0.5),
        "published_at": published_at,
    }
