"""WeasyPrint PDF generation service for personal newspaper editions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NewspaperEdition

logger = logging.getLogger(__name__)

PdfTemplateName = Literal["A4", "TABLOID", "BOOKLET"]

BACKEND_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = BACKEND_DIR / "templates" / "newspaper"
PRINT_CSS_PATH = TEMPLATE_DIR / "print.css"
PDF_STORAGE_DIR = BACKEND_DIR / "storage" / "pdf" / "editions"


from app.services.template_service import TemplateService


class PdfService:
    """Create, store, and attach PDF exports for newspaper editions.

    The service intentionally imports WeasyPrint lazily so the FastAPI app can
    still start in environments where the native WeasyPrint dependencies are
    not installed.  PDF generation failures are logged and returned as
    controlled HTTP errors rather than crashing the process.
    """

    def __init__(
        self,
        storage_dir: str | Path | None = None,
        template_service: TemplateService | None = None,
    ) -> None:
        """Initialize the PDF storage and template helpers."""
        self.storage_dir = Path(storage_dir) if storage_dir is not None else PDF_STORAGE_DIR
        self.template_service = template_service or TemplateService()

    def generate_pdf_bytes(self, html_content: str, template: str = "A4") -> bytes:
        """Convert newspaper HTML content into PDF bytes using WeasyPrint.

        Args:
            html_content: The edition HTML stored in ``newspaper_editions``.
            template: One of ``A4``, ``TABLOID`` or ``BOOKLET``. Unsupported
                values fall back to ``A4``.

        Returns:
            Raw PDF bytes.

        Raises:
            HTTPException: 400 when HTML is empty, or 500 when WeasyPrint cannot
                render the document.
        """
        if not html_content or not html_content.strip():
            raise HTTPException(status_code=400, detail="html_content is empty; PDF cannot be generated")

        try:
            from weasyprint import CSS, HTML
        except Exception as exc:  # pragma: no cover - depends on system libraries
            logger.exception("WeasyPrint is not available")
            raise HTTPException(
                status_code=500,
                detail="WeasyPrint is not available. Install weasyprint and native Pango dependencies.",
            ) from exc

        try:
            selected_template = self.template_service.validate_template(template)
            page_css = self.template_service.get_template_css(selected_template)
            stylesheets: list[Any] = [CSS(string=page_css)]
            if PRINT_CSS_PATH.exists():
                stylesheets.insert(0, CSS(filename=str(PRINT_CSS_PATH)))
            html = HTML(string=html_content, base_url=str(BACKEND_DIR))
            pdf_bytes = html.write_pdf(stylesheets=stylesheets, presentational_hints=True)
            if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
                raise RuntimeError("WeasyPrint returned empty PDF bytes")
            return pdf_bytes
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to generate PDF for template=%s", template)
            raise HTTPException(status_code=500, detail="PDF generation failed") from exc

    def save_pdf_file(self, pdf_bytes: bytes, edition_id: int, template: str = "A4") -> str:
        """Save PDF bytes under backend/storage/pdf/editions and return a relative path."""
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="PDF bytes are empty")
        selected_template = self.template_service.validate_template(template)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"edition_{edition_id}_{selected_template}_{timestamp}.pdf"
        file_path = self.storage_dir / filename
        try:
            file_path.write_bytes(pdf_bytes)
        except Exception as exc:
            logger.exception("Could not save PDF file path=%s", file_path)
            raise HTTPException(status_code=500, detail="PDF file could not be saved") from exc
        return str(file_path.relative_to(BACKEND_DIR)).replace("\\", "/")

    async def generate_pdf_for_edition(
        self,
        db: AsyncSession,
        edition_id: int,
        template: str = "A4",
    ) -> dict[str, Any]:
        """Generate and persist a PDF for one newspaper edition.

        Args:
            db: AsyncSession owned by the caller.
            edition_id: Primary key in ``newspaper_editions``.
            template: PDF template name: ``A4``, ``TABLOID`` or ``BOOKLET``.

        Returns:
            Metadata about the generated PDF and updated edition row.
        """
        edition = await db.get(NewspaperEdition, edition_id)
        if edition is None:
            raise HTTPException(status_code=404, detail=f"Edition not found: {edition_id}")
        if not edition.html_content or not edition.html_content.strip():
            raise HTTPException(status_code=400, detail="Edition html_content is empty")

        selected_template = self.template_service.validate_template(template)
        pdf_bytes = self.generate_pdf_bytes(edition.html_content, selected_template)
        generated_path = self.save_pdf_file(pdf_bytes, edition_id=edition.id, template=selected_template)

        edition.pdf_path = generated_path
        if hasattr(edition, "updated_at"):
            edition.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(edition)

        return {
            "edition_id": edition.id,
            "user_id": edition.user_id,
            "edition_date": edition.edition_date.isoformat() if edition.edition_date else None,
            "template": selected_template,
            "pdf_path": edition.pdf_path,
            "byte_size": len(pdf_bytes),
            "status": "generated",
        }
