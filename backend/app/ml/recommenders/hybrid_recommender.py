"""Hybrid recommender that combines content-based and collaborative signals."""

from __future__ import annotations

ALPHA = 0.60
BETA = 0.40


class HybridRecommender:
    """Merge CB and CF recommendation scores with a 60/40 weighting."""

    def combine(
        self,
        cb_scores: list[dict[str, float | int]],
        cf_scores: list[dict[str, float | int]],
        limit: int = 30,
    ) -> list[dict[str, float | int]]:
        """Return ranked hybrid recommendations.

        ``final_score = 0.60 * normalized_cb + 0.40 * normalized_cf``.
        """
        normalized_cb = self._normalize(cb_scores)
        normalized_cf = self._normalize(cf_scores)
        article_ids = set(normalized_cb) | set(normalized_cf)
        results: list[dict[str, float | int]] = []
        for article_id in article_ids:
            cb_score = normalized_cb.get(article_id, 0.0)
            cf_score = normalized_cf.get(article_id, 0.0)
            final_score = ALPHA * cb_score + BETA * cf_score
            if final_score <= 0:
                continue
            results.append(
                {
                    "article_id": int(article_id),
                    "score": float(final_score),
                    "cb_score": float(cb_score),
                    "cf_score": float(cf_score),
                    "algorithm": "hybrid_cb60_cf40",
                }
            )
        results.sort(key=lambda row: float(row["score"]), reverse=True)
        return results[:limit]

    def _normalize(self, rows: list[dict[str, float | int]]) -> dict[int, float]:
        """Normalize recommendation scores by dividing by the maximum score."""
        if not rows:
            return {}
        max_score = max(float(row.get("score") or 0.0) for row in rows)
        if max_score <= 0:
            return {}
        return {int(row["article_id"]): float(row.get("score") or 0.0) / max_score for row in rows}
