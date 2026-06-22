"""Engagement analytics service for user behavior, article and source metrics."""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from fastapi import HTTPException, status
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ArticleCategory, Category, Source, User, UserBookmark, UserEvent

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Cache kapalı: admin rapor/analytics ekranı her istekte güncel aggregation üretir.
ANALYTICS_CACHE_TTL_SECONDS = 0


class AnalyticsService:
    """Produce admin/reporting analytics from engagement and content tables.

    Cache disabled. Every method uses fresh SQL aggregation so admin dashboard
    never shows stale analytics during development.
    """

    EVENT_WEIGHTS: dict[str, float] = {
        "VIEWED": 0.3,
        "READ": 1.0,
        "BOOKMARKED": 1.5,
        "SHARED": 2.0,
        "SKIPPED": 0.0,
        "UNBOOKMARKED": 0.0,
    }

    POSITIVE_READ_EVENTS = ("READ", "BOOKMARKED", "SHARED")

    async def get_daily_active_users(self, db: AsyncSession, days: int = 30) -> list[dict[str, Any]]:
        """Return distinct active users grouped by day for the last N days."""
        safe_days = _clamp_int(days, minimum=1, maximum=365, default=30)
        cache_key = f"analytics:dau:{safe_days}:0"
        cached = await self._cache_get(cache_key)
        if isinstance(cached, list):
            return cached

        since = _utc_now() - timedelta(days=safe_days)
        day_expr = func.date(UserEvent.created_at).label("event_date")
        stmt = (
            select(day_expr, func.count(func.distinct(UserEvent.user_id)).label("active_users"))
            .where(UserEvent.created_at >= since)
            .group_by(day_expr)
            .order_by(day_expr)
        )
        rows = (await db.execute(stmt)).all()
        payload = [
            {
                "date": _date_to_iso(row.event_date),
                "active_users": int(row.active_users or 0),
            }
            for row in rows
        ]
        await self._cache_set(cache_key, payload)
        return payload

    async def get_top_articles(self, db: AsyncSession, days: int = 7, limit: int = 20) -> list[dict[str, Any]]:
        """Return top non-duplicate articles by weighted engagement score."""
        safe_days = _clamp_int(days, minimum=1, maximum=365, default=7)
        safe_limit = _clamp_int(limit, minimum=1, maximum=100, default=20)
        cache_key = f"analytics:top_articles:{safe_days}:{safe_limit}"
        cached = await self._cache_get(cache_key)
        if isinstance(cached, list):
            return cached

        since = _utc_now() - timedelta(days=safe_days)
        read_count = func.sum(case((UserEvent.event_type == "READ", 1), else_=0)).label("read_count")
        bookmark_count = func.sum(case((UserEvent.event_type == "BOOKMARKED", 1), else_=0)).label("bookmark_count")
        share_count = func.sum(case((UserEvent.event_type == "SHARED", 1), else_=0)).label("share_count")
        view_events = func.sum(case((UserEvent.event_type == "VIEWED", 1), else_=0)).label("view_events")
        engagement_score = _weighted_engagement_expr().label("engagement_score")

        stmt = (
            select(
                Article.id,
                Article.title,
                Article.summary,
                Article.url,
                Article.view_count,
                Article.published_at,
                Source.name.label("source_name"),
                read_count,
                bookmark_count,
                share_count,
                view_events,
                engagement_score,
            )
            .join(UserEvent, UserEvent.article_id == Article.id)
            .outerjoin(Source, Source.id == Article.source_id)
            .where(UserEvent.created_at >= since, Article.is_duplicate.is_(False))
            .group_by(Article.id, Article.title, Article.summary, Article.url, Article.view_count, Article.published_at, Source.name)
            .order_by(desc(engagement_score), desc(Article.view_count), desc(Article.published_at))
            .limit(safe_limit)
        )
        rows = (await db.execute(stmt)).all()
        payload = [
            {
                "article_id": int(row.id),
                "title": row.title,
                "summary": row.summary,
                "url": row.url,
                "source": row.source_name,
                "view_count": int(row.view_count or 0),
                "engagement_score": round(float(row.engagement_score or 0.0), 4),
                "read_count": int(row.read_count or 0),
                "bookmark_count": int(row.bookmark_count or 0),
                "share_count": int(row.share_count or 0),
                "view_events": int(row.view_events or 0),
                "published_at": _dt_to_iso(row.published_at),
            }
            for row in rows
        ]
        await self._cache_set(cache_key, payload)
        return payload

    async def get_category_reads(self, db: AsyncSession, days: int = 30) -> list[dict[str, Any]]:
        """Return category-level engagement/read statistics."""
        safe_days = _clamp_int(days, minimum=1, maximum=365, default=30)
        cache_key = f"analytics:categories:{safe_days}:0"
        cached = await self._cache_get(cache_key)
        if isinstance(cached, list):
            return cached

        since = _utc_now() - timedelta(days=safe_days)
        read_count = func.sum(case((UserEvent.event_type == "READ", 1), else_=0)).label("read_count")
        unique_users = func.count(func.distinct(UserEvent.user_id)).label("unique_users")
        avg_duration = func.avg(UserEvent.duration_seconds).label("avg_duration_seconds")
        avg_scroll = func.avg(UserEvent.scroll_percent).label("avg_scroll_percent")
        engagement_score = _weighted_engagement_expr().label("engagement_score")

        stmt = (
            select(
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                read_count,
                unique_users,
                avg_duration,
                avg_scroll,
                engagement_score,
            )
            .join(ArticleCategory, ArticleCategory.category_id == Category.id)
            .join(Article, Article.id == ArticleCategory.article_id)
            .join(UserEvent, UserEvent.article_id == Article.id)
            .where(
                UserEvent.created_at >= since,
                UserEvent.event_type.in_(self.POSITIVE_READ_EVENTS),
                Article.is_duplicate.is_(False),
            )
            .group_by(Category.id, Category.name)
            .order_by(desc(engagement_score), desc(unique_users))
        )
        rows = (await db.execute(stmt)).all()
        payload = [
            {
                "category_id": int(row.category_id),
                "category_name": row.category_name,
                "read_count": int(row.read_count or 0),
                "unique_users": int(row.unique_users or 0),
                "avg_duration_seconds": round(float(row.avg_duration_seconds or 0.0), 2),
                "avg_scroll_percent": round(float(row.avg_scroll_percent or 0.0), 2),
                "engagement_score": round(float(row.engagement_score or 0.0), 4),
            }
            for row in rows
        ]
        await self._cache_set(cache_key, payload)
        return payload

    async def get_user_analytics(self, db: AsyncSession, user_id: str | int, days: int = 30) -> dict[str, Any]:
        """Return one user's engagement summary and favorite categories."""
        normalized_user_id = _normalize_user_id(user_id)
        safe_days = _clamp_int(days, minimum=1, maximum=365, default=30)
        since = _utc_now() - timedelta(days=safe_days)

        user = (await db.execute(select(User).where(User.id == normalized_user_id))).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        counts_stmt = (
            select(
                func.count(UserEvent.id).label("total_events"),
                func.sum(case((UserEvent.event_type == "READ", 1), else_=0)).label("read_count"),
                func.sum(case((UserEvent.event_type == "BOOKMARKED", 1), else_=0)).label("bookmark_count"),
                func.sum(case((UserEvent.event_type == "SHARED", 1), else_=0)).label("share_count"),
                func.avg(UserEvent.duration_seconds).label("avg_duration_seconds"),
                func.avg(UserEvent.scroll_percent).label("avg_scroll_percent"),
                func.max(UserEvent.created_at).label("last_active_at"),
            )
            .where(UserEvent.user_id == normalized_user_id, UserEvent.created_at >= since)
        )
        stats = (await db.execute(counts_stmt)).one()

        favorite_stmt = (
            select(
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                _weighted_engagement_expr().label("engagement_score"),
                func.count(UserEvent.id).label("event_count"),
            )
            .join(ArticleCategory, ArticleCategory.category_id == Category.id)
            .join(UserEvent, UserEvent.article_id == ArticleCategory.article_id)
            .where(UserEvent.user_id == normalized_user_id, UserEvent.created_at >= since)
            .group_by(Category.id, Category.name)
            .order_by(desc("engagement_score"))
            .limit(10)
        )
        favorite_rows = (await db.execute(favorite_stmt)).all()
        favorite_categories = [
            {
                "category_id": int(row.category_id),
                "category_name": row.category_name,
                "engagement_score": round(float(row.engagement_score or 0.0), 4),
                "event_count": int(row.event_count or 0),
            }
            for row in favorite_rows
        ]

        return {
            "user_id": normalized_user_id,
            "email": getattr(user, "email", None),
            "days": safe_days,
            "total_events": int(stats.total_events or 0),
            "read_count": int(stats.read_count or 0),
            "bookmark_count": int(stats.bookmark_count or 0),
            "share_count": int(stats.share_count or 0),
            "avg_duration_seconds": round(float(stats.avg_duration_seconds or 0.0), 2),
            "avg_scroll_percent": round(float(stats.avg_scroll_percent or 0.0), 2),
            "favorite_categories": favorite_categories,
            "last_active_at": _dt_to_iso(stats.last_active_at),
        }

    async def get_source_performance(self, db: AsyncSession, days: int = 30) -> list[dict[str, Any]]:
        """Return source-level article, view, trust and engagement metrics."""
        safe_days = _clamp_int(days, minimum=1, maximum=365, default=30)
        cache_key = f"analytics:sources:{safe_days}:0"
        cached = await self._cache_get(cache_key)
        if isinstance(cached, list):
            return cached

        since = _utc_now() - timedelta(days=safe_days)
        article_metrics = (
            select(
                Article.source_id.label("source_id"),
                func.count(func.distinct(Article.id)).label("article_count"),
                func.sum(Article.view_count).label("total_views"),
            )
            .where(Article.created_at >= since, Article.is_duplicate.is_(False))
            .group_by(Article.source_id)
            .subquery()
        )
        event_metrics = (
            select(
                Article.source_id.label("source_id"),
                _weighted_engagement_expr().label("engagement_score"),
            )
            .join(UserEvent, UserEvent.article_id == Article.id)
            .where(UserEvent.created_at >= since, Article.is_duplicate.is_(False))
            .group_by(Article.source_id)
            .subquery()
        )
        stmt = (
            select(
                Source.id,
                Source.name,
                Source.base_url,
                Source.trust_score,
                article_metrics.c.article_count,
                article_metrics.c.total_views,
                event_metrics.c.engagement_score,
            )
            .outerjoin(article_metrics, article_metrics.c.source_id == Source.id)
            .outerjoin(event_metrics, event_metrics.c.source_id == Source.id)
            .order_by(desc(func.coalesce(event_metrics.c.engagement_score, 0.0)), desc(func.coalesce(article_metrics.c.total_views, 0)))
        )
        rows = (await db.execute(stmt)).all()
        payload = [
            {
                "source_id": int(row.id),
                "source_name": row.name,
                "base_url": row.base_url,
                "article_count": int(row.article_count or 0),
                "total_views": int(row.total_views or 0),
                "avg_trust_score": round(float(row.trust_score or 0.5), 4),
                "trust_score": round(float(row.trust_score or 0.5), 4),
                "engagement_score": round(float(row.engagement_score or 0.0), 4),
            }
            for row in rows
        ]
        await self._cache_set(cache_key, payload)
        return payload

    async def get_overview(self, db: AsyncSession) -> dict[str, Any]:
        """Return a compact dashboard overview for admin/reporting screens."""
        cache_key = "analytics:overview:0:0"
        cached = await self._cache_get(cache_key)
        if isinstance(cached, dict):
            return cached

        now = _utc_now()
        active_since = now - timedelta(days=7)
        total_users = int((await db.execute(select(func.count(User.id)))).scalar_one() or 0)
        total_articles = int((await db.execute(select(func.count(Article.id)))).scalar_one() or 0)
        total_events = int((await db.execute(select(func.count(UserEvent.id)))).scalar_one() or 0)
        total_bookmarks = int((await db.execute(select(func.count(UserBookmark.id)))).scalar_one() or 0)
        active_users_7d = int(
            (
                await db.execute(
                    select(func.count(func.distinct(UserEvent.user_id))).where(UserEvent.created_at >= active_since)
                )
            ).scalar_one()
            or 0
        )
        top_categories = await self.get_category_reads(db, days=30)
        top_articles = await self.get_top_articles(db, days=7, limit=1)
        payload = {
            "total_users": total_users,
            "total_articles": total_articles,
            "total_events": total_events,
            "total_bookmarks": total_bookmarks,
            "active_users_7d": active_users_7d,
            "top_category": top_categories[0] if top_categories else None,
            "top_article": top_articles[0] if top_articles else None,
            "generated_at": _dt_to_iso(now),
        }
        await self._cache_set(cache_key, payload)
        return payload

    async def _cache_get(self, key: str) -> Any | None:
        """Cache disabled: always force fresh SQL aggregation."""
        return None

    async def _cache_set(self, key: str, payload: Any) -> None:
        """Cache disabled: no-op."""
        return None


