"""Trending articles API using temporal decay scoring."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status

from app.database import AsyncSessionLocal
from app.services.trending_service import DEFAULT_WINDOW_HOURS, TrendingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trending", tags=["trending"])
trending_service = TrendingService()


@router.get("")
async def get_trending(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    window_hours: Annotated[int, Query(ge=1, le=336)] = DEFAULT_WINDOW_HOURS,
    language: Annotated[str | None, Query(min_length=2, max_length=10)] = None,
    source_ids: Annotated[list[str] | None, Query(description="Repeat or comma-separate source ids")] = None,
    category_id: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, Any]:
    """Return trending articles filtered by optional category, language and sources."""
    try:
        filters = {
            "category_id": category_id,
            "language": language,
            "source_ids": _parse_ids(source_ids, "source_id"),
        }
        async with AsyncSessionLocal() as db:
            items = await trending_service.get_trending_articles(
                db,
                limit=limit,
                window_hours=window_hours,
                filters=filters,
            )
        return {
            "items": items,
            "count": len(items),
            "limit": limit,
            "window_hours": window_hours,
            "filters_applied": {
                "category_id": category_id,
                "language": language,
                "source_ids": _parse_ids(source_ids, "source_id"),
                "exclude_duplicates": True,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Trending endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Trending query failed") from exc


@router.get("/category/{category_id}")
async def get_trending_by_category(
    category_id: int,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    """Return trending articles for one category."""
    if category_id <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="category_id must be positive")
    try:
        async with AsyncSessionLocal() as db:
            items = await trending_service.get_trending_by_category(db, category_id=category_id, limit=limit)
        return {"category_id": category_id, "items": items, "count": len(items), "limit": limit}
    except Exception as exc:
        logger.exception("Trending by category failed category_id=%s", category_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Trending category query failed") from exc


@router.post("/refresh-cache")
async def refresh_trending_cache() -> dict[str, Any]:
    """Refresh the default 72-hour trending cache immediately."""
    try:
        async with AsyncSessionLocal() as db:
            return await trending_service.refresh_trending_cache(db)
    except Exception as exc:
        logger.exception("Manual trending cache refresh failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Trending cache refresh failed") from exc


def _parse_ids(raw_values: list[str] | None, label: str) -> list[int] | None:
    """Parse repeated or comma-separated integer query parameters."""
    if not raw_values:
        return None
    parsed: list[int] = []
    for raw_value in raw_values:
        for part in str(raw_value).split(","):
            cleaned = part.strip()
            if not cleaned:
                continue
            try:
                value = int(cleaned)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid {label}: {cleaned}",
                ) from exc
            if value <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid {label}: {cleaned}",
                )
            if value not in parsed:
                parsed.append(value)
    return parsed or None
