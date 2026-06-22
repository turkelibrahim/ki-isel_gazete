"""Crawler API routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.crawlers.spider_manager import SpiderManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crawl", tags=["crawl"])


@router.post("/run")
async def run_crawl() -> dict[str, int]:
    """Run all active crawlers and return crawl statistics."""
    try:
        return await SpiderManager().run_all()
    except Exception as exc:
        logger.exception("Crawler run endpoint failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Crawler run failed",
        ) from exc


@router.get("/status")
async def crawl_status() -> dict[str, Any]:
    """Return the latest crawl status."""
    try:
        return await SpiderManager().status()
    except Exception as exc:
        logger.exception("Crawler status endpoint failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Crawler status failed",
        ) from exc
