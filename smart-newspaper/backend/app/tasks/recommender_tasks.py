"""Celery tasks for weekly Module 7 recommender model training."""

from __future__ import annotations

import asyncio
import logging

from backend.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.services.recommender_training_service import RecommenderTrainingService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def train_recommender_models(self) -> dict:
    """Train IBCF and SVD recommender models from implicit feedback."""
    try:
        return asyncio.run(_train_recommender_models_async())
    except Exception as exc:  # pragma: no cover - Celery runtime path
        logger.exception("Recommender model training task failed")
        raise self.retry(exc=exc) from exc


async def _train_recommender_models_async() -> dict:
    """Async implementation used by the Celery task wrapper."""
    async with AsyncSessionLocal() as db:
        return await RecommenderTrainingService().train_recommenders(db)
