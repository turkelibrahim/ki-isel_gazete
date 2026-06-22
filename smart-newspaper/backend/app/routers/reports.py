"""Admin report generation, download and cleanup endpoints."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.database import AsyncSessionLocal
from app.dependencies.auth import require_role
from app.models import User
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])
report_service = ReportService()


REPORT_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".csv": "text/csv; charset=utf-8",
}



@router.post("/generate")
async def generate_report(
    days: int = Query(default=30, ge=1, le=365),
    format: Literal["pdf", "csv"] = Query(default="pdf"),
    admin_user: User = Depends(require_role("ADMIN")),
) -> dict[str, Any]:
    """Generate a PDF or CSV report under backend/storage/reports."""
    _ = admin_user
    try:
        async with AsyncSessionLocal() as db:
            return await report_service.generate_overview_report(db, days=days, format=format)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not generate report format=%s days=%s", format, days)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not generate report") from exc


@router.get("/download")
async def download_report(
    path: str = Query(..., description="Report filename or path returned by /api/reports/generate"),
    admin_user: User = Depends(require_role("ADMIN")),
) -> FileResponse:
    """Download only files inside backend/storage/reports; path traversal is rejected."""
    _ = admin_user
    safe_path = _resolve_report_path(path)
    if not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    media_type = REPORT_MEDIA_TYPES.get(safe_path.suffix.lower(), "application/octet-stream")
    return FileResponse(path=safe_path, media_type=media_type, filename=safe_path.name)


@router.get("/list")
async def list_reports(admin_user: User = Depends(require_role("ADMIN"))) -> dict[str, Any]:
    """List generated PDF/CSV reports newest first."""
    _ = admin_user
    try:
        items = report_service.list_reports()
        return {"items": items, "total": len(items)}
    except Exception as exc:
        logger.exception("Could not list reports")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list reports") from exc


@router.delete("/cleanup")
async def cleanup_reports(
    days: int = Query(default=30, ge=1, le=3650),
    admin_user: User = Depends(require_role("ADMIN")),
) -> dict[str, Any]:
    """Delete generated reports older than N days."""
    _ = admin_user
    try:
        return report_service.cleanup_old_reports(days=days)
    except Exception as exc:
        logger.exception("Could not cleanup reports")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not cleanup reports") from exc


def _reports_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "storage" / "reports"


def _resolve_report_path(raw_path: str) -> Path:
    """Resolve a user-supplied path safely under reports storage."""
    if not raw_path or ".." in raw_path.replace("\\", "/").split("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid report path")
    root = _reports_dir().resolve()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate.name
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid report path") from exc
    if resolved.suffix.lower() not in REPORT_MEDIA_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported report file type")
    return resolved
