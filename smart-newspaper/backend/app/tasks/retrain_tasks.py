"""Celery tasks for active-learning model retraining."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.services.model_retrain_service import retrain_models_if_needed as retrain_service

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="app.tasks.retrain_tasks.retrain_models_if_needed")
def retrain_models_if_needed(self: Any, force: bool = False) -> dict[str, Any]:
    """Retrain NB/SVM models if enough human labels have accumulated."""
    try:
        logger.info("Starting active-learning retrain task force=%s", force)
        result = asyncio.run(_run(force=force))
        logger.info("Finished active-learning retrain task result=%s", result)
        return result
    except Exception as exc:
        logger.exception("Active-learning retrain task failed")
        raise self.retry(exc=exc) from exc


async def _run(force: bool = False) -> dict[str, Any]:
    """Create a fresh AsyncSession for the Celery worker process."""
    async with AsyncSessionLocal() as db:
        return await retrain_service(db, force=force)
