"""Advanced BM25 + SQL hybrid search API."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError

from app.database import AsyncSessionLocal
from app.schemas.search_filters import SearchFilterParams
from app.services.advanced_search_service import AdvancedSearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search/advanced", tags=["advanced-search"])
advanced_search_service = AdvancedSearchService()


@router.get("")
async def advanced_search(
    q: str | None = Query(default=None, description="Optional keyword query for BM25 relevance"),
    category_ids: Annotated[list[str] | None, Query(description="Repeat or comma-separate category ids")] = None,
    source_ids: Annotated[list[str] | None, Query(description="Repeat or comma-separate source ids")] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    language: Annotated[str | None, Query(min_length=2, max_length=10)] = None,
    only_bookmarked: bool = False,
    user_id: str | None = Query(default=None, description="Required when only_bookmarked=true"),
    sort_by: Literal["relevance", "date", "popularity", "trend"] = "relevance",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    """Search articles with optional BM25 relevance plus SQL filters."""
    try:
        params = SearchFilterParams(
            q=q,
            category_ids=_parse_ids(category_ids, "category_id"),
            source_ids=_parse_ids(source_ids, "source_id"),
            date_from=date_from,
            date_to=date_to,
            language=language,
            only_bookmarked=only_bookmarked,
            sort_by=sort_by,
            page=page,
            page_size=page_size,
        )
        async with AsyncSessionLocal() as db:
            return await advanced_search_service.advanced_search(db, user_id=user_id, params=params)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Advanced search failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Advanced search failed") from exc


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
                parsed.append(int(cleaned))
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid {label}: {cleaned}",
                ) from exc
    return parsed or None
