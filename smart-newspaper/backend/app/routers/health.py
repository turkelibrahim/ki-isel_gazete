"""Health-check API routes."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}
