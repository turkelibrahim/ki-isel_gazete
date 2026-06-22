"""HTML preview service for generated personal newspaper editions."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NewspaperEdition
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)


class PreviewService:
    """Return PDF-ready HTML previews without generating a PDF file."""

    def __init__(self, template_service: TemplateService | None = None) -> None:
        """Initialize the preview service with a TemplateService instance."""
        self.template_service = template_service or TemplateService()

    async def get_preview_for_edition(
        self,
        db: AsyncSession,
        edition_id: int,
        template: str = "A4",
    ) -> str:
        """Return an edition HTML preview decorated with print template CSS.

        Args:
            db: Async SQLAlchemy session owned by the caller.
            edition_id: ``newspaper_editions`` primary key.
            template: PDF template name. Invalid values fall back to A4.

        Returns:
            HTML string suitable for browser preview.

        Raises:
            HTTPException: 404 when the edition does not exist, 400 when its
                ``html_content`` field is empty.
        """
        edition = await db.get(NewspaperEdition, edition_id)
        if edition is None:
            raise HTTPException(status_code=404, detail="Edition not found")
        if not edition.html_content or not edition.html_content.strip():
            raise HTTPException(status_code=400, detail="Edition html_content is empty")
        return self._inject_template_css(edition.html_content, template)

    def _inject_template_css(self, html_content: str, template: str = "A4") -> str:
        """Inject template CSS into an HTML document for faithful preview rendering."""
        selected_template = self.template_service.validate_template(template)
        template_css = self.template_service.get_template_css(selected_template)
        metadata = self.template_service.get_template_metadata(selected_template)
        preview_css = f"""
<style id=\"pdf-template-preview-css\">
/* Preview-only CSS injected by PreviewService. Actual PDF export uses WeasyPrint stylesheets. */
:root {{
  --pdf-template-name: \"{metadata['name']}\";
}}
{template_css}
</style>
""".strip()
        lower_html = html_content.lower()
        if "</head>" in lower_html:
            index = lower_html.rfind("</head>")
            return html_content[:index] + "\n" + preview_css + "\n" + html_content[index:]
        return preview_css + "\n" + html_content

    def preview_metadata(self, template: str = "A4") -> dict[str, Any]:
        """Return template metadata used by the HTML preview."""
        return self.template_service.get_template_metadata(template)
