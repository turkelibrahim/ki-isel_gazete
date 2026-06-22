"""Engagement analytics API endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.database import AsyncSessionLocal
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])
analytics_service = AnalyticsService()


@router.get("/overview")
async def analytics_overview() -> dict[str, Any]:
    """Return compact dashboard totals for admin/reporting screens.

    TODO(auth): restrict this endpoint to ADMIN/EDITOR once auth dependencies are wired.
    """
    try:
        async with AsyncSessionLocal() as db:
            return await analytics_service.get_overview(db)
    except Exception as exc:
        logger.exception("Could not load analytics overview")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load overview") from exc


@router.get("/dau")
async def daily_active_users(days: int = Query(default=30, ge=1, le=365)) -> list[dict[str, Any]]:
    """Return daily active users for the requested period.

    TODO(auth): restrict this endpoint to ADMIN/EDITOR once auth dependencies are wired.
    """
    try:
        async with AsyncSessionLocal() as db:
            return await analytics_service.get_daily_active_users(db, days=days)
    except Exception as exc:
        logger.exception("Could not load DAU analytics")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load DAU") from exc


@router.get("/top-articles")
async def top_articles(
    days: int = Query(default=7, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Return top articles ordered by weighted engagement score.

    TODO(auth): restrict this endpoint to ADMIN/EDITOR once auth dependencies are wired.
    """
    try:
        async with AsyncSessionLocal() as db:
            return await analytics_service.get_top_articles(db, days=days, limit=limit)
    except Exception as exc:
        logger.exception("Could not load top articles analytics")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load top articles") from exc


@router.get("/categories")
async def category_reads(days: int = Query(default=30, ge=1, le=365)) -> list[dict[str, Any]]:
    """Return category-level engagement metrics.

    TODO(auth): restrict this endpoint to ADMIN/EDITOR once auth dependencies are wired.
    """
    try:
        async with AsyncSessionLocal() as db:
            return await analytics_service.get_category_reads(db, days=days)
    except Exception as exc:
        logger.exception("Could not load category analytics")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load categories") from exc


@router.get("/user/{user_id}")
async def user_analytics(
    user_id: str,
    days: int = Query(default=30, ge=1, le=365),
    requester_user_id: str | None = Query(default=None, description="TODO(auth): replace with current_user.id"),
    requester_role: str = Query(default="USER", description="TODO(auth): replace with current_user.role"),
) -> dict[str, Any]:
    """Return one user's analytics.

    Until auth is connected, optional requester query parameters enforce the intended
    rule: users can read their own analytics, ADMIN can read all users.
    """
    _assert_user_permission(target_user_id=user_id, requester_user_id=requester_user_id, requester_role=requester_role)
    try:
        async with AsyncSessionLocal() as db:
            return await analytics_service.get_user_analytics(db, user_id=user_id, days=days)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not load user analytics user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load user analytics") from exc


@router.get("/sources")
async def source_performance(days: int = Query(default=30, ge=1, le=365)) -> list[dict[str, Any]]:
    """Return source-level article, view, trust and engagement metrics.

    TODO(auth): restrict this endpoint to ADMIN/EDITOR once auth dependencies are wired.
    """
    try:
        async with AsyncSessionLocal() as db:
            return await analytics_service.get_source_performance(db, days=days)
    except Exception as exc:
        logger.exception("Could not load source analytics")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load sources") from exc


def _assert_user_permission(target_user_id: str, requester_user_id: str | None, requester_role: str) -> None:
    """Temporary permission guard until the real auth dependency is connected."""
    role = (requester_role or "USER").upper()
    if role in {"ADMIN", "EDITOR"}:
        return
    if requester_user_id is None:
        # TODO(auth): require current_user once authentication is wired. Kept permissive
        # for local MVP/dev calls where no auth layer exists yet.
        return
    if str(requester_user_id) != str(target_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
