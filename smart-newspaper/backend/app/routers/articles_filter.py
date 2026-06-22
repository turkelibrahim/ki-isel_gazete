"""Article filtering API with composite-index-friendly SQL filters."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError

from app.database import AsyncSessionLocal
from app.schemas.article_filters import FilterParams
from app.services.article_filter_service import filter_articles

logger = logging.getLogger(__name__)

router = APIRouter(tags=["articles-filter"])


@router.get("/api/articles")
async def list_filtered_articles(
    category_id: Annotated[int | None, Query(ge=1)] = None,
    source_ids: Annotated[list[str] | None, Query(description="Repeat or comma-separate source ids")] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    language: Annotated[str | None, Query(min_length=2, max_length=10)] = None,
    user_id: str | None = Query(default=None, description="Optional user id for language_preference fallback"),
    sort_by: Literal["date", "popularity", "relevance"] = "date",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    """Return paginated duplicate-free articles using dynamic SQL filters."""
    try:
        params = FilterParams(
            category_id=category_id,
            source_ids=_parse_source_ids(source_ids),
            date_from=date_from,
            date_to=date_to,
            language=language,
            user_id=user_id,
            sort_by=sort_by,
            page=page,
            page_size=page_size,
        )
        async with AsyncSessionLocal() as db:
            return await filter_articles(db, params)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Article filtering failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Article filtering failed",
        ) from exc


def _parse_source_ids(raw_values: list[str] | None) -> list[int] | None:
    """Parse repeated or comma-separated source_ids query parameters."""
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
                    detail=f"Invalid source_id: {cleaned}",
                ) from exc
    return parsed or None
