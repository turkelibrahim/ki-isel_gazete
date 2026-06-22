"""Celery tasks for generating personal newspaper editions."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select

from backend.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import User
from app.services.edition_pipeline_service import EditionPipelineService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_daily_editions(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Generate daily personal newspaper editions for all active users.

    A failure for one user is logged and counted but does not stop the other
    users.  Transient database/task-level failures are retried by Celery.
    """
    try:
        return asyncio.run(_generate_daily_editions_async())
    except Exception as exc:
        logger.exception("Daily edition generation task failed")
        raise self.retry(exc=exc) from exc


async def _generate_daily_editions_async() -> dict[str, Any]:
    """Async implementation used by the synchronous Celery task wrapper."""
    generated = 0
    errors = 0
    results: list[dict[str, Any]] = []
    async with AsyncSessionLocal() as db:
        users = list((await db.execute(select(User))).scalars().all())

    for user in users:
        user_id = str(user.id)
        try:
            async with AsyncSessionLocal() as db:
                result = await EditionPipelineService().generate_daily_edition(db, user_id=user_id)
                results.append({
                    "user_id": user_id,
                    "edition_id": result.get("edition_id"),
                    "status": "generated",
                })
                generated += 1
        except Exception as exc:
            logger.exception("Could not generate daily edition for user_id=%s", user_id)
            results.append({"user_id": user_id, "status": "error", "error": str(exc)})
            errors += 1
            continue

    return {
        "generated": generated,
        "errors": errors,
        "user_count": len(users),
        "results": results,
    }
