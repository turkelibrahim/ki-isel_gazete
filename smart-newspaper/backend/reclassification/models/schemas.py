"""Pydantic schemas for the admin reclassification API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .enums import ALLOWED_CATEGORY_VALUES


class ReclassifyRequest(BaseModel):
    """Request body for a manual article label correction."""

    article_id: str = Field(..., min_length=1)
    corrected_labels: list[str]
    correction_reason: str | None = Field(default=None, max_length=1000)

    @field_validator("corrected_labels")
    @classmethod
    def validate_labels(cls, value: list[str]) -> list[str]:
        """Reject empty, duplicated, or non-whitelisted categories."""
        if not value:
            raise ValueError("En az bir kategori seçilmelidir.")
        allowed = set(ALLOWED_CATEGORY_VALUES)
        invalid = [label for label in value if label not in allowed]
        if invalid:
            raise ValueError(f"Geçersiz kategori: {invalid}. İzin verilenler: {list(ALLOWED_CATEGORY_VALUES)}")
        if len(value) != len(set(value)):
            raise ValueError("Aynı kategori iki kez seçilemez.")
        return value


class ReclassifyResponse(BaseModel):
    """Response returned after a correction is saved."""

    success: bool
    record_id: int
    article_id: str
    corrected_labels: list[str]
    message: str
    requires_verification: bool
    feedback_queued: bool


class VerifyRequest(BaseModel):
    """Request body for second-admin verification."""

    approved: bool
    note: str | None = Field(default=None, max_length=1000)


class FeedbackQueueStatus(BaseModel):
    """Current feedback queue counters."""

    pending_count: int
    processed_count: int
    retraining_threshold: int
    next_retraining_at: datetime | None
    current_batch_id: int


class AdminCorrectionStats(BaseModel):
    """Per-admin correction performance summary."""

    admin_id: int
    username: str
    total_corrections: int
    corrections_today: int
    accuracy_rate: float
    most_corrected_category: str
    avg_corrections_per_day: float


class AuthLoginRequest(BaseModel):
    """Admin login body."""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AuthLoginResponse(BaseModel):
    """Admin login response."""

    success: bool
    token: str
    expires_at: datetime
    admin: dict[str, Any]
