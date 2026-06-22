"""Feedback manager facade used by Celery tasks and tests."""
from __future__ import annotations

from backend.reclassification.managers.reclassification_manager import ReclassificationManager


class FeedbackManager:
    """Small wrapper around ReclassificationManager feedback operations."""

    def __init__(self, manager: ReclassificationManager) -> None:
        self.manager = manager

    def process_feedback(self, record_id: int) -> bool:
        """Process one feedback record safely."""
        return self.manager.process_feedback(record_id)

    def analyze_feedback(self, days: int = 7):
        """Return recent feedback analysis."""
        return self.manager.analyze_feedback(days=days)
