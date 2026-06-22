"""PDF template CSS service for personal newspaper exports."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

logger = logging.getLogger(__name__)


class TemplateService:
    """Generate WeasyPrint paged-media CSS for supported PDF templates.

    The service is intentionally deterministic and side-effect free. Unsupported
    template names fall back to A4 so export endpoints can continue safely.
    """

    SIZE_CSS: dict[str, dict[str, Any]] = {
        "A4": {
            "label": "A4 Standart Gazete",
            "description": "Standart dikey A4 kişisel gazete çıktısı.",
            "size": "A4 portrait",
            "margin": "1.5cm",
            "columns": 3,
            "font_size": "10pt",
            "top_font_size": "9pt",
            "bottom_font_size": "8pt",
            "column_gap": "20px",
        },
        "TABLOID": {
            "label": "Tabloid Geniş Gazete",
            "description": "Geniş yatay gazete sayfası; daha fazla kolon ve kompakt font.",
            "size": "279mm 432mm landscape",
            "margin": "1.2cm",
            "columns": 4,
            "font_size": "9pt",
            "top_font_size": "9pt",
            "bottom_font_size": "8pt",
            "column_gap": "18px",
        },
        "BOOKLET": {
            "label": "Booklet Kitapçık",
            "description": "Küçük dikey A5 kitapçık formatı.",
            "size": "A5 portrait",
            "margin": "1cm",
            "columns": 2,
            "font_size": "9pt",
            "top_font_size": "8pt",
            "bottom_font_size": "7pt",
            "column_gap": "14px",
        },
    }

    def get_available_templates(self) -> list[dict[str, Any]]:
        """Return metadata for all supported PDF templates."""
        return [self.get_template_metadata(name) for name in self.SIZE_CSS]

    def validate_template(self, template: str | None) -> str:
        """Normalize a template name and return a safe supported template.

        Args:
            template: Raw template value from API/service callers.

        Returns:
            ``A4``, ``TABLOID`` or ``BOOKLET``. Invalid values fall back to
            ``A4`` with a warning instead of raising an exception.
        """
        normalized = str(template or "A4").strip().upper()
        if normalized not in self.SIZE_CSS:
            logger.warning("Unsupported PDF template=%s; falling back to A4", template)
            return "A4"
        return normalized

    def get_template_metadata(self, template: str | None) -> dict[str, Any]:
        """Return the selected template metadata with the normalized name."""
        selected = self.validate_template(template)
        metadata = deepcopy(self.SIZE_CSS[selected])
        metadata["name"] = selected
        return metadata

    def get_template_css(self, template: str = "A4") -> str:
        """Build CSS Paged Media rules for the selected PDF template."""
        meta = self.get_template_metadata(template)
        return f"""
@page {{
  size: {meta['size']};
  margin: {meta['margin']};
  @top-center {{
    content: "Personel Gazetesi";
    font-family: Arial, sans-serif;
    font-size: {meta['top_font_size']};
    color: #555;
  }}
  @bottom-right {{
    content: counter(page) " / " counter(pages);
    font-family: Arial, sans-serif;
    font-size: {meta['bottom_font_size']};
    color: #555;
  }}
}}

body {{
  font-size: {meta['font_size']};
}}

.newspaper-body {{
  column-count: {meta['columns']};
  column-gap: {meta['column_gap']};
  column-rule: 1px solid #ccc;
}}

.featured,
.masthead,
.edition-header,
.events-section,
.footer,
.empty-state {{
  column-span: all;
}}

@media print {{
  .newspaper-body {{
    column-count: {meta['columns']};
    column-gap: {meta['column_gap']};
    column-rule: 1px solid #ccc;
  }}
}}
""".strip()

    # Backward-compatible aliases used by P18 service/tests.
    def normalize_template(self, template: str | None = "A4") -> str:
        """Backward-compatible alias for validate_template()."""
        return self.validate_template(template)

    def build_page_css(self, template: str = "A4") -> str:
        """Backward-compatible alias for get_template_css()."""
        return self.get_template_css(template)
