"""API routes for article keyword extraction."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.database import AsyncSessionLocal
from app.services.keyword_service import extract_and_save_keywords, extract_keywords_batch, get_article_keywords

logger = logging.getLogger(__name__)

router = APIRouter(tags=["keywords"])


@router.post("/api/articles/{article_id}/keywords")
async def extract_one(article_id: int, top_n: int = Query(default=15, ge=1, le=50)) -> dict[str, Any]:
    """Extract and save keywords for one article."""
    try:
        async with AsyncSessionLocal() as db:
            return await extract_and_save_keywords(db, article_id, top_n=top_n)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Keyword extraction failed article_id=%s", article_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Keyword extraction failed: {exc}",
        ) from exc


@router.post("/api/keywords/batch")
async def extract_many(
    limit: int = Query(default=50, ge=1, le=500),
    top_n: int = Query(default=15, ge=1, le=50),
) -> dict[str, Any]:
    """Extract and save keywords for a batch of articles."""
    try:
        async with AsyncSessionLocal() as db:
            return await extract_keywords_batch(db, limit=limit, top_n=top_n)
    except Exception as exc:
        logger.exception("Keyword batch extraction failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Keyword batch extraction failed: {exc}",
        ) from exc


@router.get("/api/articles/{article_id}/keywords")
async def list_keywords(article_id: int) -> list[dict[str, Any]]:
    """Return saved keywords for one article."""
    try:
        async with AsyncSessionLocal() as db:
            return await get_article_keywords(db, article_id)
    except Exception as exc:
        logger.exception("Keyword listing failed article_id=%s", article_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Keyword listing failed: {exc}",
        ) from exc
