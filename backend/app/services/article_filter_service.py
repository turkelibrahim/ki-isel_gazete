"""Dynamic SQL article filtering service for Module 3 / P13."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ArticleCategory, User
from app.schemas.article_filters import FilterParams

logger = logging.getLogger(__name__)


async def filter_articles(db: AsyncSession, params: FilterParams) -> dict[str, Any]:
    """Filter duplicate-free articles by category, source, date, language, and sort order.

    The query is built incrementally so unused filters do not add unnecessary joins.
    Pagination is offset/limit based and returns total plus has_next metadata.
    """
    language = await _resolve_language(db, params)
    stmt = select(Article).where(Article.is_duplicate.is_(False))

    if params.category_id is not None:
        stmt = stmt.join(ArticleCategory, Article.id == ArticleCategory.article_id).where(
            ArticleCategory.category_id == params.category_id
        )

    if params.source_ids:
        stmt = stmt.where(Article.source_id.in_(params.source_ids))

    if params.date_from is not None:
        stmt = stmt.where(Article.published_at >= params.date_from)

    if params.date_to is not None:
        stmt = stmt.where(Article.published_at <= params.date_to)

    if language:
        stmt = stmt.where(Article.language == language)

    stmt = stmt.distinct()
    total = await _count_total(db, stmt)
    ordered = _apply_sort(stmt, params.sort_by)
    offset = (params.page - 1) * params.page_size
    page_stmt = ordered.offset(offset).limit(params.page_size)
    articles = list((await db.execute(page_stmt)).scalars().all())

    return {
        "items": [_serialize_article(article) for article in articles],
        "page": params.page,
        "page_size": params.page_size,
        "total": total,
        "has_next": offset + len(articles) < total,
        "filters_applied": _filters_applied(params, language),
    }


async def _resolve_language(db: AsyncSession, params: FilterParams) -> str | None:
    """Resolve explicit language first, then user language preference if user_id exists."""
    if params.language:
        return params.language
    if not params.user_id:
        return None
    try:
        user = await db.get(User, params.user_id)
        return (getattr(user, "language_preference", None) or "tr").strip().lower() if user else "tr"
    except Exception:
        logger.warning("Could not resolve user language preference for user_id=%s", params.user_id, exc_info=True)
        return "tr"


async def _count_total(db: AsyncSession, stmt) -> int:  # type: ignore[no-untyped-def]
    """Count rows from a filtered statement without page ordering."""
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    result = await db.execute(count_stmt)
    return int(result.scalar_one() or 0)


def _apply_sort(stmt, sort_by: str):  # type: ignore[no-untyped-def]
    """Apply date, popularity, or relevance ordering with safe fallback."""
    if sort_by == "popularity":
        return stmt.order_by(desc(Article.view_count), desc(Article.published_at))
    if sort_by == "relevance" and hasattr(Article, "priority_score"):
        return stmt.order_by(desc(getattr(Article, "priority_score")), desc(Article.published_at))
    return stmt.order_by(desc(Article.published_at))


def _filters_applied(params: FilterParams, resolved_language: str | None) -> dict[str, Any]:
    """Return a transparent summary of filters applied by the API."""
    return {
        "category_id": params.category_id,
        "source_ids": params.source_ids,
        "date_from": params.date_from.isoformat() if params.date_from else None,
        "date_to": params.date_to.isoformat() if params.date_to else None,
        "language": resolved_language,
        "user_id": params.user_id,
        "sort_by": params.sort_by,
        "exclude_duplicates": True,
    }


def _serialize_article(article: Article) -> dict[str, Any]:
    """Serialize an Article ORM row for filter API responses."""
    published_at = _dt_to_iso(getattr(article, "published_at", None))
    created_at = _dt_to_iso(getattr(article, "created_at", None))
    return {
        "id": article.id,
        "title": article.title,
        "summary": getattr(article, "summary", None),
        "content": getattr(article, "content", ""),
        "url": article.url,
        "language": getattr(article, "language", "unknown"),
        "source_id": article.source_id,
        "view_count": int(getattr(article, "view_count", 0) or 0),
        "is_duplicate": bool(getattr(article, "is_duplicate", False)),
        "published_at": published_at,
        "created_at": created_at,
    }


def _dt_to_iso(value: Any) -> str | None:
    """Return ISO text for datetime values and None for missing values."""
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)
