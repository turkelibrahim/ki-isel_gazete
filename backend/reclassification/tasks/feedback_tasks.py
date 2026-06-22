"""Feedback Celery tasks."""
from __future__ import annotations

from backend.reclassification.managers.reclassification_manager import ReclassificationManager
from backend.reclassification.tasks.celery_app import celery_app

manager = ReclassificationManager()


@celery_app.task(bind=True, max_retries=3)
def process_feedback(self, record_id: int) -> bool:
    """Process one feedback record with retry support when Celery is available."""
    try:
        return manager.process_feedback(record_id)
    except Exception as exc:  # pragma: no cover - retry path depends on Celery.
        retry = getattr(self, "retry", None)
        if retry:
            raise retry(exc=exc, countdown=2)
        manager.dead_letter_queue.append({"record_id": record_id, "reason": str(exc)})
        return False


@celery_app.task(bind=True, max_retries=3)
def check_retraining_threshold(self) -> tuple[bool, str]:
    """Check whether enough processed feedback exists for retraining."""
    return manager.check_retraining_threshold()
