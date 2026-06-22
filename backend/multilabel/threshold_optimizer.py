"""Threshold utilities for future ML-backed multi-label classifiers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .models import ALLOWED_LABELS, DEFAULT_LABEL_THRESHOLD


def clamp_threshold(value: float) -> float:
    """Clamp a threshold to a safe probability range."""

    return max(0.05, min(0.95, float(value)))


def normalize_thresholds(thresholds: dict[str, float] | None = None) -> dict[str, float]:
    """Return a threshold dict that never leaves the allowed label set."""

    thresholds = thresholds or {}
    return {label: clamp_threshold(thresholds.get(label, DEFAULT_LABEL_THRESHOLD)) for label in ALLOWED_LABELS}


def optimize_thresholds(
    validation_scores: Iterable[dict[str, float]],
    validation_targets: Iterable[Sequence[str]],
    candidate_thresholds: Sequence[float] = (0.45, 0.50, 0.55, 0.60, 0.65, 0.70),
) -> dict[str, float]:
    """Pick per-label thresholds using a simple F1 search.

    This function is intentionally dependency-free so it can run in small CI
    environments. A future BERT/fastText model can reuse the exact output.
    """

    scores_list = list(validation_scores)
    targets_list = [set(targets).intersection(ALLOWED_LABELS) for targets in validation_targets]
    if not scores_list or len(scores_list) != len(targets_list):
        return normalize_thresholds()

    optimized: dict[str, float] = {}
    for label in ALLOWED_LABELS:
        best_threshold = DEFAULT_LABEL_THRESHOLD
        best_f1 = -1.0
        for threshold in candidate_thresholds:
            tp = fp = fn = 0
            for scores, targets in zip(scores_list, targets_list):
                predicted = float(scores.get(label, 0.0)) >= threshold
                actual = label in targets
                tp += int(predicted and actual)
                fp += int(predicted and not actual)
                fn += int((not predicted) and actual)
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = float(threshold)
        optimized[label] = clamp_threshold(best_threshold)
    return optimized
