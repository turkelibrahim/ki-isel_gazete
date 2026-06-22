"""Shared constants for manual reclassification and feedback loop."""
from __future__ import annotations

from enum import Enum

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
ALLOWED_CATEGORY_VALUES: tuple[str, ...] = tuple(ALLOWED_CATEGORIES.values())


class FeedbackStatus(str, Enum):
    """Allowed lifecycle values for an admin correction."""

    PENDING = "pending"
    PROCESSED = "processed"
    USED_IN_TRAINING = "used_in_training"
    REJECTED = "rejected"


class AdminRole(str, Enum):
    """Supported admin roles."""

    REVIEWER = "reviewer"
    EDITOR = "editor"
    SUPER_ADMIN = "super_admin"


ROLE_PERMISSIONS: dict[str, dict[str, object]] = {
    "reviewer": {
        "can_reclassify": True,
        "can_verify": False,
        "can_trigger_retrain": False,
        "can_view_stats": True,
        "max_corrections_per_day": 200,
        "feedback_weight": 1.0,
    },
    "editor": {
        "can_reclassify": True,
        "can_verify": True,
        "can_trigger_retrain": False,
        "can_view_stats": True,
        "max_corrections_per_day": 500,
        "feedback_weight": 1.2,
    },
    "super_admin": {
        "can_reclassify": True,
        "can_verify": True,
        "can_trigger_retrain": True,
        "can_view_stats": True,
        "max_corrections_per_day": 9999,
        "feedback_weight": 1.5,
    },
}

RETRAINING_TRIGGERS: dict[str, float | int] = {
    "count_threshold": 100,
    "daily_rate_threshold": 30,
    "accuracy_threshold": 0.80,
}

ACCURACY_DROP_TOLERANCE = 0.02
