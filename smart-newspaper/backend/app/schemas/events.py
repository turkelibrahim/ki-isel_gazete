"""Pydantic schemas for event CRUD and text detection APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EventCreate(BaseModel):
    """Request body for manual event creation."""

    title: str = Field(..., min_length=1, max_length=500)
    event_date: datetime
    description: str | None = None
    location: str | None = None
    category: str | None = Field(default=None, max_length=100)
    remind_at: datetime | None = None
    user_id: str | None = Field(default=None, max_length=255)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        """Trim title whitespace."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title cannot be empty")
        return cleaned

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        """Normalize category names to uppercase when provided."""
        if value is None:
            return None
        cleaned = value.strip().upper()
        return cleaned or None


class EventUpdate(BaseModel):
    """Partial update body for an event."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    event_date: datetime | None = None
    description: str | None = None
    location: str | None = None
    category: str | None = Field(default=None, max_length=100)
    remind_at: datetime | None = None
    user_id: str | None = Field(default=None, max_length=255)
    is_notified: bool | None = None

    @field_validator("title")
    @classmethod
    def clean_optional_title(cls, value: str | None) -> str | None:
        """Trim title whitespace when present."""
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title cannot be empty")
        return cleaned

    @field_validator("category")
    @classmethod
    def normalize_optional_category(cls, value: str | None) -> str | None:
        """Normalize optional category names to uppercase."""
        if value is None:
            return None
        cleaned = value.strip().upper()
        return cleaned or None


class EventResponse(BaseModel):
    """Serialized event response."""

    id: int
    title: str
    description: str | None = None
    location: str | None = None
    category: str | None = None
    event_date: str
    remind_at: str | None = None
    user_id: str | None = None
    is_notified: bool
    is_active: bool
    created_at: str | None = None


class EventDetectionRequest(BaseModel):
    """Request body for event detection from raw text."""

    text: str = Field(..., min_length=1)


class EventDetectionResponse(BaseModel):
    """Response body for detection and persistence from text."""

    created_count: int
    items: list[EventResponse]
    status: str = "processed"
    meta: dict[str, Any] = Field(default_factory=dict)
