"""Celery tasks for weekly LDA topic refresh."""

from __future__ import annotations

import asyncio
import logging

from app.database import AsyncSessionLocal
from app.services.topic_service import topic_service
from backend.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def refresh_topic_model(self) -> dict:
    """Refresh the LDA topic model from current non-duplicate articles."""
    try:
        return asyncio.run(_refresh_topic_model_async())
    except Exception as exc:
        logger.exception("Topic refresh task failed")
        raise self.retry(exc=exc) from exc


async def _refresh_topic_model_async() -> dict:
    """Async implementation for the Celery task."""
    async with AsyncSessionLocal() as db:
        result = await topic_service.train_topics(db)
        logger.info("Topic model refresh finished: %s", result)
        return result
