"""Celery task for periodic MinHash/LSH duplicate re-indexing."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

try:  # Project-root command: celery -A backend.celery_app ...
    from backend.celery_app import celery_app
except ImportError:  # Fallback for running from inside backend/.
    from celery_app import celery_app  # type: ignore[no-redef]

from app.database import get_engine
from app.ml.duplicate_detector import DuplicateDetector
from app.models import Article

logger = logging.getLogger(__name__)
T = TypeVar("T")
BATCH_SIZE = 500


def _run_async(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Run an async coroutine factory from Celery's sync worker context."""
    return asyncio.run(coro_factory())


def _retry_or_raise(task: Any, exc: Exception, task_name: str) -> None:
    """Retry transient failures and log the permanent failure path."""
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
    name="app.tasks.dedup_task.rebuild_duplicate_index",
    max_retries=3,
    default_retry_delay=60,
)
def rebuild_duplicate_index(self: Any) -> dict[str, int]:
    """Rebuild the LSH index and mark near-duplicate articles in batches.

    This task avoids an all-pairs O(n²) comparison. Each article is queried only
    against the current LSH candidate index, then verified with exact Jaccard.
    """
    task_name = "rebuild_duplicate_index"
    logger.info("Starting %s", task_name)

    async def _job() -> dict[str, int]:
        engine = get_engine()
        detector = DuplicateDetector()
        detector.clear()

        scanned = 0
        marked_duplicate = 0
        indexed = 0
        errors = 0
        offset = 0

        async with AsyncSession(engine, expire_on_commit=False) as session:
            while True:
                result = await session.execute(
                    select(Article).order_by(Article.id.asc()).offset(offset).limit(BATCH_SIZE)
                )
                articles = list(result.scalars().all())
                if not articles:
                    break

                for article in articles:
                    scanned += 1
                    try:
                        text = f"{article.title} {str(article.content or '')[:500]}"
                        duplicate_result = detector.is_duplicate(text)
                        article.minhash_signature = detector.build_signature_for_text(text)

                        if duplicate_result.is_duplicate:
                            if not article.is_duplicate:
                                marked_duplicate += 1
                            article.is_duplicate = True
                        else:
                            article.is_duplicate = False
                            if detector.add(int(article.id), text):
                                indexed += 1
                    except Exception:
                        errors += 1
                        logger.exception("Dedup processing failed for article_id=%s", getattr(article, "id", None))

                await session.commit()
                offset += BATCH_SIZE

        return {
            "scanned": scanned,
            "marked_duplicate": marked_duplicate,
            "indexed": indexed,
            "errors": errors,
        }

    try:
        result = _run_async(_job)
        logger.info(
            "Finished %s scanned=%s marked_duplicate=%s indexed=%s errors=%s",
            task_name,
            result.get("scanned", 0),
            result.get("marked_duplicate", 0),
            result.get("indexed", 0),
            result.get("errors", 0),
        )
        return result
    except Exception as exc:
        _retry_or_raise(self, exc, task_name)
        return {"scanned": 0, "marked_duplicate": 0, "indexed": 0, "errors": 1}
