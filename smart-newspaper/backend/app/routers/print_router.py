"""Print preview, PDF generation, and PDF download endpoints."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse

from app.database import AsyncSessionLocal
from app.models import NewspaperEdition, User
from app.services.pdf_service import BACKEND_DIR, PdfService
from app.services.preview_service import PreviewService
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/print", tags=["print"])

template_service = TemplateService()
pdf_service = PdfService(template_service=template_service)
preview_service = PreviewService(template_service=template_service)
DownloadMode = Literal["attachment", "inline"]


@router.get("/templates")
async def get_print_templates() -> list[dict[str, Any]]:
    """Return available PDF/print templates."""
    return template_service.get_available_templates()


@router.get("/preview/{edition_id}", response_class=HTMLResponse)
async def preview_edition_html(
    edition_id: int,
    template: str = Query(default="A4"),
    user_id: str | None = Query(default=None, description="Temporary auth placeholder until current_user is wired"),
) -> HTMLResponse:
    """Return an HTML preview for one newspaper edition without generating a PDF."""
    try:
        async with AsyncSessionLocal() as db:
            edition = await _get_authorized_edition(db, edition_id, user_id)
            html = await preview_service.get_preview_for_edition(db, edition.id, template=template)
        return HTMLResponse(
            content=html,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Preview generation failed edition_id=%s", edition_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Preview generation failed") from exc


@router.post("/generate/{edition_id}")
async def generate_edition_pdf(
    edition_id: int,
    template: str = Query(default="A4"),
    user_id: str | None = Query(default=None, description="Temporary auth placeholder until current_user is wired"),
) -> dict[str, Any]:
    """Generate and store a PDF for one newspaper edition."""
    try:
        async with AsyncSessionLocal() as db:
            await _get_authorized_edition(db, edition_id, user_id)
            result = await pdf_service.generate_pdf_for_edition(db, edition_id=edition_id, template=template)
        return {
            "edition_id": result["edition_id"],
            "template": result["template"],
            "pdf_path": result["pdf_path"],
            "status": "generated",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("PDF generation endpoint failed edition_id=%s", edition_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="PDF generation failed") from exc


@router.get("/download/{edition_id}")
async def download_edition_pdf(
    edition_id: int,
    template: str = Query(default="A4"),
    mode: DownloadMode = Query(default="attachment"),
    user_id: str | None = Query(default=None, description="Temporary auth placeholder until current_user is wired"),
) -> StreamingResponse:
    """Stream an existing or newly generated PDF for one newspaper edition."""
    try:
        async with AsyncSessionLocal() as db:
            edition = await _get_authorized_edition(db, edition_id, user_id)
            selected_template = template_service.validate_template(template)
            pdf_path = _resolve_stored_pdf_path(getattr(edition, "pdf_path", None))
            if pdf_path is None or not pdf_path.exists():
                result = await pdf_service.generate_pdf_for_edition(db, edition_id=edition.id, template=selected_template)
                pdf_path = _resolve_stored_pdf_path(result.get("pdf_path"))
            if pdf_path is None or not pdf_path.exists():
                raise HTTPException(status_code=500, detail="Generated PDF file could not be found")
            pdf_bytes = pdf_path.read_bytes()

        disposition = "inline" if mode == "inline" else "attachment"
        filename = f"newspaper_edition_{edition_id}_{selected_template}.pdf"
        headers = {
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "no-store",
        }
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("PDF download failed edition_id=%s", edition_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="PDF download failed") from exc


async def _get_authorized_edition(db, edition_id: int, user_id: str | None) -> NewspaperEdition:  # type: ignore[no-untyped-def]
    """Load an edition and apply the temporary owner/admin authorization check.

    TODO: Replace the explicit ``user_id`` query parameter with the project's
    authenticated ``current_user`` dependency once auth is connected to FastAPI.
    Until then, calls without ``user_id`` are allowed so existing local/dev flows
    and tests are not broken.
    """
    edition = await db.get(NewspaperEdition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")

    if user_id is None:
        return edition

    requester = await db.get(User, str(user_id))
    requester_role = str(getattr(requester, "role", "USER") or "USER").upper() if requester is not None else "USER"
    if str(edition.user_id) == str(user_id) or requester_role == "ADMIN":
        return edition
    raise HTTPException(status_code=403, detail="You are not allowed to access this edition")


def _resolve_stored_pdf_path(pdf_path: str | None) -> Path | None:
    """Resolve a stored relative pdf_path under backend/ and reject unsafe paths."""
    if not pdf_path:
        return None
    candidate = Path(pdf_path)
    if not candidate.is_absolute():
        candidate = BACKEND_DIR / candidate
    try:
        resolved_backend = BACKEND_DIR.resolve()
        resolved_candidate = candidate.resolve()
        if not resolved_candidate.is_relative_to(resolved_backend):
            logger.warning("Rejected unsafe pdf_path outside backend: %s", pdf_path)
            return None
        return resolved_candidate
    except Exception:
        logger.warning("Could not resolve pdf_path=%s", pdf_path)
        return None
