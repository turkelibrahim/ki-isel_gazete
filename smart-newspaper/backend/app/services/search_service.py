"""Search service that combines BM25 ranking with SQL article retrieval."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.search.bm25_engine import BM25Engine
from app.models import Article

logger = logging.getLogger(__name__)


class SearchService:
    """Application service for keyword search over duplicate-free news."""

    def __init__(self, engine: BM25Engine | None = None) -> None:
        """Initialize the service with the singleton BM25 engine."""
        self.engine = engine or BM25Engine()

    async def rebuild_index(self, db: AsyncSession) -> dict[str, Any]:
        """Rebuild and return BM25 index status."""
        return await self.engine.rebuild(db)

    async def search_articles(self, db: AsyncSession, query: str, top: int = 20) -> dict[str, Any]:
        """Search articles by keyword and preserve the BM25 rank order."""
        cleaned_query = (query or "").strip()
        if not cleaned_query:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query parameter q is required")

        if not self.engine.is_ready:
            try:
                await self.engine.rebuild(db)
            except Exception:
                logger.exception("Lazy BM25 rebuild failed; returning empty search results")

        hits = self.engine.search(cleaned_query, top_n=top)
        if not hits:
            return {
                "query": cleaned_query,
                "top": top,
                "count": 0,
                "items": [],
                "engine": self.engine.status(),
            }

        article_ids = [int(hit["article_id"]) for hit in hits]
        rank_by_id = {int(hit["article_id"]): hit for hit in hits}
        result = await db.execute(
            select(Article).where(Article.id.in_(article_ids), Article.is_duplicate.is_(False))
        )
        articles_by_id = {int(article.id): article for article in result.scalars().all()}
        items = []
        for article_id in article_ids:
            article = articles_by_id.get(article_id)
            if article is None:
                continue
            hit = rank_by_id[article_id]
            items.append(_serialize_article(article, score=float(hit["score"]), rank=int(hit["rank"])))

        return {
            "query": cleaned_query,
            "top": top,
            "count": len(items),
            "items": items,
            "engine": self.engine.status(),
        }

    def status(self) -> dict[str, Any]:
        """Return BM25 engine status."""
        return self.engine.status()


def _serialize_article(article: Article, score: float, rank: int) -> dict[str, Any]:
    """Serialize article search result data."""
    published_at = getattr(article, "published_at", None)
    return {
        "article_id": article.id,
        "id": article.id,
        "rank": rank,
        "score": score,
        "title": article.title,
        "summary": getattr(article, "summary", None),
        "url": article.url,
        "language": getattr(article, "language", "unknown"),
        "source_id": article.source_id,
        "view_count": int(getattr(article, "view_count", 0) or 0),
        "published_at": published_at.isoformat() if hasattr(published_at, "isoformat") else str(published_at),
    }
