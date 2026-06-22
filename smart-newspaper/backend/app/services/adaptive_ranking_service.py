"""Adaptive online ranking service for user category interests."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ArticleCategory, Category, UserInterest

logger = logging.getLogger(__name__)


class AdaptiveRankingService:
    """Update and use ``user_interests.weight`` from online user feedback.

    The service intentionally performs an application-level SELECT + UPDATE for
    user_interests, because Prompt 35 requested no migration and deployments may
    not yet have a UNIQUE(user_id, category_id) constraint everywhere.
    """

    ALPHA = 0.1
    POSITIVE_EVENTS = {"READ", "BOOKMARKED", "SHARED"}
    NEGATIVE_EVENTS = {"SKIPPED", "UNBOOKMARKED"}

    async def update_weights_from_event(
        self,
        db: AsyncSession,
        user_id: str | int,
        article_id: int,
        event_type: str,
        implicit_rating: float | None = None,
    ) -> dict[str, Any]:
        """Update all article category weights for a user event.

        If the article has multiple categories, every category is updated. Each
        category's classifier confidence scales ``ALPHA`` through
        ``effective_alpha = ALPHA * confidence``. Missing confidence uses ALPHA.
        """
        normalized_user_id = _normalize_user_id(user_id)
        normalized_event = _normalize_event_type(event_type)
        if normalized_event not in self.POSITIVE_EVENTS | self.NEGATIVE_EVENTS:
            return {
                "status": "ignored",
                "reason": "event_type_not_adaptive",
                "user_id": normalized_user_id,
                "article_id": article_id,
                "event_type": normalized_event,
                "updates": [],
            }

        article = await db.get(Article, article_id)
        if article is None:
            return {
                "status": "not_found",
                "reason": "article_not_found",
                "user_id": normalized_user_id,
                "article_id": article_id,
                "event_type": normalized_event,
                "updates": [],
            }

        result = await db.execute(select(ArticleCategory).where(ArticleCategory.article_id == article_id))
        article_categories = list(result.scalars().all())
        if not article_categories:
            return {
                "status": "no_categories",
                "user_id": normalized_user_id,
                "article_id": article_id,
                "event_type": normalized_event,
                "updates": [],
            }

        updates: list[dict[str, Any]] = []
        for assignment in article_categories:
            confidence = _safe_confidence(getattr(assignment, "confidence", None))
            updates.append(
                await self.update_category_weight(
                    db=db,
                    user_id=normalized_user_id,
                    category_id=int(assignment.category_id),
                    event_type=normalized_event,
                    confidence=confidence,
                    commit=False,
                )
            )
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception(
                "Adaptive ranking commit failed user_id=%s article_id=%s event_type=%s",
                normalized_user_id,
                article_id,
                normalized_event,
            )
            raise

        return {
            "status": "updated",
            "user_id": normalized_user_id,
            "article_id": article_id,
            "event_type": normalized_event,
            "implicit_rating": implicit_rating,
            "updates": updates,
        }

    async def update_category_weight(
        self,
        db: AsyncSession,
        user_id: str | int,
        category_id: int,
        event_type: str,
        confidence: float | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        """Update one user/category weight with the Prompt 35 online formula."""
        normalized_user_id = _normalize_user_id(user_id)
        normalized_event = _normalize_event_type(event_type)
        if normalized_event not in self.POSITIVE_EVENTS | self.NEGATIVE_EVENTS:
            return {
                "status": "ignored",
                "category_id": category_id,
                "event_type": normalized_event,
                "old_weight": None,
                "new_weight": None,
                "delta": 0.0,
            }

        is_positive = normalized_event in self.POSITIVE_EVENTS
        initial_weight = 0.5 if is_positive else 0.2
        effective_alpha = self.ALPHA * _safe_confidence(confidence)

        result = await db.execute(
            select(UserInterest).where(
                UserInterest.user_id == normalized_user_id,
                UserInterest.category_id == category_id,
            )
        )
        interest = result.scalars().first()
        if interest is None:
            old_weight = initial_weight
            interest = UserInterest(
                user_id=normalized_user_id,
                category_id=category_id,
                weight=old_weight,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(interest)
        else:
            old_weight = _clamp(float(getattr(interest, "weight", 0.0) or 0.0))

        if is_positive:
            new_weight = old_weight + effective_alpha * (1.0 - old_weight)
        else:
            new_weight = old_weight - effective_alpha * old_weight
        new_weight = _clamp(new_weight)
        interest.weight = new_weight
        interest.updated_at = datetime.now(timezone.utc)

        if commit:
            try:
                await db.commit()
                await db.refresh(interest)
            except Exception:
                await db.rollback()
                logger.exception(
                    "Adaptive category update failed user_id=%s category_id=%s event_type=%s",
                    normalized_user_id,
                    category_id,
                    normalized_event,
                )
                raise

        return {
            "status": "updated",
            "user_id": normalized_user_id,
            "category_id": int(category_id),
            "event_type": normalized_event,
            "old_weight": round(old_weight, 6),
            "new_weight": round(new_weight, 6),
            "delta": round(new_weight - old_weight, 6),
            "alpha": round(effective_alpha, 6),
            "confidence": _safe_confidence(confidence),
        }

    async def get_user_interest_vector(self, db: AsyncSession, user_id: str | int) -> dict[str, Any]:
        """Return one user's category interest vector."""
        normalized_user_id = _normalize_user_id(user_id)
        result = await db.execute(
            select(UserInterest, Category)
            .join(Category, Category.id == UserInterest.category_id, isouter=True)
            .where(UserInterest.user_id == normalized_user_id)
            .order_by(UserInterest.weight.desc())
        )
        interests = []
        for interest, category in result.all():
            interests.append(
                {
                    "category_id": int(interest.category_id),
                    "category_name": getattr(category, "name", None),
                    "category_slug": getattr(category, "slug", None),
                    "weight": round(float(interest.weight or 0.0), 6),
                    "updated_at": _dt_to_iso(getattr(interest, "updated_at", None)),
                }
            )
        return {"user_id": normalized_user_id, "interests": interests, "total": len(interests)}

    async def rank_articles_with_interests(
        self,
        db: AsyncSession,
        user_id: str | int,
        articles: list[Any],
    ) -> list[dict[str, Any]]:
        """Rank articles by combining existing recommendation score and interest score.

        Formula: ``0.70 * existing_recommendation_score + 0.30 * interest_score``.
        If no existing score is present, the fallback is 0.5.
        """
        normalized_user_id = _normalize_user_id(user_id)
        article_ids = [_extract_article_id(article) for article in articles]
        article_ids = [article_id for article_id in article_ids if article_id is not None]
        if not article_ids:
            return []

        interest_map = await self._load_interest_weights(db, normalized_user_id)
        category_map = await self._load_article_categories(db, article_ids)

        ranked: list[dict[str, Any]] = []
        for article in articles:
            article_id = _extract_article_id(article)
            if article_id is None:
                continue
            existing_score = _extract_existing_score(article)
            interest_score = self._calculate_interest_score(category_map.get(article_id, []), interest_map)
            final_score = 0.70 * existing_score + 0.30 * interest_score
            row = _article_to_dict(article)
            row.update(
                {
                    "article_id": article_id,
                    "existing_recommendation_score": round(existing_score, 6),
                    "interest_score": round(interest_score, 6),
                    "adaptive_score": round(_clamp(final_score), 6),
                }
            )
            ranked.append(row)
        ranked.sort(key=lambda row: float(row.get("adaptive_score", 0.0)), reverse=True)
        return ranked

    async def reset_user_interests(self, db: AsyncSession, user_id: str | int) -> dict[str, Any]:
        """Delete a user's learned category weights."""
        normalized_user_id = _normalize_user_id(user_id)
        result = await db.execute(select(UserInterest).where(UserInterest.user_id == normalized_user_id))
        existing = list(result.scalars().all())
        count = len(existing)
        await db.execute(delete(UserInterest).where(UserInterest.user_id == normalized_user_id))
        await db.commit()
        return {"status": "reset", "user_id": normalized_user_id, "deleted": count}

    async def _load_interest_weights(self, db: AsyncSession, user_id: str) -> dict[int, float]:
        result = await db.execute(select(UserInterest).where(UserInterest.user_id == user_id))
        return {int(row.category_id): _clamp(float(row.weight or 0.0)) for row in result.scalars().all()}

    async def _load_article_categories(self, db: AsyncSession, article_ids: list[int]) -> dict[int, list[tuple[int, float]]]:
        result = await db.execute(select(ArticleCategory).where(ArticleCategory.article_id.in_(article_ids)))
        mapping: dict[int, list[tuple[int, float]]] = {}
        for row in result.scalars().all():
            mapping.setdefault(int(row.article_id), []).append((int(row.category_id), _safe_confidence(row.confidence)))
        return mapping

    def _calculate_interest_score(self, categories: list[tuple[int, float]], interests: dict[int, float]) -> float:
        if not categories:
            return 0.5
        numerator = 0.0
        denominator = 0.0
        for category_id, confidence in categories:
            category_confidence = _safe_confidence(confidence)
            numerator += category_confidence * interests.get(category_id, 0.0)
            denominator += category_confidence
        if denominator <= 0:
            return 0.5
        return _clamp(numerator / denominator)


