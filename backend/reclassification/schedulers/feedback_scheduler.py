"""Nightly feedback analysis scheduler."""
from __future__ import annotations

from backend.reclassification.tasks.feedback_tasks import manager


def analyze_feedback():
    """Analyze the last seven days of feedback."""
    return manager.analyze_feedback(days=7)
