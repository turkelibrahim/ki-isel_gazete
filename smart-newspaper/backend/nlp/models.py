"""Data models for SmartNewspaper multilingual NLP processing."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class RawArticle:
    """Raw article received from RSS/API before NLP processing."""
    id: str
    title: str
    content: str
    summary: str | None = None
    source_name: str = ""
    source_url: str = ""
    source_logo: str | None = None
    category: str | None = None
    country: str | None = None
    city: str | None = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    published_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe dict."""
        data = asdict(self)
        data["fetched_at"] = self.fetched_at.isoformat()
        data["published_at"] = self.published_at.isoformat() if self.published_at else None
        return data


@dataclass
class DetectionResult:
    """Language detection result with confidence and fallback metadata."""
    detected_lang: str
    confidence: float
    is_reliable: bool
    fallback_used: bool
    candidates: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TranslationResult:
    """Prepared TR/EN fields and translation status."""
    original_lang: str
    title_original: str
    content_original: str
    title_tr: str | None
    content_tr: str | None
    title_en: str | None
    content_en: str | None
    translation_status: str
    provider: str | None
    error_message: str | None


@dataclass
class ProcessedArticle:
    """Article after language detection, preprocessing, dedupe and formatting."""
    raw: RawArticle
    detection: DetectionResult
    translation: TranslationResult | None
    pipeline_name: str
    tokens: list[str]
    lemmas: list[str]
    entities: list[dict[str, Any]]
    keywords: list[str]
    cleaned_text: str
    normalized_title: str
    dedupe_key: str
    cluster_id: str | None
    processing_status: str
    error_message: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe dict."""
        data = asdict(self)
        data["raw"] = self.raw.to_dict()
        return data