def _normalize_user_id(user_id: str | int) -> str:
    cleaned = str(user_id).strip()
    if not cleaned:
        raise ValueError("user_id is required")
    return cleaned


def _normalize_event_type(event_type: str) -> str:
    return str(event_type or "").strip().upper()


def _safe_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 1.0
    if confidence <= 0:
        return 1.0
    return _clamp(confidence)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _extract_article_id(article: Any) -> int | None:
    if isinstance(article, dict):
        value = article.get("article_id", article.get("id"))
    else:
        value = getattr(article, "id", getattr(article, "article_id", None))
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _extract_existing_score(article: Any) -> float:
    if isinstance(article, dict):
        for key in ("existing_recommendation_score", "recommendation_score", "adaptive_score", "final_score", "score"):
            if article.get(key) is not None:
                return _clamp(float(article[key]))
        return 0.5
    for key in ("existing_recommendation_score", "recommendation_score", "adaptive_score", "final_score", "score"):
        value = getattr(article, key, None)
        if value is not None:
            return _clamp(float(value))
    return 0.5


def _article_to_dict(article: Any) -> dict[str, Any]:
    if isinstance(article, dict):
        return dict(article)
    return {
        "id": getattr(article, "id", None),
        "title": getattr(article, "title", None),
        "summary": getattr(article, "summary", None),
        "url": getattr(article, "url", None),
        "language": getattr(article, "language", None),
        "view_count": int(getattr(article, "view_count", 0) or 0),
        "published_at": _dt_to_iso(getattr(article, "published_at", None)),
    }


def _dt_to_iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)
