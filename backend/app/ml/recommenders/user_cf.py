"""User-based collaborative filtering for implicit news events."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Mapping, Sequence

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

EVENT_WEIGHTS: dict[str, float] = {
    "SHARED": 2.0,
    "BOOKMARKED": 1.5,
    "READ": 1.0,
    "VIEWED": 0.3,
    "SKIPPED": 0.0,
    "UNBOOKMARKED": 0.0,
}
K_NEIGHBORS = 20


class UserCollaborativeFilter:
    """Recommend articles from behavior of users similar to the target user."""

    def event_rating(self, event: Mapping[str, object]) -> float:
        """Convert one implicit event into a Module 7 weighted rating."""
        event_type = str(event.get("event_type") or "VIEWED").upper()
        duration_seconds = event.get("duration_seconds")
        scroll_percent = event.get("scroll_percent")

        try:
            duration = float(duration_seconds) if duration_seconds is not None else None
        except (TypeError, ValueError):
            duration = None
        try:
            scroll = float(scroll_percent) if scroll_percent is not None else None
        except (TypeError, ValueError):
            scroll = None

        if event_type in {"VIEWED", "READ"}:
            if duration is not None and scroll is not None and duration < 5 and scroll < 10:
                event_type = "SKIPPED"
            elif duration is not None and duration >= 30 and event_type == "VIEWED":
                event_type = "READ"

        weight = EVENT_WEIGHTS.get(event_type, 0.0)
        if weight <= 0:
            return 0.0

        if scroll is not None:
            scroll_factor = min(max(scroll, 0.0) / 100.0, 1.0)
        elif event_type == "VIEWED":
            scroll_factor = 0.1
        elif event_type == "READ":
            scroll_factor = 0.8
        elif event_type in {"BOOKMARKED", "SHARED"}:
            scroll_factor = 1.0
        else:
            scroll_factor = 0.0

        return float(weight * scroll_factor)

    def recommend(
        self,
        user_id: str,
        events: Sequence[Mapping[str, object]],
        candidate_article_ids: set[int] | None = None,
        exclude_ids: set[int] | None = None,
        limit: int = 100,
    ) -> list[dict[str, float | int]]:
        """Return collaborative recommendations for ``user_id``.

        The implementation follows user-based CF with cosine similarity and the
        prediction formula ``mean(u) + weighted neighbor deviations``.
        """
        exclude = exclude_ids or set()
        candidate_filter = candidate_article_ids or set()
        ratings = self._aggregate_ratings(events)
        if user_id not in ratings or len(ratings) < 2:
            return []

        users = sorted(ratings)
        articles = sorted({article_id for user_ratings in ratings.values() for article_id in user_ratings})
        user_idx = {uid: idx for idx, uid in enumerate(users)}
        article_idx = {article_id: idx for idx, article_id in enumerate(articles)}
        matrix = np.zeros((len(users), len(articles)), dtype=float)

        for uid, user_ratings in ratings.items():
            for article_id, value in user_ratings.items():
                matrix[user_idx[uid], article_idx[article_id]] = value

        target_index = user_idx[user_id]
        similarities = cosine_similarity(matrix[target_index : target_index + 1], matrix).ravel()
        neighbors = [
            (idx, float(score))
            for idx, score in sorted(enumerate(similarities), key=lambda item: item[1], reverse=True)
            if idx != target_index and score > 0
        ][:K_NEIGHBORS]
        if not neighbors:
            return []

        means = self._nonzero_means(matrix)
        target_mean = float(means[target_index])
        predictions: list[dict[str, float | int]] = []

        for article_id in articles:
            if article_id in exclude:
                continue
            if candidate_filter and article_id not in candidate_filter:
                continue
            col = article_idx[article_id]
            if matrix[target_index, col] > 0:
                continue

            numerator = 0.0
            denominator = 0.0
            for neighbor_index, similarity in neighbors:
                neighbor_rating = matrix[neighbor_index, col]
                if neighbor_rating <= 0:
                    continue
                numerator += similarity * (neighbor_rating - means[neighbor_index])
                denominator += abs(similarity)
            if denominator <= 0:
                continue
            score = target_mean + numerator / denominator
            if score > 0:
                predictions.append({"article_id": int(article_id), "score": float(score)})

        predictions.sort(key=lambda row: float(row["score"]), reverse=True)
        return predictions[:limit]

    def _aggregate_ratings(self, events: Sequence[Mapping[str, object]]) -> dict[str, dict[int, float]]:
        """Aggregate multiple events per user/article using MAX signal logic."""
        ratings: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
        for event in events:
            try:
                uid = str(event.get("user_id") or "").strip()
                article_id = int(event.get("article_id") or 0)
            except (TypeError, ValueError):
                continue
            if not uid or article_id <= 0:
                continue
            rating = self.event_rating(event)
            if rating <= 0:
                continue
            ratings[uid][article_id] = max(float(ratings[uid].get(article_id, 0.0)), float(rating))
        return {uid: dict(user_ratings) for uid, user_ratings in ratings.items()}

    def _nonzero_means(self, matrix: np.ndarray) -> np.ndarray:
        """Return per-user mean over non-zero ratings."""
        means = np.zeros(matrix.shape[0], dtype=float)
        for idx, row in enumerate(matrix):
            nonzero = row[row > 0]
            means[idx] = float(nonzero.mean()) if nonzero.size else 0.0
        return means
