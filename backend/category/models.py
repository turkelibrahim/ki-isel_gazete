"""Typed models for SmartNewspaper category classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


SUPPORTED_CATEGORIES: List[str] = [
    "Gündem",
    "Siyaset",
    "Ekonomi",
    "Teknoloji",
    "Spor",
    "Sağlık",
    "Bilim",
    "Dünya",
    "Yaşam",
    "Kültür/Sanat",
    "Eğlence",
    "Diğer",
]

RELIABLE_CONFIDENCE_THRESHOLD = 0.85
MIN_CLASSIFIABLE_TEXT_LENGTH = 24


@dataclass(frozen=True)
class NewsArticle:
    """Minimal article shape consumed by the category classifier."""

    id: str = ""
    title: str = ""
    summary: str = ""
    content: str = ""
    full_text: str = ""
    description: str = ""
    source_name: str = ""
    source_url: str = ""
    language: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "NewsArticle":
        """Build a normalized article input from common RSS/API field names."""

        return cls(
            id=str(payload.get("id") or payload.get("article_id") or payload.get("articleId") or ""),
            title=str(payload.get("title") or payload.get("displayTitle") or payload.get("originalTitle") or ""),
            summary=str(payload.get("summary") or payload.get("description") or payload.get("displaySummary") or ""),
            content=str(payload.get("content") or payload.get("fullText") or payload.get("body") or ""),
            full_text=str(payload.get("full_text") or payload.get("fullText") or payload.get("originalContent") or ""),
            description=str(payload.get("description") or ""),
            source_name=str(payload.get("source_name") or payload.get("sourceName") or payload.get("source") or ""),
            source_url=str(payload.get("source_url") or payload.get("sourceUrl") or payload.get("url") or ""),
            language=str(payload.get("detected_lang") or payload.get("originalLanguage") or payload.get("language") or ""),
            metadata=dict(payload),
        )

    def joined_text(self) -> str:
        """Return the text used for category inference."""

        return "\n".join(
            part
            for part in [self.title, self.summary, self.description, self.content, self.full_text, self.source_name, self.source_url]
            if part
        )


@dataclass(frozen=True)
class CategoryPrediction:
    """Classifier output attached to every feed article."""

    category: str
    category_confidence: float
    category_source: str
    is_category_reliable: bool
    detected_lang: str
    scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the prediction for API payloads."""

        return {
            "category": self.category,
            "category_confidence": round(float(self.category_confidence), 4),
            "category_source": self.category_source,
            "is_category_reliable": bool(self.is_category_reliable),
            "detected_lang": self.detected_lang,
            "category_scores": {key: round(float(value), 4) for key, value in self.scores.items()},
        }
