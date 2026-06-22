"""Celery tasks for scheduled news ingestion."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

try:  # Project-root command: celery -A backend.celery_app ...
    from backend.celery_app import celery_app
except ImportError:  # Fallback for running from inside backend/.
    from celery_app import celery_app  # type: ignore[no-redef]

from app.crawlers.spider_manager import SpiderManager
from app.database import get_engine
from app.services.news_api_service import NewsAPIService
from app.services.rss_service import RSSService

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _run_async(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Run an async ingestion coroutine from Celery's sync worker context."""
    return asyncio.run(coro_factory())


def _retry_or_raise(task: Any, exc: Exception, task_name: str) -> None:
    """Retry transient task failures and log final failures after max retries."""
    if task.request.retries >= task.max_retries:
        logger.exception("%s failed permanently after %s retries", task_name, task.max_retries)
        raise exc

    logger.exception(
        "%s failed; retrying in %s seconds attempt=%s/%s",
        task_name,
        task.default_retry_delay,
        task.request.retries + 1,
        task.max_retries,
    )
    raise task.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="app.tasks.fetch_tasks.fetch_breaking_news",
    max_retries=3,
    default_retry_delay=60,
)
def fetch_breaking_news(self: Any) -> dict[str, int]:
    """Fetch breaking-news provider data every five minutes."""
    task_name = "fetch_breaking_news"
    logger.info("Starting %s", task_name)

    async def _job() -> dict[str, int]:
        engine = get_engine()
        async with AsyncSession(engine, expire_on_commit=False) as session:
            return await NewsAPIService().fetch(session)

    try:
        result = _run_async(_job)
        logger.info("Finished %s fetched=%s errors=%s", task_name, result.get("fetched", 0), result.get("errors", 0))
        return result
    except Exception as exc:
        _retry_or_raise(self, exc, task_name)
        return {"fetched": 0, "errors": 1}


@celery_app.task(
    bind=True,
    name="app.tasks.fetch_tasks.fetch_all_rss",
    max_retries=3,
    default_retry_delay=60,
)
def fetch_all_rss(self: Any) -> dict[str, int]:
    """Fetch all active RSS source URLs hourly."""
    task_name = "fetch_all_rss"
    logger.info("Starting %s", task_name)

    async def _job() -> dict[str, int]:
        engine = get_engine()
        async with AsyncSession(engine, expire_on_commit=False) as session:
            return await RSSService().fetch_all(session)

    try:
        result = _run_async(_job)
        logger.info("Finished %s fetched=%s errors=%s", task_name, result.get("fetched", 0), result.get("errors", 0))
        return result
    except Exception as exc:
        _retry_or_raise(self, exc, task_name)
        return {"fetched": 0, "errors": 1}


@celery_app.task(
    bind=True,
    name="app.tasks.fetch_tasks.full_crawl",
    max_retries=3,
    default_retry_delay=60,
)
def full_crawl(self: Any) -> dict[str, int]:
    """Run the complete asynchronous web crawler every morning at 06:00."""
    task_name = "full_crawl"
    logger.info("Starting %s", task_name)

    async def _job() -> dict[str, int]:
        return await SpiderManager().run_all()

    try:
        result = _run_async(_job)
        logger.info("Finished %s crawled=%s errors=%s", task_name, result.get("crawled", 0), result.get("errors", 0))
        return result
    except Exception as exc:
        _retry_or_raise(self, exc, task_name)
        return {"crawled": 0, "errors": 1}
