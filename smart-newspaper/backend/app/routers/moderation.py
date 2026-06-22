"""Admin moderation and active-learning endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.database import AsyncSessionLocal
from app.services.model_retrain_service import get_retrain_status, retrain_models_if_needed
from app.services.moderation_service import (
    approve_moderation_item,
    get_moderation_stats,
    get_pending_items,
    mark_reviewed,
    reclassify_moderation_item,
    require_admin,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/moderation", tags=["moderation"])


class AdminRequest(BaseModel):
    """Request body containing the admin actor."""

    admin_user_id: str = Field(..., min_length=1)


class ApproveRequest(AdminRequest):
    """Approve request with optional category override."""

    category_id: int | None = None


class ReclassifyRequest(AdminRequest):
    """Reclassification request using an explicit category."""

    category_id: int = Field(..., ge=1)


class RetrainRequest(AdminRequest):
    """Manual retrain trigger request."""

    force: bool = False


@router.get("/pending")
async def pending(admin_user_id: str = Query(..., min_length=1)) -> dict[str, Any]:
    """Return pending low-confidence items for admin review."""
    try:
        async with AsyncSessionLocal() as db:
            await require_admin(db, admin_user_id)
            return {"items": await get_pending_items(db)}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not list moderation pending items")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{moderation_id}/approve")
async def approve(moderation_id: int, request: ApproveRequest) -> dict[str, Any]:
    """Approve a predicted category or override it before approving."""
    try:
        async with AsyncSessionLocal() as db:
            return await approve_moderation_item(db, moderation_id, request.admin_user_id, request.category_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Moderation approve failed id=%s", moderation_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{moderation_id}/reclassify")
async def reclassify(moderation_id: int, request: ReclassifyRequest) -> dict[str, Any]:
    """Replace an automatic prediction with an admin-selected category."""
    try:
        async with AsyncSessionLocal() as db:
            return await reclassify_moderation_item(
                db,
                moderation_id,
                request.category_id,
                request.admin_user_id,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Moderation reclassify failed id=%s", moderation_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{moderation_id}/reviewed")
async def reviewed(moderation_id: int, request: AdminRequest) -> dict[str, Any]:
    """Mark a queue item reviewed without changing labels."""
    try:
        async with AsyncSessionLocal() as db:
            return await mark_reviewed(db, moderation_id, request.admin_user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Moderation mark-reviewed failed id=%s", moderation_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/retrain")
async def retrain(request: RetrainRequest) -> dict[str, Any]:
    """Trigger active-learning retraining if the human-label threshold is met."""
    try:
        async with AsyncSessionLocal() as db:
            await require_admin(db, request.admin_user_id)
            return await retrain_models_if_needed(db, force=request.force)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Manual retrain trigger failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stats")
async def stats(admin_user_id: str = Query(..., min_length=1)) -> dict[str, Any]:
    """Return active-learning and moderation counters."""
    try:
        async with AsyncSessionLocal() as db:
            await require_admin(db, admin_user_id)
            moderation = await get_moderation_stats(db)
            retrain = await get_retrain_status(db)
            return {"moderation": moderation, "retraining": retrain}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not read moderation stats")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
