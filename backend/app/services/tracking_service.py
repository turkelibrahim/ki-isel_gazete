"""User behavior tracking and implicit feedback conversion service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, UserEvent

logger = logging.getLogger(__name__)


class TrackingService:
    """Record user events and convert them into implicit recommendation ratings."""

    EVENT_WEIGHTS: dict[str, float] = {
        "SHARED": 2.0,
        "BOOKMARKED": 1.5,
        "READ": 1.0,
        "VIEWED": 0.3,
        "SKIPPED": 0.0,
        "UNBOOKMARKED": 0.0,
    }

    POSITIVE_EVENTS = {"VIEWED", "READ", "BOOKMARKED", "SHARED"}
    VALID_EVENTS = set(EVENT_WEIGHTS)

    async def track_event(
        self,
        db: AsyncSession,
        user_id: str | int,
        article_id: int,
        event_type: str,
        duration_seconds: int | float | None = None,
        scroll_percent: float | None = None,
    ) -> dict[str, Any]:
        """Persist one user behavior event and return its implicit feedback score.

        TODO(auth): replace the temporary ``user_id`` parameter with the authenticated
        ``current_user.id`` once the auth dependency is connected.
        """
        normalized_user_id = _normalize_user_id(user_id)
        article = await self._get_article_or_404(db, article_id)
        normalized_type = self._normalize_event_type(event_type, duration_seconds, scroll_percent)
        implicit_rating = self.calculate_implicit_rating(normalized_type, duration_seconds, scroll_percent)

        event = UserEvent(
            user_id=normalized_user_id,
            article_id=article.id,
            event_type=normalized_type,
            duration_seconds=float(duration_seconds) if duration_seconds is not None else None,
            scroll_percent=float(scroll_percent) if scroll_percent is not None else None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        if normalized_type in {"VIEWED", "READ"}:
            await self.increment_view_count(db, article.id, commit=False)

        try:
            await db.commit()
            await db.refresh(event)
            await db.refresh(article)
        except Exception:
            await db.rollback()
            logger.exception("Could not track event user_id=%s article_id=%s", normalized_user_id, article_id)
            raise

        await self._invalidate_recommendation_cache(normalized_user_id)
        await self._update_adaptive_ranking_hook(
            db=db,
            user_id=normalized_user_id,
            article_id=article.id,
            event_type=normalized_type,
            implicit_rating=implicit_rating,
        )

        return {
            "status": "tracked",
            "event_id": event.id,
            "user_id": normalized_user_id,
            "article_id": article.id,
            "event_type": normalized_type,
            "duration_seconds": event.duration_seconds,
            "scroll_percent": event.scroll_percent,
            "implicit_rating": implicit_rating,
            "view_count": int(getattr(article, "view_count", 0) or 0),
            "created_at": _dt_to_iso(event.created_at),
        }

    def calculate_implicit_rating(
        self,
        event_type: str,
        duration_seconds: int | float | None = None,
        scroll_percent: float | None = None,
    ) -> float:
        """Convert one behavior event into an implicit rating.

        Formula: ``weight * min(scroll_percent / 100, 1.0)``. When scroll is
        missing, event-specific fallbacks are used as specified by Module 7.
        """
        normalized_type = self._normalize_event_type(event_type, duration_seconds, scroll_percent)
        weight = self.EVENT_WEIGHTS.get(normalized_type, 0.0)
        if weight <= 0:
            return 0.0

        scroll_factor = self._scroll_factor(normalized_type, scroll_percent)
        rating = weight * scroll_factor
        return round(float(max(rating, 0.0)), 6)

    async def get_user_article_rating(self, db: AsyncSession, user_id: str | int, article_id: int) -> float:
        """Return the strongest implicit signal for one user/article pair."""
        normalized_user_id = _normalize_user_id(user_id)
        result = await db.execute(
            select(UserEvent).where(
                UserEvent.user_id == normalized_user_id,
                UserEvent.article_id == article_id,
            )
        )
        events = list(result.scalars().all())
        if not events:
            return 0.0
        return max(
            self.calculate_implicit_rating(event.event_type, event.duration_seconds, event.scroll_percent)
            for event in events
        )

    async def get_user_ratings_matrix(self, db: AsyncSession) -> list[dict[str, Any]]:
        """Return max implicit rating rows aggregated by user/article.

        Multiple events for the same user/article use MAX signal logic rather
        than summing repeated weak interactions.
        """
        result = await db.execute(select(UserEvent))
        events = list(result.scalars().all())
        ratings: dict[tuple[str, int], float] = {}
        counts: dict[tuple[str, int], int] = {}
        last_seen: dict[tuple[str, int], datetime | None] = {}
        for event in events:
            key = (str(event.user_id), int(event.article_id))
            rating = self.calculate_implicit_rating(event.event_type, event.duration_seconds, event.scroll_percent)
            ratings[key] = max(ratings.get(key, 0.0), rating)
            counts[key] = counts.get(key, 0) + 1
            last_seen[key] = event.created_at
        return [
            {
                "user_id": user_id,
                "article_id": article_id,
                "rating": rating,
                "event_count": counts[(user_id, article_id)],
                "last_event_at": _dt_to_iso(last_seen.get((user_id, article_id))),
            }
            for (user_id, article_id), rating in sorted(ratings.items(), key=lambda item: (item[0][0], item[0][1]))
        ]

    async def increment_view_count(self, db: AsyncSession, article_id: int, commit: bool = True) -> None:
        """Increment article view_count for VIEWED and READ events."""
        article = await self._get_article_or_404(db, article_id)
        article.view_count = int(getattr(article, "view_count", 0) or 0) + 1
        if commit:
            await db.commit()

    async def get_user_ratings(self, db: AsyncSession, user_id: str | int) -> dict[str, Any]:
        """Return max implicit ratings for one user across all articles."""
        normalized_user_id = _normalize_user_id(user_id)
        result = await db.execute(select(UserEvent).where(UserEvent.user_id == normalized_user_id))
        events = list(result.scalars().all())
        items = self._aggregate_max_ratings(events)
        return {
            "user_id": normalized_user_id,
            "items": items,
            "total": len(items),
            "event_weights": dict(self.EVENT_WEIGHTS),
            "aggregation": "max_signal",
        }

    async def get_article_stats(self, db: AsyncSession, article_id: int) -> dict[str, Any]:
        """Return basic event counts and view_count for one article."""
        article = await self._get_article_or_404(db, article_id)
        result = await db.execute(
            select(UserEvent.event_type, func.count(UserEvent.id))
            .where(UserEvent.article_id == article_id)
            .group_by(UserEvent.event_type)
        )
        counts = {str(event_type): int(count) for event_type, count in result.all()}
        total_events = sum(counts.values())
        unique_users = int(
            (
                await db.execute(
                    select(func.count(func.distinct(UserEvent.user_id))).where(UserEvent.article_id == article_id)
                )
            ).scalar_one()
            or 0
        )
        return {
            "article_id": article.id,
            "title": article.title,
            "view_count": int(getattr(article, "view_count", 0) or 0),
            "event_counts": counts,
            "total_events": total_events,
            "unique_users": unique_users,
        }

    def _normalize_event_type(
        self,
        event_type: str,
        duration_seconds: int | float | None = None,
        scroll_percent: float | None = None,
    ) -> str:
        """Normalize and optionally promote/demote event type by behavior signals."""
        normalized = str(event_type or "VIEWED").strip().upper()
        if normalized not in self.VALID_EVENTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported event_type: {event_type}")

        duration = _safe_float(duration_seconds)
        scroll = _safe_float(scroll_percent)
        if normalized in {"VIEWED", "READ"}:
            if duration is not None and scroll is not None and duration < 5 and scroll < 10:
                return "SKIPPED"
            if duration is not None and duration >= 30 and normalized == "VIEWED":
                return "READ"
        return normalized

    def _scroll_factor(self, event_type: str, scroll_percent: float | None) -> float:
        """Return scroll factor with Module 7 fallbacks when scroll is missing."""
        if scroll_percent is not None:
            try:
                return min(max(float(scroll_percent), 0.0) / 100.0, 1.0)
            except (TypeError, ValueError):
                logger.debug("Invalid scroll_percent=%r, using fallback", scroll_percent)
        if event_type == "VIEWED":
            return 0.1
        if event_type == "READ":
            return 0.8
        if event_type in {"BOOKMARKED", "SHARED"}:
            return 1.0
        return 0.0

    def _aggregate_max_ratings(self, events: Iterable[UserEvent]) -> list[dict[str, Any]]:
        """Aggregate SQLAlchemy UserEvent objects with MAX signal logic."""
        ratings: dict[int, dict[str, Any]] = {}
        for event in events:
            rating = self.calculate_implicit_rating(event.event_type, event.duration_seconds, event.scroll_percent)
            existing = ratings.get(int(event.article_id))
            if existing is None or rating > float(existing["rating"]):
                ratings[int(event.article_id)] = {
                    "article_id": int(event.article_id),
                    "rating": rating,
                    "strongest_event_type": event.event_type,
                    "duration_seconds": event.duration_seconds,
                    "scroll_percent": event.scroll_percent,
                    "created_at": _dt_to_iso(event.created_at),
                }
        return sorted(ratings.values(), key=lambda row: float(row["rating"]), reverse=True)

    async def _get_article_or_404(self, db: AsyncSession, article_id: int) -> Article:
        """Fetch an article or raise a controlled 404 response."""
        article = await db.get(Article, article_id)
        if article is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        return article

    async def _invalidate_recommendation_cache(self, user_id: str) -> None:
        """Invalidate Module 3 personalized feed cache without breaking tracking."""
        try:
            from app.services.recommendation_service import invalidate_personal_feed_cache

            await invalidate_personal_feed_cache(user_id)
        except Exception:
            logger.warning("Recommendation cache invalidation failed user_id=%s", user_id, exc_info=True)

    async def _update_adaptive_ranking_hook(
        self,
        db: AsyncSession,
        user_id: str,
        article_id: int,
        event_type: str,
        implicit_rating: float,
    ) -> None:
        """Call AdaptiveRankingService if a later module provides it."""
        try:
            from app.services.adaptive_ranking_service import AdaptiveRankingService  # type: ignore

            service = AdaptiveRankingService()
            maybe_result = service.update_weights_from_event(
                db=db,
                user_id=user_id,
                article_id=article_id,
                event_type=event_type,
                implicit_rating=implicit_rating,
            )
            if hasattr(maybe_result, "__await__"):
                await maybe_result
        except ModuleNotFoundError:
            return
        except Exception:
            logger.warning("Adaptive ranking hook failed user_id=%s article_id=%s", user_id, article_id, exc_info=True)


def _normalize_user_id(user_id: str | int) -> str:
    """Normalize temporary user identifiers for current schema."""
    cleaned = str(user_id).strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")
    return cleaned


def _safe_float(value: Any) -> float | None:
    """Safely coerce optional numeric values."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dt_to_iso(value: Any) -> str | None:
    """Serialize datetime-like values to ISO strings."""
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)
