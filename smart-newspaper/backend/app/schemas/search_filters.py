"""Pydantic schemas for BM25 + SQL hybrid advanced search filters."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SearchFilterParams(BaseModel):
    """Validated query parameters for the advanced search endpoint."""

    q: str | None = Field(default=None, description="Optional keyword query for BM25 relevance search")
    category_ids: list[int] | None = None
    source_ids: list[int] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    language: str | None = Field(default=None, min_length=2, max_length=10)
    only_bookmarked: bool = False
    sort_by: Literal["relevance", "date", "popularity", "trend"] = "relevance"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("q")
    @classmethod
    def normalize_q(cls, value: str | None) -> str | None:
        """Treat blank q as missing so SQL-only filtering can run."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("category_ids", "source_ids")
    @classmethod
    def validate_positive_unique_ids(cls, value: list[int] | None) -> list[int] | None:
        """Require positive ids and remove duplicates while preserving order."""
        if value is None:
            return None
        seen: set[int] = set()
        cleaned: list[int] = []
        for item_id in value:
            if item_id <= 0:
                raise ValueError("ids must contain positive integers")
            if item_id not in seen:
                seen.add(item_id)
                cleaned.append(item_id)
        return cleaned or None

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        """Normalize language code for SQL filtering."""
        if value is None:
            return None
        cleaned = value.strip().lower()
        return cleaned or None

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, value: datetime | None, info):  # type: ignore[no-untyped-def]
        """Ensure date_to is not before date_from."""
        date_from = info.data.get("date_from") if hasattr(info, "data") else None
        if value is not None and date_from is not None and value < date_from:
            raise ValueError("date_to must be greater than or equal to date_from")
        return value


class AdvancedSearchResponse(BaseModel):
    """Documented response shape for advanced search results."""

    items: list[dict]
    page: int
    page_size: int
    total: int
    has_next: bool
    filters_applied: dict
