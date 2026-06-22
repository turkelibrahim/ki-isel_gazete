"""Personalized news-feed service using hybrid recommendation."""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.recommenders.content_based import ContentBasedRecommender
from app.ml.recommenders.hybrid_recommender import ALPHA, BETA, HybridRecommender
from app.ml.recommenders.user_cf import EVENT_WEIGHTS, UserCollaborativeFilter
from app.ml.recommender.analytics_hybrid_recommender import AnalyticsHybridRecommender
from app.services.recommender_training_service import IBCF_MODEL_PATH, SVD_MODEL_PATH
from app.models import Article, ArticleCategory, Category, Source, User, UserEvent, UserInterest

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = int(os.getenv("PERSONAL_FEED_CACHE_TTL_SECONDS", "300"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_CONTENT_RECOMMENDER = ContentBasedRecommender()
_CF_RECOMMENDER = UserCollaborativeFilter()
_HYBRID_RECOMMENDER = HybridRecommender()
_LAST_INDEX_STATE: dict[str, Any] = {"indexed_articles": 0, "rebuilt_at": None}


def build_article_text(article: Article) -> str:
    """Combine article fields into the recommender text representation."""
    title = getattr(article, "title", "") or ""
    summary = getattr(article, "summary", "") or getattr(article, "description", "") or ""
    content = getattr(article, "content", "") or ""
    return f"{title} {summary} {content[:1000]}".strip()


async def get_personalized_feed(db: AsyncSession, user_id: str, limit: int = 30) -> dict[str, Any]:
    """Return a personalized feed for a user with hybrid or cold-start ranking."""
    user = await db.get(User, user_id)
    language = (getattr(user, "language_preference", None) or "tr").strip() or "tr"
    cached = await _get_cached_feed(user_id, language)
    if cached is not None:
        cached["cache"] = "hit"
        return cached

    article_rows = await _load_candidate_articles(db, language)
    if not article_rows:
        response = _build_response(user_id, language, [], "empty", limit, {"reason": "no_candidate_articles"})
        await _set_cached_feed(user_id, language, response)
        return response

    events = await _load_events(db)
    user_events = [event for event in events if event["user_id"] == user_id]
    read_article_ids = _read_article_ids(user_events)
    article_id_set = {int(row["id"]) for row in article_rows}
    exclude_ids = read_article_ids & article_id_set

    recommendations: list[dict[str, Any]] = []
    algorithm = "cold_start"
    debug: dict[str, Any] = {
        "read_article_count": len(read_article_ids),
        "candidate_article_count": len(article_rows),
        "language": language,
        "weights": {"content_based": ALPHA, "collaborative_filtering": BETA},
    }

    if read_article_ids:
        _CONTENT_RECOMMENDER.index_articles(article_rows)
        _LAST_INDEX_STATE.update(
            {
                "indexed_articles": len(article_rows),
                "rebuilt_at": datetime.now(timezone.utc).isoformat(),
                "language": language,
            }
        )
        profile = _CONTENT_RECOMMENDER.build_profile(list(read_article_ids))
        cb_scores = _CONTENT_RECOMMENDER.recommend(profile, exclude_ids=exclude_ids, limit=max(limit * 4, 100))
        cf_scores = _CF_RECOMMENDER.recommend(
            user_id=user_id,
            events=events,
            candidate_article_ids=article_id_set,
            exclude_ids=exclude_ids,
            limit=max(limit * 4, 100),
        )
        analytics_scores = _analytics_hybrid_scores(
            user_id=user_id,
            candidate_article_ids=article_id_set - exclude_ids,
            cb_scores=cb_scores,
            article_rows=article_rows,
            limit=limit,
        )
        if analytics_scores:
            recommendations = _attach_articles(analytics_scores, article_rows)
            algorithm = "analytics_hybrid_cb30_ibcf35_svd25_trending10"
            debug.update(
                {
                    "analytics_hybrid_used": True,
                    "analytics_hybrid_candidates": len(analytics_scores),
                    "module7_weights": {"content_based": 0.30, "ibcf": 0.35, "svd": 0.25, "trending": 0.10},
                }
            )
        else:
            hybrid_scores = _HYBRID_RECOMMENDER.combine(cb_scores, cf_scores, limit=limit)
            recommendations = _attach_articles(hybrid_scores, article_rows)
            algorithm = "hybrid_cb60_cf40" if recommendations else "cold_start_after_empty_hybrid"
            debug.update({"analytics_hybrid_used": False, "hybrid_candidates": len(hybrid_scores)})
        debug.update({"cb_candidates": len(cb_scores), "cf_candidates": len(cf_scores)})

    if not recommendations:
        recommendations = await _cold_start_feed(db, user_id, language, limit)
        debug["cold_start_used"] = True

    try:
        from app.services.adaptive_ranking_service import AdaptiveRankingService

        adaptive_ranked = await AdaptiveRankingService().rank_articles_with_interests(db, user_id, recommendations)
        if adaptive_ranked:
            recommendations = adaptive_ranked
            algorithm = f"{algorithm}+adaptive_interests"
            debug["adaptive_ranking_used"] = True
            debug["adaptive_formula"] = "0.70 existing_recommendation_score + 0.30 interest_score"
    except Exception:
        logger.warning("Adaptive ranking could not be applied user_id=%s", user_id, exc_info=True)
        debug["adaptive_ranking_used"] = False

    response = _build_response(user_id, language, recommendations[:limit], algorithm, limit, debug)
    await _set_cached_feed(user_id, language, response)
    return response


async def rebuild_recommendation_index(db: AsyncSession, language: str | None = None) -> dict[str, Any]:
    """Rebuild the content-based index for duplicate-free articles."""
    rows = await _load_candidate_articles(db, language)
    indexed = _CONTENT_RECOMMENDER.index_articles(rows)
    _LAST_INDEX_STATE.update(
        {
            "indexed_articles": indexed,
            "rebuilt_at": datetime.now(timezone.utc).isoformat(),
            "language": language or "all",
        }
    )
    return dict(_LAST_INDEX_STATE)


async def get_recommendation_debug(db: AsyncSession, user_id: str | None = None) -> dict[str, Any]:
    """Return non-sensitive recommender status for diagnostics."""
    event_count = len(await _load_events(db))
    debug: dict[str, Any] = {
        "content_index": dict(_LAST_INDEX_STATE),
        "hybrid_weights": {"content_based": ALPHA, "collaborative_filtering": BETA},
        "module7_hybrid_weights": {"content_based": 0.30, "ibcf": 0.35, "svd": 0.25, "trending": 0.10},
        "module7_models": {"ibcf_exists": IBCF_MODEL_PATH.exists(), "svd_exists": SVD_MODEL_PATH.exists()},
        "event_weights": EVENT_WEIGHTS,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "event_count": event_count,
    }
    if user_id:
        user = await db.get(User, user_id)
        debug["user_id"] = user_id
        debug["language"] = (getattr(user, "language_preference", None) or "tr") if user else "tr"
    return debug


async def invalidate_personal_feed_cache(user_id: str, language: str | None = None) -> None:
    """Invalidate cached feed for a user after a new event is recorded."""
    try:
        redis = await _get_redis()
        if redis is None:
            return
        if language:
            await redis.delete(_cache_key(user_id, language))
        else:
            pattern = f"personal_feed:{user_id}:*"
            async for key in redis.scan_iter(pattern):
                await redis.delete(key)
        await redis.aclose()
    except Exception:
        logger.warning("Could not invalidate personal feed cache user_id=%s", user_id, exc_info=True)


async def _load_candidate_articles(db: AsyncSession, language: str | None = None) -> list[dict[str, Any]]:
    """Load duplicate-free articles with source trust for recommendation."""
    stmt = (
        select(Article, Source.trust_score)
        .join(Source, Article.source_id == Source.id, isouter=True)
        .where(Article.is_duplicate.is_(False))
        .order_by(desc(Article.published_at))
    )
    if language:
        stmt = stmt.where(Article.language == language)
    rows = (await db.execute(stmt)).all()
    return [_article_row(article, trust_score) for article, trust_score in rows]


async def _load_events(db: AsyncSession) -> list[dict[str, Any]]:
    """Load user events needed for collaborative filtering."""
    stmt = select(UserEvent)
    events = list((await db.execute(stmt)).scalars().all())
    return [
        {
            "user_id": event.user_id,
            "article_id": event.article_id,
            "event_type": event.event_type,
            "duration_seconds": event.duration_seconds,
            "scroll_percent": event.scroll_percent,
        }
        for event in events
    ]


def _read_article_ids(events: Iterable[dict[str, Any]]) -> set[int]:
    """Return articles with positive interaction events."""
    ids: set[int] = set()
    for event in events:
        if EVENT_WEIGHTS.get(str(event.get("event_type") or "").upper(), 0.0) > 0:
            try:
                ids.add(int(event["article_id"]))
            except (KeyError, TypeError, ValueError):
                continue
    return ids


async def _cold_start_feed(db: AsyncSession, user_id: str, language: str, limit: int) -> list[dict[str, Any]]:
    """Return category-interest fallback or popular trusted recent articles."""
    interest_rows = await _load_interest_articles(db, user_id, language)
    if interest_rows:
        interest_rows.sort(key=lambda row: float(row["score"]), reverse=True)
        return interest_rows[:limit]
    popular = await _load_popular_trusted_articles(db, language)
    return popular[:limit]


async def _load_interest_articles(db: AsyncSession, user_id: str, language: str) -> list[dict[str, Any]]:
    """Load articles matching user interest category weights."""
    stmt = (
        select(Article, Source.trust_score, UserInterest.weight, ArticleCategory.confidence, Category.name)
        .join(ArticleCategory, Article.id == ArticleCategory.article_id)
        .join(UserInterest, UserInterest.category_id == ArticleCategory.category_id)
        .join(Category, Category.id == ArticleCategory.category_id)
        .join(Source, Source.id == Article.source_id, isouter=True)
        .where(UserInterest.user_id == user_id)
        .where(Article.is_duplicate.is_(False))
        .where(Article.language == language)
        .order_by(desc(UserInterest.weight), desc(Article.published_at))
    )
    rows = (await db.execute(stmt)).all()
    items: dict[int, dict[str, Any]] = {}
    max_views = max([int(getattr(article, "view_count", 0) or 0) for article, *_rest in rows] or [1])
    for article, trust_score, interest_weight, category_confidence, category_name in rows:
        view_norm = (int(getattr(article, "view_count", 0) or 0) / max_views) if max_views else 0.0
        trust = float(trust_score if trust_score is not None else 0.5)
        score = 0.55 * float(interest_weight or 0.0) + 0.20 * float(category_confidence or 0.0) + 0.15 * view_norm + 0.10 * trust
        row = _article_row(article, trust)
        row.update({"score": float(score), "algorithm": "cold_start_interests", "matched_category": category_name})
        existing = items.get(article.id)
        if existing is None or float(row["score"]) > float(existing["score"]):
            items[article.id] = row
    return list(items.values())


async def _load_popular_trusted_articles(db: AsyncSession, language: str) -> list[dict[str, Any]]:
    """Load recent popular and trusted articles for full cold start."""
    recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    stmt = (
        select(Article, Source.trust_score)
        .join(Source, Source.id == Article.source_id, isouter=True)
        .where(Article.is_duplicate.is_(False))
        .where(Article.language == language)
        .order_by(desc(Article.published_at))
    )
    rows = (await db.execute(stmt)).all()
    max_views = max([int(getattr(article, "view_count", 0) or 0) for article, _trust in rows] or [1])
    items: list[dict[str, Any]] = []
    for article, trust_score in rows:
        published_at = article.published_at
        if isinstance(published_at, datetime) and published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        recency = 1.0 if isinstance(published_at, datetime) and published_at >= recent_cutoff else 0.35
        view_norm = (int(getattr(article, "view_count", 0) or 0) / max_views) if max_views else 0.0
        trust = float(trust_score if trust_score is not None else 0.5)
        score = 0.40 * recency + 0.30 * view_norm + 0.30 * trust
        row = _article_row(article, trust)
        row.update({"score": float(score), "algorithm": "cold_start_popular_trusted"})
        items.append(row)
    items.sort(key=lambda row: float(row["score"]), reverse=True)
    return items


def _analytics_hybrid_scores(
    user_id: str,
    candidate_article_ids: set[int],
    cb_scores: list[dict[str, float | int]],
    article_rows: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Return Module 7 analytics-hybrid scores when IBCF/SVD models exist.

    If model files are missing or not loadable, the old Module 3 hybrid
    recommender remains the active fallback.
    """
    try:
        if not (Path(IBCF_MODEL_PATH).exists() or Path(SVD_MODEL_PATH).exists()):
            return []
        recommender = AnalyticsHybridRecommender(IBCF_MODEL_PATH, SVD_MODEL_PATH)
        if not recommender.has_models():
            return []
        cb_score_map = {int(row["article_id"]): float(row.get("score") or 0.0) for row in cb_scores}
        trend_score_map = _trend_scores_from_article_rows(article_rows)
        return recommender.recommend(
            user_id=user_id,
            candidate_article_ids=candidate_article_ids,
            content_based_scores=cb_score_map,
            trending_scores=trend_score_map,
            limit=limit,
        )
    except Exception:
        logger.warning("Analytics hybrid recommender unavailable; falling back to Module 3 hybrid", exc_info=True)
        return []


def _trend_scores_from_article_rows(article_rows: list[dict[str, Any]]) -> dict[int, float]:
    """Calculate Module 6 trending scores from serialized article rows."""
    now = datetime.now(timezone.utc)
    scores: dict[int, float] = {}
    for row in article_rows:
        try:
            article_id = int(row["id"])
            view_count = int(row.get("view_count") or 0)
            published_raw = row.get("published_at")
            if isinstance(published_raw, datetime):
                published_at = published_raw
            elif published_raw:
                published_at = datetime.fromisoformat(str(published_raw).replace("Z", "+00:00"))
            else:
                published_at = now - timedelta(hours=24)
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            hours_old = max((now - published_at).total_seconds() / 3600.0, 0.0)
            scores[article_id] = float(view_count) * math.exp(-0.05 * hours_old)
        except Exception:
            logger.debug("Could not calculate recommendation trend score row=%s", row, exc_info=True)
    return scores


def _attach_articles(score_rows: list[dict[str, Any]], article_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach article metadata to ML score rows."""
    by_id = {int(row["id"]): row for row in article_rows}
    attached: list[dict[str, Any]] = []
    for score_row in score_rows:
        article = by_id.get(int(score_row["article_id"]))
        if article is None:
            continue
        merged = dict(article)
        merged.update(score_row)
        merged["id"] = article["id"]
        attached.append(merged)
    return attached


def _article_row(article: Article, trust_score: float | None = None) -> dict[str, Any]:
    """Serialize article metadata used by recommendation responses."""
    published_at = article.published_at.isoformat() if isinstance(article.published_at, datetime) else article.published_at
    created_at = article.created_at.isoformat() if isinstance(article.created_at, datetime) else article.created_at
    return {
        "id": article.id,
        "article_id": article.id,
        "title": article.title,
        "summary": getattr(article, "summary", None),
        "content": article.content,
        "url": article.url,
        "language": article.language,
        "source_id": article.source_id,
        "source_trust_score": float(trust_score if trust_score is not None else 0.5),
        "view_count": int(getattr(article, "view_count", 0) or 0),
        "published_at": published_at,
        "created_at": created_at,
        "text": build_article_text(article),
    }


def _build_response(
    user_id: str,
    language: str,
    items: list[dict[str, Any]],
    algorithm: str,
    limit: int,
    debug: dict[str, Any],
) -> dict[str, Any]:
    """Build the API response envelope."""
    clean_items = []
    for item in items:
        row = {key: value for key, value in item.items() if key != "text"}
        row.setdefault("score", 0.0)
        clean_items.append(row)
    return {
        "user_id": user_id,
        "language": language,
        "algorithm": algorithm,
        "limit": limit,
        "count": len(clean_items),
        "items": clean_items,
        "debug": debug,
        "cache": "miss",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _get_cached_feed(user_id: str, language: str) -> dict[str, Any] | None:
    """Read a cached feed from Redis when available."""
    try:
        redis = await _get_redis()
        if redis is None:
            return None
        raw = await redis.get(_cache_key(user_id, language))
        await redis.aclose()
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except Exception:
        logger.warning("Redis personal feed cache read failed", exc_info=True)
        return None


async def _set_cached_feed(user_id: str, language: str, payload: dict[str, Any]) -> None:
    """Store a feed in Redis for five minutes when Redis is available."""
    try:
        redis = await _get_redis()
        if redis is None:
            return
        await redis.setex(_cache_key(user_id, language), CACHE_TTL_SECONDS, json.dumps(payload, ensure_ascii=False, default=str))
        await redis.aclose()
    except Exception:
        logger.warning("Redis personal feed cache write failed", exc_info=True)


async def _get_redis():
    """Return a Redis async client, or None if redis-py is unavailable."""
    try:
        import redis.asyncio as redis_async
    except Exception:
        return None
    return redis_async.from_url(REDIS_URL, decode_responses=True)


def _cache_key(user_id: str, language: str) -> str:
    """Return the Redis key for one user's language-specific feed."""
    return f"personal_feed:{user_id}:{language}"
