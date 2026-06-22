"""Pydantic schemas for article filtering and pagination."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FilterParams(BaseModel):
    """Validated query parameters for duplicate-free article listing."""

    category_id: int | None = Field(default=None, ge=1)
    source_ids: list[int] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    language: str | None = Field(default=None, min_length=2, max_length=10)
    user_id: str | None = Field(default=None, description="Optional user id for language_preference fallback")
    sort_by: Literal["date", "popularity", "relevance"] = "date"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("source_ids")
    @classmethod
    def validate_source_ids(cls, value: list[int] | None) -> list[int] | None:
        """Remove duplicate source ids while preserving order."""
        if value is None:
            return None
        seen: set[int] = set()
        cleaned: list[int] = []
        for source_id in value:
            if source_id <= 0:
                raise ValueError("source_ids must contain positive integers")
            if source_id not in seen:
                cleaned.append(source_id)
                seen.add(source_id)
        return cleaned or None

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        """Normalize language codes for consistent SQL filtering."""
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, value: datetime | None, info):  # type: ignore[no-untyped-def]
        """Ensure date_to is not earlier than date_from when both are provided."""
        date_from = info.data.get("date_from") if hasattr(info, "data") else None
        if value is not None and date_from is not None and value < date_from:
            raise ValueError("date_to must be greater than or equal to date_from")
        return value
