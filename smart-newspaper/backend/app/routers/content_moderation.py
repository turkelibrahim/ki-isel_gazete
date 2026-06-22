"""Two-layer content moderation API endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.database import AsyncSessionLocal
from app.dependencies.auth import require_role
from app.models import User
from app.services.content_moderation_service import ContentModerationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/moderation", tags=["content-moderation"])
moderation_service = ContentModerationService()


class CheckTextRequest(BaseModel):
    """Request for keyword + ML toxicity moderation."""

    text: str = Field(..., min_length=1)
    article_id: int | None = Field(default=None, ge=1)
    persist: bool = True


class ReviewResponse(BaseModel):
    """Moderation review response."""

    id: int
    article_id: int
    toxicity_score: float
    flagged_reason: str | None = None
    reason: str | None = None
    status: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    created_at: str | None = None


@router.post("/check-text")
async def check_text(
    payload: CheckTextRequest,
    editor_user: User = Depends(require_role("ADMIN", "EDITOR")),
) -> dict[str, Any]:
    """Moderate arbitrary text and optionally persist a PENDING/REJECTED article result."""
    _ = editor_user
    try:
        result = moderation_service.moderate_text(payload.text, article_id=payload.article_id)
        if payload.persist and payload.article_id is not None and result.get("status") in {"PENDING", "REJECTED"}:
            async with AsyncSessionLocal() as db:
                result["queue_item"] = await moderation_service.create_moderation_queue_item(db, payload.article_id, result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not check text moderation")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not moderate text") from exc


@router.get("/queue")
async def get_queue(
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    editor_user: User = Depends(require_role("ADMIN", "EDITOR")),
) -> dict[str, Any]:
    """List content moderation queue items for human review."""
    _ = editor_user
    try:
        async with AsyncSessionLocal() as db:
            return await moderation_service.list_queue(db, status_filter=status_filter, page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not list content moderation queue")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list moderation queue") from exc


@router.get("/stats")
async def get_content_moderation_stats(
    editor_user: User = Depends(require_role("ADMIN", "EDITOR")),
) -> dict[str, Any]:
    """Return keyword/ML content moderation statistics."""
    _ = editor_user
    try:
        async with AsyncSessionLocal() as db:
            return await moderation_service.get_stats(db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not read content moderation stats")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not read moderation stats") from exc


@router.post("/{moderation_id}/approve", response_model=ReviewResponse)
async def approve_moderation_item(
    moderation_id: int,
    editor_user: User = Depends(require_role("ADMIN", "EDITOR")),
) -> dict[str, Any]:
    """Approve a PENDING moderation item and write audit log."""
    try:
        async with AsyncSessionLocal() as db:
            return await moderation_service.approve_item(db, moderation_id=moderation_id, reviewer_id=str(editor_user.id))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not approve moderation item id=%s", moderation_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not approve moderation item") from exc


@router.post("/{moderation_id}/reject", response_model=ReviewResponse)
async def reject_moderation_item(
    moderation_id: int,
    editor_user: User = Depends(require_role("ADMIN", "EDITOR")),
) -> dict[str, Any]:
    """Reject a moderation item, hide the article and write audit log."""
    try:
        async with AsyncSessionLocal() as db:
            return await moderation_service.reject_item(db, moderation_id=moderation_id, reviewer_id=str(editor_user.id))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not reject moderation item id=%s", moderation_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not reject moderation item") from exc
