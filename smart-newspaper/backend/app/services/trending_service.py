"""Temporal-decay trending article service for Module 6."""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ArticleCategory, Source

logger = logging.getLogger(__name__)

LAMBDA_DECAY = 0.05
DEFAULT_WINDOW_HOURS = 72
DEFAULT_CACHE_TTL_SECONDS = 0
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Cache kapalı: her trending isteği güncel DB verisinden hesaplanır.
TRENDING_CACHE_TTL_SECONDS = 0


class TrendingService:
    """Rank recent articles by popularity with exponential temporal decay."""

    def calculate_trend_score(self, article: Article, now: datetime | None = None) -> float:
        """Calculate ``view_count * exp(-0.05 * hours_since_published)``.

        Args:
            article: Article-like ORM object containing ``view_count`` and ``published_at``.
            now: Optional clock for deterministic tests.

        Returns:
            Non-negative trend score. Missing ``published_at`` uses a 24-hour fallback.
        """
        view_count = int(getattr(article, "view_count", 0) or 0)
        published_at = getattr(article, "published_at", None)
        hours_old = self._hours_since_published(published_at, now=now)
        return float(view_count) * math.exp(-LAMBDA_DECAY * hours_old)

    async def get_trending_articles(
        self,
        db: AsyncSession,
        limit: int = 20,
        window_hours: int = DEFAULT_WINDOW_HOURS,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return trending articles from the last ``window_hours`` with optional filters.

        Filters support ``category_id``, ``language`` and ``source_ids``. Duplicate
        articles are always excluded.
        """
        safe_limit = max(1, min(int(limit or 20), 100))
        safe_window = max(1, min(int(window_hours or DEFAULT_WINDOW_HOURS), 24 * 14))
        normalized_filters = _normalize_filters(filters)
        # Cache kapalı: eski trend listesi dönmesin.
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=safe_window)
        stmt = (
            select(Article, Source.name.label("source_name"))
            .outerjoin(Source, Article.source_id == Source.id)
            .where(Article.is_duplicate.is_(False))
            .where(Article.published_at >= window_start)
        )

        category_id = normalized_filters.get("category_id")
        if category_id is not None:
            stmt = stmt.join(ArticleCategory, Article.id == ArticleCategory.article_id).where(
                ArticleCategory.category_id == int(category_id)
            )

        language = normalized_filters.get("language")
        if language:
            stmt = stmt.where(Article.language == str(language))

        source_ids = normalized_filters.get("source_ids")
        if source_ids:
            stmt = stmt.where(Article.source_id.in_([int(source_id) for source_id in source_ids]))

        rows = (await db.execute(stmt.distinct())).all()
        items: list[dict[str, Any]] = []
        for row in rows:
            try:
                article: Article = row[0]
                source_name = row[1]
                hours_old = self._hours_since_published(getattr(article, "published_at", None), now=now)
                trend_score = self.calculate_trend_score(article, now=now)
                items.append(_serialize_trending_article(article, source_name, hours_old, trend_score))
            except Exception:
                logger.exception("Failed to serialize trending article row")
                continue

        items.sort(key=lambda item: float(item.get("trend_score", 0.0)), reverse=True)
        top_items = items[:safe_limit]
        return top_items

    async def get_trending_by_category(self, db: AsyncSession, category_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """Return trending articles for one category using the default 72-hour window."""
        return await self.get_trending_articles(db, limit=limit, window_hours=DEFAULT_WINDOW_HOURS, filters={"category_id": category_id})

    async def refresh_trending_cache(self, db: AsyncSession) -> dict[str, Any]:
        """Refresh the default cache entry used by the public trending endpoint."""
        items = await self.get_trending_articles(db, limit=20, window_hours=DEFAULT_WINDOW_HOURS, filters=None)
        return {
            "status": "refreshed_without_cache",
            "items": len(items),
            "window_hours": DEFAULT_WINDOW_HOURS,
            "cache_ttl_seconds": 0,
            "cache_enabled": False,
        }

    def _hours_since_published(self, published_at: Any, now: datetime | None = None) -> float:
        """Return hours since publication with the required 24-hour fallback."""
        if not isinstance(published_at, datetime):
            return 24.0
        clock = now or datetime.now(timezone.utc)
        if clock.tzinfo is None:
            clock = clock.replace(tzinfo=timezone.utc)
        else:
            clock = clock.astimezone(timezone.utc)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        else:
            published_at = published_at.astimezone(timezone.utc)
        return max((clock - published_at).total_seconds() / 3600.0, 0.0)

    async def _get_cached_trending(
        self,
        limit: int,
        window_hours: int,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        """Cache disabled: always return None so fresh DB data is used."""
        return None

    async def _set_cached_trending(
        self,
        limit: int,
        window_hours: int,
        filters: dict[str, Any],
        payload: list[dict[str, Any]],
    ) -> None:
        """Cache disabled: no-op."""
        return None

async def _get_redis():
    """Return a Redis async client or None when redis-py is unavailable."""
    try:
        import redis.asyncio as redis_async
    except Exception:
        return None
    return redis_async.from_url(REDIS_URL, decode_responses=True)


def _normalize_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize filter values for SQL and cache keys."""
    if not filters:
        return {}
    normalized: dict[str, Any] = {}
    category_id = filters.get("category_id")
    if category_id is not None:
        try:
            normalized["category_id"] = int(category_id)
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid trending category_id=%r", category_id)
    language = filters.get("language")
    if language:
        normalized["language"] = str(language).strip().lower()
    source_ids = filters.get("source_ids")
    if source_ids:
        if isinstance(source_ids, str):
            source_ids = [part.strip() for part in source_ids.split(",") if part.strip()]
        cleaned: list[int] = []
        for source_id in source_ids:
            try:
                value = int(source_id)
            except (TypeError, ValueError):
                continue
            if value > 0 and value not in cleaned:
                cleaned.append(value)
        if cleaned:
            normalized["source_ids"] = cleaned
    return normalized


def _cache_key(limit: int, window_hours: int, filters: dict[str, Any]) -> str:
    """Return Redis key for one trending query."""
    language = filters.get("language") or "all"
    category_id = filters.get("category_id") or "all"
    source_ids = "-".join(str(item) for item in filters.get("source_ids") or []) or "all"
    return f"trending:{language}:{category_id}:{source_ids}:{window_hours}:{limit}"


def _serialize_trending_article(article: Article, source_name: str | None, hours_old: float, trend_score: float) -> dict[str, Any]:
    """Serialize article data for trending responses."""
    published_at = getattr(article, "published_at", None)
    return {
        "article_id": article.id,
        "id": article.id,
        "title": article.title,
        "summary": getattr(article, "summary", None),
        "source_id": getattr(article, "source_id", None),
        "source_name": source_name or f"Source #{getattr(article, 'source_id', '')}",
        "published_at": published_at.isoformat() if hasattr(published_at, "isoformat") else None,
        "view_count": int(getattr(article, "view_count", 0) or 0),
        "hours_old": round(float(hours_old), 4),
        "trend_score": round(float(trend_score), 6),
        "url": getattr(article, "url", None),
        "language": getattr(article, "language", "unknown"),
    }
