"""Headline prioritization with temporal decay, relevance, popularity, and trust."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

logger = logging.getLogger(__name__)

RECENCY_LAMBDA = 0.05
RELEVANCE_WEIGHT = 0.40
RECENCY_WEIGHT = 0.30
POPULARITY_WEIGHT = 0.20
TRUST_WEIGHT = 0.10


class PrioritizationService:
    """Rank articles for newspaper headline placement.

    The service is intentionally runtime-only.  If an Article model later gains a
    ``priority_score`` column the caller may persist the score, but this service
    does not require a schema migration and never touches ``database.py``.
    """

    def rank(self, articles: Iterable[Any], user_profile: Any | None = None) -> list[dict[str, Any]]:
        """Return articles sorted by final headline priority score.

        Args:
            articles: ORM rows or dictionaries.  Each item may include
                ``published_at``, ``view_count``, ``source_trust_score`` or
                ``trust_score`` and optional relevance hints.
            user_profile: Optional relevance provider.  Supported forms are:
                - ``None``: fallback relevance of ``0.5``.
                - ``dict[int, float]``: article id to relevance score.
                - callable(article) -> float.

        Returns:
            A list of dictionaries containing article fields plus ``priority``
            score components and top-level ``priority_score``.
        """
        rows = [self._to_dict(article) for article in articles]
        if not rows:
            return []

        popularity_values = [self._popularity(row.get("view_count")) for row in rows]
        max_popularity = max(popularity_values) if popularity_values else 0.0

        ranked: list[dict[str, Any]] = []
        for row, popularity in zip(rows, popularity_values, strict=False):
            try:
                relevance = self._relevance(row, user_profile)
                recency = self._recency(row.get("published_at"))
                pop_norm = (popularity / max_popularity) if max_popularity > 0 else 0.0
                trust = self._trust(row)
                final_score = self._clamp01(
                    RELEVANCE_WEIGHT * relevance
                    + RECENCY_WEIGHT * recency
                    + POPULARITY_WEIGHT * pop_norm
                    + TRUST_WEIGHT * trust
                )
                enriched = dict(row)
                enriched["priority_score"] = final_score
                enriched["priority"] = {
                    "relevance": relevance,
                    "recency": recency,
                    "popularity": pop_norm,
                    "trust": trust,
                    "final_score": final_score,
                    "weights": {
                        "relevance": RELEVANCE_WEIGHT,
                        "recency": RECENCY_WEIGHT,
                        "popularity": POPULARITY_WEIGHT,
                        "trust": TRUST_WEIGHT,
                    },
                }
                ranked.append(enriched)
            except Exception:
                logger.exception("Could not prioritize article id=%r", row.get("id") or row.get("article_id"))
                fallback = dict(row)
                fallback["priority_score"] = 0.0
                fallback["priority"] = {
                    "relevance": 0.5,
                    "recency": 0.5,
                    "popularity": 0.0,
                    "trust": 0.5,
                    "final_score": 0.0,
                    "error": "priority_calculation_failed",
                }
                ranked.append(fallback)

        ranked.sort(key=lambda item: float(item.get("priority_score") or 0.0), reverse=True)
        return ranked

    def score_article(self, article: Any, *, max_popularity: float = 0.0, user_profile: Any | None = None) -> dict[str, Any]:
        """Score one article and return the enriched dictionary.

        ``max_popularity`` should be the maximum ``log10(1 + view_count)`` in the
        current candidate list.  When absent or zero, the popularity component is
        safely set to 0.
        """
        row = self._to_dict(article)
        popularity = self._popularity(row.get("view_count"))
        pop_norm = (popularity / max_popularity) if max_popularity > 0 else 0.0
        relevance = self._relevance(row, user_profile)
        recency = self._recency(row.get("published_at"))
        trust = self._trust(row)
        final_score = self._clamp01(
            RELEVANCE_WEIGHT * relevance
            + RECENCY_WEIGHT * recency
            + POPULARITY_WEIGHT * pop_norm
            + TRUST_WEIGHT * trust
        )
        row["priority_score"] = final_score
        row["priority"] = {
            "relevance": relevance,
            "recency": recency,
            "popularity": pop_norm,
            "trust": trust,
            "final_score": final_score,
            "weights": {
                "relevance": RELEVANCE_WEIGHT,
                "recency": RECENCY_WEIGHT,
                "popularity": POPULARITY_WEIGHT,
                "trust": TRUST_WEIGHT,
            },
        }
        return row

    def _recency(self, published_at: Any) -> float:
        """Compute temporal decay ``exp(-0.05 * hours_old)`` with 0.5 fallback."""
        dt = self._parse_datetime(published_at)
        if dt is None:
            return 0.5
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours_old = max((now - dt.astimezone(timezone.utc)).total_seconds() / 3600.0, 0.0)
        return self._clamp01(math.exp(-RECENCY_LAMBDA * hours_old))

    def _popularity(self, view_count: Any) -> float:
        """Return log-scaled popularity ``log10(1 + view_count)``."""
        try:
            views = max(float(view_count or 0), 0.0)
        except (TypeError, ValueError):
            views = 0.0
        return math.log10(1.0 + views)

    def _relevance(self, row: Mapping[str, Any], user_profile: Any | None) -> float:
        """Resolve article relevance or fallback to 0.5 for cold start."""
        article_id = self._safe_int(row.get("article_id") or row.get("id"))
        if callable(user_profile):
            try:
                return self._clamp01(float(user_profile(row)))
            except Exception:
                logger.warning("Callable user profile failed for article_id=%r", article_id, exc_info=True)
                return 0.5
        if isinstance(user_profile, Mapping) and article_id is not None:
            value = user_profile.get(article_id, user_profile.get(str(article_id)))
            if value is not None:
                try:
                    return self._clamp01(float(value))
                except (TypeError, ValueError):
                    return 0.5
        for key in ("relevance", "relevance_score", "score", "final_score"):
            value = row.get(key)
            if value is not None:
                try:
                    return self._clamp01(float(value))
                except (TypeError, ValueError):
                    continue
        return 0.5

    def _trust(self, row: Mapping[str, Any]) -> float:
        """Return source trust score with 0.5 fallback."""
        for key in ("source_trust_score", "trust_score", "source_trust", "trust"):
            value = row.get(key)
            if value is not None:
                try:
                    return self._clamp01(float(value))
                except (TypeError, ValueError):
                    continue
        return 0.5

    def _to_dict(self, article: Any) -> dict[str, Any]:
        """Serialize ORM-like objects or mappings into a plain article dictionary."""
        if isinstance(article, Mapping):
            row = dict(article)
        else:
            published_at = getattr(article, "published_at", None)
            created_at = getattr(article, "created_at", None)
            row = {
                "id": getattr(article, "id", None),
                "article_id": getattr(article, "id", None),
                "title": getattr(article, "title", None),
                "summary": getattr(article, "summary", None),
                "content": getattr(article, "content", None),
                "url": getattr(article, "url", None),
                "language": getattr(article, "language", None),
                "source_id": getattr(article, "source_id", None),
                "view_count": getattr(article, "view_count", 0),
                "is_duplicate": getattr(article, "is_duplicate", False),
                "published_at": published_at.isoformat() if isinstance(published_at, datetime) else published_at,
                "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
            }
        row.setdefault("article_id", row.get("id"))
        row.setdefault("view_count", 0)
        row.setdefault("source_trust_score", row.get("trust_score", 0.5))
        return row

    def _parse_datetime(self, value: Any) -> datetime | None:
        """Parse datetime-like values without raising."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            text = str(value)
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            return datetime.fromisoformat(text)
        except Exception:
            return None

    def _safe_int(self, value: Any) -> int | None:
        """Convert a value to int or return None."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _clamp01(self, value: float) -> float:
        """Clamp numeric values to the inclusive 0-1 range."""
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return max(0.0, min(1.0, float(value)))
