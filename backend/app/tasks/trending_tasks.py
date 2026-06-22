"""Celery tasks for refreshing Module 6 trending cache."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

try:  # Project-root command: celery -A backend.celery_app ...
    from backend.celery_app import celery_app
except ImportError:  # Fallback for running from inside backend/.
    from celery_app import celery_app  # type: ignore[no-redef]

from app.database import AsyncSessionLocal
from app.services.trending_service import TrendingService

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.trending_tasks.refresh_trending_cache",
    max_retries=3,
    default_retry_delay=60,
)
def refresh_trending_cache(self: Any) -> dict[str, Any]:
    """Refresh the default trending cache every ten minutes."""
    task_name = "refresh_trending_cache"
    logger.info("Starting %s", task_name)
    try:
        result = asyncio.run(_refresh())
        logger.info("Finished %s cached_items=%s", task_name, result.get("cached_items", 0))
        return result
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.exception("%s failed permanently after %s retries", task_name, self.max_retries)
            raise exc
        logger.exception(
            "%s failed; retrying in %s seconds attempt=%s/%s",
            task_name,
            self.default_retry_delay,
            self.request.retries + 1,
            self.max_retries,
        )
        raise self.retry(exc=exc) from exc


async def _refresh() -> dict[str, Any]:
    """Run the async cache refresh in a new DB session."""
    async with AsyncSessionLocal() as db:
        return await TrendingService().refresh_trending_cache(db)
