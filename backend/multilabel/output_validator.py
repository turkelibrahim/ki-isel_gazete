"""Validation helpers for SmartNewspaper multi-label outputs."""

from __future__ import annotations

import logging
from typing import Any

from .models import ALLOWED_LABELS, MultiLabelPrediction

LOGGER = logging.getLogger(__name__)
ALLOWED_SET = set(ALLOWED_LABELS)


def clean_labels(labels: list[str] | tuple[str, ...] | None) -> tuple[list[str], list[str]]:
    """Return accepted labels and rejected labels while preserving allowed order."""

    raw_labels = list(labels or [])
    rejected = [label for label in raw_labels if label not in ALLOWED_SET]
    if rejected:
        LOGGER.warning("Rejected unsupported news labels: %s", rejected)
    accepted = [label for label in ALLOWED_LABELS if label in set(raw_labels)]
    return accepted, rejected


def validate_prediction(payload: dict[str, Any]) -> MultiLabelPrediction:
    """Validate any prediction-like dict and force the exact public schema."""

    labels, rejected = clean_labels(payload.get("labels"))
    raw_scores = payload.get("label_scores") or {}
    scores = {
        label: round(max(0.0, min(1.0, float(raw_scores.get(label, 0.0) or 0.0))), 4)
        for label in ALLOWED_LABELS
    }
    vector = [1 if label in labels else 0 for label in ALLOWED_LABELS]
    no_label_detected = not labels
    reliable = bool(labels) and bool(payload.get("is_multilabel_reliable"))
    return MultiLabelPrediction(
        labels=labels,
        label_scores=scores,
        label_vector=vector,
        is_multilabel_reliable=reliable,
        no_label_detected=no_label_detected,
        num_labels=len(ALLOWED_LABELS),
        label_source=str(payload.get("label_source") or "keyword"),
        rejected_labels=rejected + list(payload.get("rejected_labels") or []),
        fallback_category=payload.get("fallback_category"),
    )
