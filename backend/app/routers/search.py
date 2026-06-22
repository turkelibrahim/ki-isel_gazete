"""BM25 keyword search API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.database import AsyncSessionLocal
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])
search_service = SearchService()


@router.get("")
async def search_articles(
    q: str = Query(..., min_length=1, description="Search query, e.g. merkez bankası"),
    top: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    """Search duplicate-free articles using Okapi BM25 ranking."""
    try:
        async with AsyncSessionLocal() as db:
            return await search_service.search_articles(db, q, top=top)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("BM25 search failed q=%s", q)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Search failed") from exc


@router.post("/rebuild-index")
async def rebuild_search_index() -> dict[str, Any]:
    """Rebuild the in-memory BM25 index from duplicate-free articles."""
    try:
        async with AsyncSessionLocal() as db:
            return await search_service.rebuild_index(db)
    except Exception as exc:
        logger.exception("BM25 index rebuild endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Index rebuild failed") from exc


@router.get("/status")
async def search_status() -> dict[str, Any]:
    """Return current BM25 index status."""
    return search_service.status()
