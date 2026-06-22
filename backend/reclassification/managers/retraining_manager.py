"""Retraining manager facade."""
from __future__ import annotations

from backend.reclassification.managers.reclassification_manager import ReclassificationManager, RetrainingTrigger


class RetrainingManager:
    """Coordinates threshold checks and retraining runs."""

    def __init__(self, manager: ReclassificationManager) -> None:
        self.manager = manager

    def check_retraining_threshold(self) -> tuple[bool, str]:
        """Return whether retraining should start."""
        return self.manager.check_retraining_threshold()

    def trigger_retraining(self, reason: str, triggered_by: str) -> RetrainingTrigger:
        """Create a retraining trigger."""
        return self.manager.trigger_retraining(reason, triggered_by)

    def run_retraining(self, trigger_id: str) -> bool:
        """Run retraining and deploy/rollback based on quality gates."""
        return self.manager.run_retraining(trigger_id)
