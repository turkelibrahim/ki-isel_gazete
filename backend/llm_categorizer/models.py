"""Data models for SmartNewspaper LLM categorization fallback."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_CATEGORIES: dict[int, str] = {
    0: "Teknoloji",
    1: "Siyaset",
    2: "Spor",
    3: "Ekonomi",
    4: "Eğlence",
    5: "Sağlık",
    6: "Bilim",
    7: "Dünya",
    8: "Yaşam",
}
ALLOWED_CATEGORY_NAMES: tuple[str, ...] = tuple(ALLOWED_CATEGORIES.values())
MAX_RETRIES = 2


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class LLMCategorizationRequest:
    """Input payload sent to the LLM categorization fallback."""

    article_id: str
    cluster_id: str | None
    title: str
    content: str
    summary: str | None
    language: str
    source_name: str | None
    source_url: str | None
    trigger_reason: str
    ml_prediction: dict[str, Any]
    multilabel_prediction: dict[str, Any] | None
    category_prediction: dict[str, Any] | None
    requested_at: datetime = field(default_factory=utc_now)

    @classmethod
    def from_article(
        cls,
        article: dict[str, Any],
        trigger_reason: str,
        ml_prediction: dict[str, Any] | None = None,
    ) -> "LLMCategorizationRequest":
        """Build a request from a SmartNewspaper article dictionary."""
        article_id = str(article.get("id") or article.get("article_id") or article.get("url") or "unknown")
        category_prediction = {
            "category": article.get("category"),
            "category_confidence": article.get("category_confidence", article.get("categoryConfidence")),
            "category_source": article.get("category_source", article.get("categorySource")),
        }
        multilabel_prediction = {
            "labels": article.get("labels", []),
            "label_scores": article.get("label_scores", article.get("labelScores", {})),
            "no_label_detected": article.get("no_label_detected", article.get("noLabelDetected")),
        }
        return cls(
            article_id=article_id,
            cluster_id=article.get("cluster_id") or article.get("clusterId"),
            title=str(article.get("title") or article.get("displayTitle") or ""),
            content=str(article.get("content") or article.get("fullText") or article.get("description") or ""),
            summary=article.get("summary") or article.get("displaySummary"),
            language=str(article.get("detected_lang") or article.get("detectedLang") or article.get("language") or "unknown"),
            source_name=article.get("source_name") or article.get("sourceName") or article.get("source"),
            source_url=article.get("source_url") or article.get("sourceUrl") or article.get("url"),
            trigger_reason=trigger_reason,
            ml_prediction=ml_prediction or {"category": article.get("category"), "labels": article.get("labels", [])},
            multilabel_prediction=multilabel_prediction,
            category_prediction=category_prediction,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the request to a JSON-serializable dictionary."""
        data = asdict(self)
        data["requested_at"] = self.requested_at.isoformat()
        return data


@dataclass(slots=True)
class LLMCategorizationResponse:
    """Validated result returned by the categorization fallback."""

    article_id: str
    cluster_id: str | None
    predicted_labels: list[str]
    label_confidences: dict[str, float]
    reasoning: str
    provider: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    is_reliable: bool
    no_label_detected: bool
    retry_count: int
    response_time_ms: float
    raw_response: str
    created_at: datetime = field(default_factory=utc_now)
    used: bool = True
    trigger_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the response to a JSON-serializable dictionary."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass(slots=True)
class LLMUsageStats:
    """Daily provider usage and cost counters."""

    date: datetime
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_response_time_ms: float = 0.0
    claude_requests: int = 0
    gpt4_requests: int = 0
    fallback_requests: int = 0
    invalid_category_rejections: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert usage stats to a JSON-serializable dictionary."""
        data = asdict(self)
        data["date"] = self.date.date().isoformat()
        data["total_cost_usd"] = round(self.total_cost_usd, 6)
        data["avg_response_time_ms"] = round(self.avg_response_time_ms, 3)
        return data


class LLMOutputSchema(BaseModel):
    """Strict schema for model output; rejects unsupported categories."""

    model_config = ConfigDict(extra="forbid")

    categories: list[str] = Field(default_factory=list)
    confidences: dict[str, float] = Field(default_factory=dict)
    reasoning: str = ""

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, value: list[str]) -> list[str]:
        allowed = set(ALLOWED_CATEGORY_NAMES)
        invalid = [item for item in value if item not in allowed]
        if invalid:
            raise ValueError(f"İzinsiz kategori: {invalid}")
        return list(dict.fromkeys(value))

    @field_validator("confidences")
    @classmethod
    def validate_confidences(cls, value: dict[str, float]) -> dict[str, float]:
        allowed = set(ALLOWED_CATEGORY_NAMES)
        normalized: dict[str, float] = {}
        for key, score in value.items():
            if key not in allowed:
                raise ValueError(f"İzinsiz kategori güven skoru anahtarı: {key}")
            numeric = float(score)
            if not 0.0 <= numeric <= 1.0:
                raise ValueError(f"Güven skoru 0.0-1.0 arasında olmalı: {key}")
            normalized[key] = numeric
        return normalized

    @field_validator("reasoning")
    @classmethod
    def trim_reasoning(cls, value: str) -> str:
        """Keep reasoning short enough for cards/admin UI."""
        words = str(value or "").split()
        return " ".join(words[:100])


@dataclass(slots=True)
class ProviderResult:
    """Raw provider response with token and latency metadata."""

    raw_response: str
    prompt_tokens: int
    completion_tokens: int
    response_time_ms: float
    provider: str
    model_name: str
