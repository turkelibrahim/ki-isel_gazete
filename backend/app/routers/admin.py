"""Admin CRUD, soft delete and audit-log API endpoints for Module 8."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import AsyncSessionLocal
from app.dependencies.auth import require_role
from app.models import User
from app.schemas.admin import AdminActionResponse, AdminListResponse, SourceTrustUpdateRequest, UserRoleUpdateRequest
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_service = AdminService()



@router.get("/users", response_model=AdminListResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin_user: User = Depends(require_role("ADMIN")),
) -> dict[str, Any]:
    """List users for the admin panel."""
    _ = admin_user
    try:
        async with AsyncSessionLocal() as db:
            return await admin_service.list_users(db, page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not list users")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list users") from exc


@router.patch("/users/{user_id}/role", response_model=AdminActionResponse)
async def update_user_role(
    user_id: str,
    payload: UserRoleUpdateRequest,
    admin_user: User = Depends(require_role("ADMIN")),
) -> dict[str, Any]:
    """Update a user's role. Admins cannot update their own role here."""
    try:
        async with AsyncSessionLocal() as db:
            return await admin_service.update_user_role(db, user_id=user_id, role=payload.role, admin_user_id=str(admin_user.id))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not update user role user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update user role") from exc


@router.get("/sources", response_model=AdminListResponse)
async def list_sources(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin_user: User = Depends(require_role("ADMIN")),
) -> dict[str, Any]:
    """List news sources for admin management."""
    _ = admin_user
    try:
        async with AsyncSessionLocal() as db:
            return await admin_service.list_sources(db, page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not list sources")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list sources") from exc


@router.post("/sources/{source_id}/activate", response_model=AdminActionResponse)
async def activate_source(source_id: int, admin_user: User = Depends(require_role("ADMIN"))) -> dict[str, Any]:
    """Activate a source and write audit log."""
    try:
        async with AsyncSessionLocal() as db:
            return await admin_service.activate_source(db, source_id=source_id, admin_user_id=str(admin_user.id))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not activate source source_id=%s", source_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not activate source") from exc


@router.post("/sources/{source_id}/deactivate", response_model=AdminActionResponse)
async def deactivate_source(source_id: int, admin_user: User = Depends(require_role("ADMIN"))) -> dict[str, Any]:
    """Deactivate a source instead of hard deleting it."""
    try:
        async with AsyncSessionLocal() as db:
            return await admin_service.deactivate_source(db, source_id=source_id, admin_user_id=str(admin_user.id))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not deactivate source source_id=%s", source_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not deactivate source") from exc


@router.patch("/sources/{source_id}/trust-score", response_model=AdminActionResponse)
async def update_source_trust_score(
    source_id: int,
    payload: SourceTrustUpdateRequest,
    admin_user: User = Depends(require_role("ADMIN")),
) -> dict[str, Any]:
    """Update source trust score in the safe 0.0-1.0 badge range."""
    try:
        async with AsyncSessionLocal() as db:
            return await admin_service.update_source_trust_score(
                db,
                source_id=source_id,
                trust_score=payload.trust_score,
                admin_user_id=str(admin_user.id),
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not update source trust score source_id=%s", source_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update trust score") from exc


@router.get("/articles", response_model=AdminListResponse)
async def list_articles_admin(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    source_id: int | None = Query(default=None, ge=1),
    language: str | None = Query(default=None, min_length=2, max_length=10),
    is_duplicate: bool | None = Query(default=None),
    q: str | None = Query(default=None),
    admin_user: User = Depends(require_role("ADMIN")),
) -> dict[str, Any]:
    """List articles with admin-side filters."""
    _ = admin_user
    try:
        async with AsyncSessionLocal() as db:
            return await admin_service.list_articles_admin(
                db,
                {
                    "page": page,
                    "page_size": page_size,
                    "source_id": source_id,
                    "language": language,
                    "is_duplicate": is_duplicate,
                    "q": q,
                },
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not list admin articles")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list articles") from exc


@router.post("/articles/{article_id}/mark-duplicate", response_model=AdminActionResponse)
async def mark_article_duplicate(article_id: int, admin_user: User = Depends(require_role("ADMIN"))) -> dict[str, Any]:
    """Mark article as duplicate instead of deleting it."""
    try:
        async with AsyncSessionLocal() as db:
            return await admin_service.mark_article_duplicate(db, article_id=article_id, admin_user_id=str(admin_user.id))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not mark article duplicate article_id=%s", article_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not mark duplicate") from exc


@router.post("/articles/{article_id}/safe-delete", response_model=AdminActionResponse)
async def safe_delete_article(article_id: int, admin_user: User = Depends(require_role("ADMIN"))) -> dict[str, Any]:
    """Safe-delete an article by setting is_duplicate=True; no hard delete is used."""
    try:
        async with AsyncSessionLocal() as db:
            return await admin_service.delete_article_safe(db, article_id=article_id, admin_user_id=str(admin_user.id))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not safe delete article article_id=%s", article_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not safe delete article") from exc


@router.get("/audit-log", response_model=AdminListResponse)
async def audit_log(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin_user: User = Depends(require_role("ADMIN")),
) -> dict[str, Any]:
    """List audit_log rows newest first."""
    _ = admin_user
    try:
        async with AsyncSessionLocal() as db:
            return await admin_service.list_audit_logs(db, page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not list audit log")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list audit log") from exc
