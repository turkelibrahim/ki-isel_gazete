"""Monitoring, health check and recent log endpoints."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import AsyncSessionLocal
from app.dependencies.auth import require_role
from app.models import User
from app.services.monitoring_service import MonitoringService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])
monitoring_service = MonitoringService()



@router.get("/health")
async def health() -> dict[str, Any]:
    """Public health endpoint for DB, Redis, CPU, RAM, disk and model files."""
    try:
        async with AsyncSessionLocal() as db:
            return await monitoring_service.get_system_health(db)
    except Exception as exc:
        logger.exception("Database session could not be created during health check")
        # DB driver/connection failures must not hide CPU/RAM/Disk/Redis/model status.
        payload = await monitoring_service.get_system_health(None)
        payload["database"] = {"status": "error", "message": str(exc)}
        payload["status"] = "degraded"
        return payload


@router.get("/metrics")
async def metrics(admin_user: User = Depends(require_role("ADMIN"))) -> dict[str, Any]:
    """Admin-only application metrics for dashboards."""
    _ = admin_user
    try:
        async with AsyncSessionLocal() as db:
            return await monitoring_service.get_application_metrics(db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not load application metrics")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load metrics") from exc


@router.get("/logs/recent")
async def recent_logs(
    lines: int = Query(default=100, ge=1, le=1000),
    admin_user: User = Depends(require_role("ADMIN")),
) -> dict[str, Any]:
    """Return the last N lines from backend/logs/app.log."""
    _ = admin_user
    log_file = _backend_root() / "logs" / "app.log"
    if not log_file.exists():
        return {"items": [], "lines": lines, "log_file": str(log_file), "exists": False}
    try:
        return {"items": _tail_file(log_file, lines), "lines": lines, "log_file": str(log_file), "exists": True}
    except Exception as exc:
        logger.exception("Could not read recent logs")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not read logs") from exc


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _tail_file(path: Path, lines: int) -> list[str]:
    """Read recent log lines without loading huge log files into memory."""
    if lines <= 0:
        return []
    block_size = 8192
    data = b""
    with path.open("rb") as handle:
        handle.seek(0, 2)
        file_size = handle.tell()
        position = file_size
        while position > 0 and data.count(b"\n") <= lines:
            read_size = min(block_size, position)
            position -= read_size
            handle.seek(position)
            data = handle.read(read_size) + data
    decoded = data.decode("utf-8", errors="replace").splitlines()
    return decoded[-lines:]
