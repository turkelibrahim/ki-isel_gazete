"""Retraining Celery tasks."""
from __future__ import annotations

from backend.reclassification.tasks.celery_app import celery_app
from backend.reclassification.tasks.feedback_tasks import manager


@celery_app.task(bind=True)
def run_retraining(self, trigger_id: str) -> bool:
    """Run guarded retraining for a queued trigger."""
    return manager.run_retraining(trigger_id)