async def _get_redis():
    """Return an async Redis client or None when redis-py is unavailable."""
    try:
        import redis.asyncio as redis_async
    except Exception:
        return None
    return redis_async.from_url(REDIS_URL, decode_responses=True)


def _weighted_engagement_expr():
    """Return SQLAlchemy expression for weighted engagement score."""
    return func.sum(
        case(
            (UserEvent.event_type == "VIEWED", 0.3),
            (UserEvent.event_type == "READ", 1.0),
            (UserEvent.event_type == "BOOKMARKED", 1.5),
            (UserEvent.event_type == "SHARED", 2.0),
            else_=0.0,
        )
    )


def _clamp_int(value: int | str | None, minimum: int, maximum: int, default: int) -> int:
    """Convert and clamp int-like query values."""
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(min(parsed, maximum), minimum)


def _normalize_user_id(user_id: str | int) -> str:
    """Normalize user IDs to the current string primary-key schema."""
    cleaned = str(user_id).strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")
    return cleaned


def _utc_now() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(timezone.utc)


def _dt_to_iso(value: Any) -> str | None:
    """Serialize datetime values safely."""
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def _date_to_iso(value: Any) -> str:
    """Serialize date-like grouping values as YYYY-MM-DD strings."""
    if isinstance(value, (datetime, date)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    return str(value)
