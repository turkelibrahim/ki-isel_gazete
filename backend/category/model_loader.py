"""Model loading and lightweight ML fallback for category classification.

The fallback intentionally has no mandatory external dependency so the feed never
crashes when scikit-learn, fastText or a future BERT model is unavailable. A real
model can be plugged in by implementing the same ``predict`` contract.
"""

from __future__ import annotations

import math
import os
from collections import Counter
from typing import Dict, Iterable, List, Mapping, Protocol, Tuple

from .category_rules import CATEGORY_KEYWORDS
from .text_cleaner import tokenize


class CategoryModel(Protocol):
    """Protocol for future fastText/scikit-learn/BERT category models."""

    def predict(self, text: str) -> Tuple[str, float, Dict[str, float]]:
        """Return ``category, confidence, scores`` for the given text."""


class KeywordCentroidModel:
    """TF-IDF-like centroid classifier trained from the category keyword config."""

    def __init__(self, category_keywords: Mapping[str, Mapping[str, float]]):
        self._profiles: Dict[str, Counter[str]] = {}
        self._idf: Dict[str, float] = {}
        self._build_profiles(category_keywords)

    def _build_profiles(self, category_keywords: Mapping[str, Mapping[str, float]]) -> None:
        documents: Dict[str, List[str]] = {}
        for category, keywords in category_keywords.items():
            if category == "Diğer":
                continue
            expanded: List[str] = []
            for keyword, weight in keywords.items():
                repeat = max(1, min(5, int(round(float(weight) * 2))))
                expanded.extend(tokenize(keyword, remove_stopwords=False) * repeat)
            documents[category] = expanded

        doc_count = max(1, len(documents))
        df = Counter(token for tokens in documents.values() for token in set(tokens))
        self._idf = {token: math.log((doc_count + 1) / (count + 1)) + 1 for token, count in df.items()}
        for category, tokens in documents.items():
            self._profiles[category] = self._tfidf(tokens)

    def _tfidf(self, tokens: Iterable[str]) -> Counter[str]:
        counts = Counter(tokens)
        vector: Counter[str] = Counter()
        for token, count in counts.items():
            vector[token] = (1.0 + math.log(count)) * self._idf.get(token, 1.0)
        return vector

    @staticmethod
    def _cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float:
        if not left or not right:
            return 0.0
        shared = set(left).intersection(right)
        dot = sum(left[token] * right[token] for token in shared)
        left_norm = math.sqrt(sum(value * value for value in left.values())) or 1.0
        right_norm = math.sqrt(sum(value * value for value in right.values())) or 1.0
        return dot / (left_norm * right_norm)

    def predict(self, text: str) -> Tuple[str, float, Dict[str, float]]:
        """Predict a category using centroid cosine similarity."""

        article_vector = self._tfidf(tokenize(text))
        scores = {category: self._cosine(article_vector, profile) for category, profile in self._profiles.items()}
        if not scores:
            return "Diğer", 0.0, {}
        best_category, best_score = max(scores.items(), key=lambda item: item[1])
        ordered = sorted(scores.values(), reverse=True)
        second = ordered[1] if len(ordered) > 1 else 0.0
        confidence = max(0.0, min(0.91, 0.35 + best_score * 0.65 + max(0.0, best_score - second) * 0.30))
        if best_score <= 0.025:
            return "Diğer", 0.0, scores
        return best_category, confidence, scores


_MODEL_CACHE: CategoryModel | None = None


def load_category_model() -> CategoryModel:
    """Load the configured category model with a safe local fallback."""

    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    # Hook for future production model files. The current implementation remains
    # deterministic and dependency-free so tests and local startup are reliable.
    _ = os.getenv("CATEGORY_MODEL_PATH", "")
    _MODEL_CACHE = KeywordCentroidModel(CATEGORY_KEYWORDS)
    return _MODEL_CACHE
