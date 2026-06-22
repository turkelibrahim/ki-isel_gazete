"""Analytics hybrid recommender combining CB, IBCF, SVD and trending scores."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

from app.ml.recommender.ibcf_recommender import IBCFRecommender
from app.ml.recommender.svd_recommender import SVDRecommender

logger = logging.getLogger(__name__)

CB_WEIGHT = 0.30
IBCF_WEIGHT = 0.35
SVD_WEIGHT = 0.25
TREND_WEIGHT = 0.10


class AnalyticsHybridRecommender:
    """Combine recommendation sources with Prompt 32 weights.

    Final score:
    ``0.30 * CB + 0.35 * IBCF + 0.25 * SVD + 0.10 * Trending``.
    Missing scores are treated as 0.0 and every component is normalized to
    0-1 before weighting.
    """

    def __init__(
        self,
        ibcf_model_path: str | Path | None = None,
        svd_model_path: str | Path | None = None,
    ) -> None:
        """Initialize with optional persisted IBCF/SVD model paths."""
        self.ibcf_model_path = Path(ibcf_model_path) if ibcf_model_path else None
        self.svd_model_path = Path(svd_model_path) if svd_model_path else None
        self._ibcf: IBCFRecommender | None = None
        self._svd: SVDRecommender | None = None

    def recommend(
        self,
        user_id: str | int,
        candidate_article_ids: Iterable[int],
        content_based_scores: dict[int, float] | None = None,
        trending_scores: dict[int, float] | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Return hybrid recommendations for candidate articles."""
        candidates = {int(article_id) for article_id in candidate_article_ids}
        if not candidates:
            return []

        cb_norm = self._normalize_scores(content_based_scores or {})
        trend_norm = self._normalize_scores(trending_scores or {})
        ibcf_norm = self._normalize_scores(self.ibcf.predict_for_user(user_id, candidates))
        svd_norm = self._normalize_scores(self.svd.predict_for_user(user_id, candidates))

        rows: list[dict[str, Any]] = []
        for article_id in candidates:
            cb_score = float(cb_norm.get(article_id, 0.0))
            ibcf_score = float(ibcf_norm.get(article_id, 0.0))
            svd_score = float(svd_norm.get(article_id, 0.0))
            trending_score = float(trend_norm.get(article_id, 0.0))
            final_score = (
                CB_WEIGHT * cb_score
                + IBCF_WEIGHT * ibcf_score
                + SVD_WEIGHT * svd_score
                + TREND_WEIGHT * trending_score
            )
            if final_score <= 0:
                continue
            rows.append(
                {
                    "article_id": int(article_id),
                    "score": float(final_score),
                    "content_based_score": cb_score,
                    "ibcf_score": ibcf_score,
                    "svd_score": svd_score,
                    "trending_score": trending_score,
                    "algorithm": "analytics_hybrid_cb30_ibcf35_svd25_trending10",
                }
            )
        rows.sort(key=lambda row: float(row["score"]), reverse=True)
        return rows[:limit]

    @property
    def ibcf(self) -> IBCFRecommender:
        """Lazy-load the IBCF model."""
        if self._ibcf is None:
            self._ibcf = IBCFRecommender.load(self.ibcf_model_path) if self.ibcf_model_path else IBCFRecommender()
        return self._ibcf

    @property
    def svd(self) -> SVDRecommender:
        """Lazy-load the SVD model."""
        if self._svd is None:
            self._svd = SVDRecommender.load(self.svd_model_path) if self.svd_model_path else SVDRecommender()
        return self._svd

    def has_models(self) -> bool:
        """Return whether at least one trained collaborative model is available."""
        return bool(self.ibcf.is_trained or self.svd.is_trained)

    def _normalize_scores(self, scores: dict[int, float]) -> dict[int, float]:
        """Normalize arbitrary positive scores into 0-1 range."""
        cleaned: dict[int, float] = {}
        for key, value in scores.items():
            try:
                article_id = int(key)
                score = max(float(value), 0.0)
            except (TypeError, ValueError):
                continue
            cleaned[article_id] = score
        max_score = max(cleaned.values(), default=0.0)
        if max_score <= 0:
            return {article_id: 0.0 for article_id in cleaned}
        return {article_id: score / max_score for article_id, score in cleaned.items()}
