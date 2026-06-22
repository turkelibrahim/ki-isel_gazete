"""Pydantic schemas for Module 8 admin CRUD and audit log APIs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

AdminRole = Literal["ADMIN", "EDITOR", "USER"]


class UserRoleUpdateRequest(BaseModel):
    """Request body for changing a user's RBAC role."""

    role: AdminRole

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        """Normalize role values and reject everything outside the RBAC matrix."""
        normalized = str(value or "").strip().upper()
        if normalized not in {"ADMIN", "EDITOR", "USER"}:
            raise ValueError("role must be one of ADMIN, EDITOR, USER")
        return normalized


class SourceTrustUpdateRequest(BaseModel):
    """Request body for updating a source trust score."""

    trust_score: float = Field(..., ge=0.0, le=1.0)


class AdminListResponse(BaseModel):
    """Generic paginated response for admin list endpoints."""

    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int
    has_next: bool


class AuditLogResponse(BaseModel):
    """Audit log row exposed to admin users."""

    id: int
    user_id: str | None = None
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, Any] | None = None
    timestamp: str | None = None


class AdminActionResponse(BaseModel):
    """Standard response returned after a critical admin operation."""

    status: str
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, Any] = Field(default_factory=dict)
