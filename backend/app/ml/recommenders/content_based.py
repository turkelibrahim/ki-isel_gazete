"""Content-based news recommendation using TF-IDF article profiles."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

TFIDF_CONFIG: dict[str, object] = {
    "max_features": 30000,
    "ngram_range": (1, 2),
    "sublinear_tf": True,
    "min_df": 2,
    "strip_accents": "unicode",
}


@dataclass(frozen=True)
class ContentRecommendation:
    """One content-based article recommendation."""

    article_id: int
    score: float


class ContentBasedRecommender:
    """Build user profiles from read article TF-IDF vectors and recommend similar articles.

    The configured TF-IDF parameters follow the module specification.  Very
    small corpora may not satisfy ``min_df=2``; in that case the index rebuilds
    with ``min_df=1`` so development and cold-start datasets do not crash.
    """

    def __init__(self) -> None:
        """Create an empty article index."""
        self.vectorizer: TfidfVectorizer = TfidfVectorizer(**TFIDF_CONFIG)
        self.article_ids: list[int] = []
        self._id_to_index: dict[int, int] = {}
        self.article_matrix = None
        self.fitted: bool = False

    def index_articles(self, articles: Iterable[Mapping[str, object]]) -> int:
        """Index duplicate-free article texts and return the number indexed."""
        rows = [row for row in articles if int(row.get("id", 0) or 0) > 0]
        self.article_ids = [int(row["id"]) for row in rows]
        self._id_to_index = {article_id: idx for idx, article_id in enumerate(self.article_ids)}
        texts = [str(row.get("text") or "").strip() for row in rows]

        if not rows or not any(texts):
            self.article_matrix = None
            self.fitted = False
            return 0

        try:
            self.vectorizer = TfidfVectorizer(**TFIDF_CONFIG)
            self.article_matrix = self.vectorizer.fit_transform(texts)
        except ValueError:
            logger.warning("Content TF-IDF corpus too small for min_df=2; retrying with min_df=1")
            fallback_config = dict(TFIDF_CONFIG)
            fallback_config["min_df"] = 1
            self.vectorizer = TfidfVectorizer(**fallback_config)
            self.article_matrix = self.vectorizer.fit_transform(texts)

        self.fitted = True
        return len(self.article_ids)

    def build_profile(self, read_article_ids: Sequence[int]):
        """Return the mean TF-IDF vector of articles read by the user.

        ``None`` is returned when no read article exists in the current index.
        """
        if not self.fitted or self.article_matrix is None:
            return None
        indices = [self._id_to_index[int(article_id)] for article_id in read_article_ids if int(article_id) in self._id_to_index]
        if not indices:
            return None
        return np.asarray(self.article_matrix[indices].mean(axis=0))

    def recommend(
        self,
        profile,
        exclude_ids: set[int] | None = None,
        limit: int = 100,
    ) -> list[dict[str, float | int]]:
        """Rank indexed articles by cosine similarity to a user profile."""
        if profile is None or not self.fitted or self.article_matrix is None:
            return []
        exclude = exclude_ids or set()
        scores = np.asarray(cosine_similarity(profile, self.article_matrix)).ravel()
        ranked: list[dict[str, float | int]] = []
        for idx in np.argsort(scores)[::-1]:
            article_id = self.article_ids[int(idx)]
            if article_id in exclude:
                continue
            score = float(scores[int(idx)])
            if score <= 0:
                continue
            ranked.append({"article_id": article_id, "score": score})
            if len(ranked) >= limit:
                break
        return ranked
