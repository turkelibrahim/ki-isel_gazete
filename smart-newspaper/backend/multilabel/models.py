"""Typed models and configuration for multi-label news classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

ALLOWED_LABELS: tuple[str, ...] = (
    "Teknoloji",
    "Siyaset",
    "Spor",
    "Ekonomi",
    "Eğlence",
    "Sağlık",
    "Bilim",
    "Dünya",
    "Yaşam",
)

DEFAULT_LABEL_THRESHOLD = 0.56
DEFAULT_RELIABLE_THRESHOLD = 0.85
MIN_CLASSIFIABLE_TEXT_LENGTH = 24


@dataclass(frozen=True)
class MultiLabelConfig:
    """Runtime configuration for independent sigmoid-style label scoring."""

    allowed_labels: tuple[str, ...] = ALLOWED_LABELS
    default_threshold: float = DEFAULT_LABEL_THRESHOLD
    reliable_threshold: float = DEFAULT_RELIABLE_THRESHOLD
    min_text_length: int = MIN_CLASSIFIABLE_TEXT_LENGTH
    per_label_thresholds: dict[str, float] = field(default_factory=dict)

    def threshold_for(self, label: str) -> float:
        """Return the configured decision threshold for a label."""

        if label not in self.allowed_labels:
            return 1.0
        return float(self.per_label_thresholds.get(label, self.default_threshold))


@dataclass(frozen=True)
class MultiLabelPrediction:
    """Validated output attached to each SmartNewspaper article."""

    labels: list[str]
    label_scores: dict[str, float]
    label_vector: list[int]
    is_multilabel_reliable: bool
    no_label_detected: bool
    num_labels: int = len(ALLOWED_LABELS)
    label_source: str = "keyword"
    rejected_labels: list[str] = field(default_factory=list)
    fallback_category: str | None = None

    allowed_labels: ClassVar[tuple[str, ...]] = ALLOWED_LABELS

    def to_dict(self) -> dict[str, Any]:
        """Convert the prediction to the JSON shape expected by `/api/feed`."""

        return {
            "labels": self.labels,
            "label_scores": self.label_scores,
            "label_vector": self.label_vector,
            "is_multilabel_reliable": self.is_multilabel_reliable,
            "no_label_detected": self.no_label_detected,
            "num_labels": self.num_labels,
            "label_source": self.label_source,
            "rejected_labels": self.rejected_labels,
            "fallback_category": self.fallback_category,
        }
