"""Keyword-score based event categorization.

This module classifies detected event candidates into stable event categories
using deterministic keyword scoring.  It intentionally avoids model loading so
it can run cheaply inside EventDetector and EventService flows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "EXAM": ["sınav", "vize", "final", "quiz", "test", "değerlendirme"],
    "DEADLINE": ["son başvuru", "deadline", "son tarih", "teslim", "başvuru bitiş"],
    "ACADEMIC": ["seminer", "konferans", "webinar", "eğitim", "atölye", "panel"],
    "MEETING": ["toplantı", "görüşme", "kurul", "oturum", "randevu"],
    "SOCIAL": ["konser", "festival", "tören", "gezi", "sosyal", "etkinlik"],
    "OTHER": [],
}

CATEGORY_PRIORITY: tuple[str, ...] = (
    "EXAM",
    "DEADLINE",
    "ACADEMIC",
    "MEETING",
    "SOCIAL",
    "OTHER",
)


@dataclass(frozen=True)
class EventCategoryResult:
    """Typed representation of an event category classification result."""

    category: str
    score: int
    matched_keywords: list[str]
    all_scores: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        """Return the result as a JSON-serializable dictionary."""
        return {
            "category": self.category,
            "score": self.score,
            "matched_keywords": self.matched_keywords,
            "all_scores": self.all_scores,
        }


class EventCategoryClassifier:
    """Classify event text with deterministic keyword scoring.

    Ties are resolved with the fixed priority order requested by the project:
    EXAM > DEADLINE > ACADEMIC > MEETING > SOCIAL > OTHER.
    """

    categories: dict[str, list[str]] = CATEGORY_KEYWORDS
    priority: tuple[str, ...] = CATEGORY_PRIORITY

    def score_categories(self, text: str) -> dict[str, int]:
        """Score every category by counting matched keywords in lowercase text.

        Args:
            text: Event sentence or description.

        Returns:
            Mapping of category name to integer keyword score. ``OTHER`` is
            included with score 0 and is used only as a fallback.
        """
        normalized = (text or "").lower()
        scores: dict[str, int] = {}
        for category in self.priority:
            keywords = self.categories.get(category, [])
            scores[category] = sum(1 for keyword in keywords if keyword in normalized)
        return scores

    def _matched_keywords(self, text: str, category: str) -> list[str]:
        """Return matched keywords for the selected category."""
        normalized = (text or "").lower()
        return [keyword for keyword in self.categories.get(category, []) if keyword in normalized]

    def classify(self, text: str) -> dict[str, object]:
        """Classify event text and return category, score, matches and scores.

        If no keyword is matched in any non-OTHER category, the result is
        ``OTHER`` with score 0.
        """
        try:
            scores = self.score_categories(text)
            max_score = max(scores.values()) if scores else 0
            if max_score <= 0:
                selected = "OTHER"
            else:
                selected = next(
                    category
                    for category in self.priority
                    if scores.get(category, 0) == max_score
                )

            result = EventCategoryResult(
                category=selected,
                score=scores.get(selected, 0),
                matched_keywords=self._matched_keywords(text, selected),
                all_scores=scores,
            )
            return result.to_dict()
        except Exception:
            logger.exception("Event category classification failed for text: %s", text)
            scores = {category: 0 for category in self.priority}
            return {
                "category": "OTHER",
                "score": 0,
                "matched_keywords": [],
                "all_scores": scores,
            }
