"""Service layer for extracting and persisting article keywords."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.keyword_extractor import KeywordExtractor
from app.models import Article, ArticleKeyword
from app.services.classification_service import build_article_text

logger = logging.getLogger(__name__)


async def extract_and_save_keywords(db: AsyncSession, article_id: int, top_n: int = 15) -> dict[str, Any]:
    """Extract keywords for one article and replace previous keyword rows."""
    article = await db.get(Article, article_id)
    if article is None:
        raise ValueError(f"Article {article_id} not found")

    extractor = KeywordExtractor()
    keywords = extractor.extract(build_article_text(article), top_n=top_n)

    await db.execute(delete(ArticleKeyword).where(ArticleKeyword.article_id == article.id))
    rows: list[ArticleKeyword] = []
    seen: set[str] = set()
    for item in keywords[:top_n]:
        keyword = str(item["keyword"]).strip().lower()
        if not keyword or keyword in seen:
            continue
        seen.add(keyword)
        row = ArticleKeyword(article_id=article.id, keyword=keyword, score=float(item["score"]))
        db.add(row)
        rows.append(row)
    await db.commit()
    return {"article_id": article.id, "count": len(rows), "keywords": keywords[:top_n]}


async def get_article_keywords(db: AsyncSession, article_id: int) -> list[dict[str, Any]]:
    """Return saved keywords for one article sorted by score."""
    stmt = (
        select(ArticleKeyword)
        .where(ArticleKeyword.article_id == article_id)
        .order_by(ArticleKeyword.score.desc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return [{"keyword": row.keyword, "score": row.score} for row in rows]


async def extract_keywords_batch(db: AsyncSession, limit: int = 50, top_n: int = 15) -> dict[str, Any]:
    """Extract and save keywords for a batch of recent articles."""
    stmt = select(Article).order_by(Article.created_at.desc()).limit(limit)
    articles = list((await db.execute(stmt)).scalars().all())
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for article in articles:
        try:
            results.append(await extract_and_save_keywords(db, article.id, top_n=top_n))
        except Exception as exc:  # pragma: no cover - defensive batch isolation
            logger.exception("Keyword extraction failed article_id=%s", article.id)
            await db.rollback()
            errors.append({"article_id": article.id, "error": str(exc)})
    return {"processed": len(results), "errors": len(errors), "items": results, "error_items": errors}
