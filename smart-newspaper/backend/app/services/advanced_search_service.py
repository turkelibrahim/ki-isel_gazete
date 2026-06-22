"""BM25 + SQL hybrid advanced search service."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Integer, String, column, desc, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.search.bm25_engine import BM25Engine
from app.models import Article, ArticleCategory
from app.schemas.search_filters import SearchFilterParams
from app.services.trending_service import TrendingService

logger = logging.getLogger(__name__)

# Dynamic table keeps P28 migration-free while allowing SQL joins if the table exists in DB.
UserBookmarkTable = table(
    "user_bookmarks",
    column("user_id", String),
    column("article_id", Integer),
)


class AdvancedSearchService:
    """Combine BM25 relevance ranking with category/source/date/language SQL filters."""

    def __init__(self, engine: BM25Engine | None = None) -> None:
        """Initialize the service with the shared singleton BM25 engine."""
        self.engine = engine or BM25Engine()
        self.trending_service = TrendingService()

    async def advanced_search(
        self,
        db: AsyncSession,
        user_id: str | int | None,
        params: SearchFilterParams,
    ) -> dict[str, Any]:
        """Run BM25 when q exists, then apply SQL filters and pagination."""
        normalized_user_id = str(user_id) if user_id is not None else None
        bm25_ids: list[int] | None = None
        bm25_score_map: dict[int, float] = {}
        bm25_rank_map: dict[int, int] = {}

        if params.q:
            if not self.engine.is_ready:
                try:
                    await self.engine.rebuild(db)
                except Exception:
                    logger.exception("Lazy BM25 rebuild failed during advanced search")
            hits = self.engine.search(params.q, top_n=200)
            bm25_ids = [int(hit["article_id"]) for hit in hits]
            bm25_score_map = {int(hit["article_id"]): float(hit["score"]) for hit in hits}
            bm25_rank_map = {int(hit["article_id"]): int(hit["rank"]) for hit in hits}
            if not bm25_ids:
                return _empty_response(params, normalized_user_id)

        stmt = self._build_filtered_query(params, normalized_user_id, bm25_ids)

        runtime_sort = bool(params.q and params.sort_by == "relevance") or params.sort_by == "trend"
        if runtime_sort:
            articles = list((await db.execute(stmt.distinct())).scalars().all())
            articles = self._runtime_sort(articles, params, bm25_score_map)
            total = len(articles)
            offset = (params.page - 1) * params.page_size
            page_articles = articles[offset : offset + params.page_size]
        else:
            total = await _count_total(db, stmt.distinct())
            ordered = self._apply_sql_sort(stmt.distinct(), params.sort_by)
            offset = (params.page - 1) * params.page_size
            page_articles = list((await db.execute(ordered.offset(offset).limit(params.page_size))).scalars().all())

        items = [
            _serialize_article(
                article,
                rank=offset + index + 1,
                bm25_score=bm25_score_map.get(int(article.id)),
                bm25_rank=bm25_rank_map.get(int(article.id)),
                trend_score=self.trending_service.calculate_trend_score(article) if params.sort_by == "trend" else None,
            )
            for index, article in enumerate(page_articles)
        ]

        return {
            "items": items,
            "page": params.page,
            "page_size": params.page_size,
            "total": total,
            "has_next": offset + len(page_articles) < total,
            "filters_applied": _filters_applied(params, normalized_user_id),
        }

    def _build_filtered_query(
        self,
        params: SearchFilterParams,
        user_id: str | None,
        bm25_ids: list[int] | None,
    ):
        """Build the SQL statement with only filters that are present."""
        stmt = select(Article).where(Article.is_duplicate.is_(False))

        if bm25_ids is not None:
            stmt = stmt.where(Article.id.in_(bm25_ids))

        if params.category_ids:
            stmt = stmt.join(ArticleCategory, Article.id == ArticleCategory.article_id).where(
                ArticleCategory.category_id.in_(params.category_ids)
            )

        if params.source_ids:
            stmt = stmt.where(Article.source_id.in_(params.source_ids))

        if params.date_from is not None:
            stmt = stmt.where(Article.published_at >= params.date_from)

        if params.date_to is not None:
            stmt = stmt.where(Article.published_at <= params.date_to)

        if params.language:
            stmt = stmt.where(Article.language == params.language)

        if params.only_bookmarked:
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="user_id is required when only_bookmarked=true",
                )
            stmt = stmt.join(UserBookmarkTable, Article.id == UserBookmarkTable.c.article_id).where(
                UserBookmarkTable.c.user_id == user_id
            )

        return stmt

    def _apply_sql_sort(self, stmt, sort_by: str):  # type: ignore[no-untyped-def]
        """Apply SQL-side sorting when runtime relevance/trend sorting is not needed."""
        if sort_by == "popularity":
            return stmt.order_by(desc(Article.view_count), desc(Article.published_at))
        # q-less relevance falls back to date as requested.
        return stmt.order_by(desc(Article.published_at))

    def _runtime_sort(
        self,
        articles: list[Article],
        params: SearchFilterParams,
        bm25_score_map: dict[int, float],
    ) -> list[Article]:
        """Sort filtered ORM rows by BM25 relevance or temporal trend score."""
        if params.sort_by == "trend":
            return sorted(articles, key=self.trending_service.calculate_trend_score, reverse=True)
        if params.q:
            return sorted(articles, key=lambda article: bm25_score_map.get(int(article.id), 0.0), reverse=True)
        return sorted(articles, key=lambda article: getattr(article, "published_at", datetime.min), reverse=True)


async def _count_total(db: AsyncSession, stmt) -> int:  # type: ignore[no-untyped-def]
    """Count filtered rows from a statement."""
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    result = await db.execute(count_stmt)
    return int(result.scalar_one() or 0)



def _serialize_article(
    article: Article,
    rank: int,
    bm25_score: float | None,
    bm25_rank: int | None,
    trend_score: float | None,
) -> dict[str, Any]:
    """Serialize an article row with optional search/trend scoring metadata."""
    published_at = getattr(article, "published_at", None)
    return {
        "id": article.id,
        "article_id": article.id,
        "rank": rank,
        "bm25_score": bm25_score,
        "bm25_rank": bm25_rank,
        "trend_score": trend_score,
        "title": article.title,
        "summary": getattr(article, "summary", None),
        "url": article.url,
        "language": getattr(article, "language", "unknown"),
        "source_id": article.source_id,
        "view_count": int(getattr(article, "view_count", 0) or 0),
        "published_at": published_at.isoformat() if hasattr(published_at, "isoformat") else str(published_at),
    }


def _filters_applied(params: SearchFilterParams, user_id: str | None) -> dict[str, Any]:
    """Return transparent filter metadata in API responses."""
    return {
        "q": params.q,
        "category_ids": params.category_ids,
        "source_ids": params.source_ids,
        "date_from": params.date_from.isoformat() if params.date_from else None,
        "date_to": params.date_to.isoformat() if params.date_to else None,
        "language": params.language,
        "only_bookmarked": params.only_bookmarked,
        "user_id": user_id,
        "sort_by": params.sort_by,
        "exclude_duplicates": True,
        "bm25_top_n": 200 if params.q else None,
    }


def _empty_response(params: SearchFilterParams, user_id: str | None) -> dict[str, Any]:
    """Return a standard empty advanced-search response."""
    return {
        "items": [],
        "page": params.page,
        "page_size": params.page_size,
        "total": 0,
        "has_next": False,
        "filters_applied": _filters_applied(params, user_id),
    }
