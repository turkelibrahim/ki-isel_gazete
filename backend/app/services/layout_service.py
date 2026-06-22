"""Jinja2 layout rendering for personal newspaper editions."""

from __future__ import annotations

import html
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import arrow
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from app.services.citation_service import CitationService

logger = logging.getLogger(__name__)

TR_MONTHS = {
    1: "Ocak",
    2: "Şubat",
    3: "Mart",
    4: "Nisan",
    5: "Mayıs",
    6: "Haziran",
    7: "Temmuz",
    8: "Ağustos",
    9: "Eylül",
    10: "Ekim",
    11: "Kasım",
    12: "Aralık",
}


class LayoutService:
    """Render PDF-ready newspaper HTML with a Jinja2 template."""

    def __init__(self, template_root: str | Path | None = None) -> None:
        """Initialize a Jinja2 environment and custom filters."""
        default_root = Path(__file__).resolve().parents[2] / "templates"
        self.template_root = Path(template_root) if template_root is not None else default_root
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_root)),
            autoescape=select_autoescape(("html", "xml")),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["truncate_chars"] = truncate_chars
        self.env.filters["date_tr"] = date_tr
        self.env.filters["humanize_time"] = humanize_time
        self.env.filters["safe_url"] = safe_url
        self.env.globals["render_citation"] = render_citation
        self.citation_service = CitationService()

    def render_daily(
        self,
        articles: Iterable[dict[str, Any]],
        events: Iterable[dict[str, Any]] | None,
        user: dict[str, Any],
        *,
        generated_at: datetime | None = None,
        edition_title: str = "Kişisel Gazete",
        edition_date: datetime | date | str | None = None,
        citations: dict[int, dict[str, Any]] | None = None,
    ) -> str:
        """Render the daily personal newspaper HTML.

        Args:
            articles: Ordered article dictionaries. Index 0 becomes the featured headline,
                1:4 become secondary cards, and the remainder become compact blocks.
            events: Optional event dictionaries rendered in the event box.
            user: User metadata dictionary with name/email/id fields.
            generated_at: Render timestamp. UTC now is used by default.
            edition_title: Masthead title.
            edition_date: Edition date shown in Turkish format.
            citations: Optional article_id keyed citation metadata. When absent, CitationService builds it automatically.

        Returns:
            A complete HTML document string suitable for browser preview or PDF conversion.
        """
        generated_at = generated_at or datetime.now(timezone.utc)
        article_list = list(articles)
        citation_map = citations if citations is not None else self.citation_service.build_citations(article_list)
        normalized_articles = self._normalize_articles(article_list, citation_map)
        template = self.env.get_template("newspaper/daily.html")
        return template.render(
            articles=normalized_articles,
            events=list(events or []),
            user=user or {},
            generated_at=generated_at,
            edition_date=edition_date or generated_at,
            edition_title=edition_title,
            citations=citation_map,
        )

    def _normalize_articles(
        self,
        articles: list[dict[str, Any]],
        citations: dict[int, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Attach citation metadata and safe defaults without mutating callers' data."""
        normalized: list[dict[str, Any]] = []
        for raw_article in articles:
            row = dict(raw_article)
            article_id = _safe_int(row.get("id") or row.get("article_id"))
            if article_id is not None:
                row.setdefault("article_id", article_id)
                if article_id in citations:
                    row["citation"] = {**citations[article_id], **dict(row.get("citation") or {})}
            row.setdefault("title", "Başlıksız haber")
            row.setdefault("summary", None)
            row.setdefault("content", "")
            row.setdefault("url", "#")
            row.setdefault("image_url", None)
            row.setdefault("citation", dict(row.get("citation") or {}))
            normalized.append(row)
        return normalized


def truncate_chars(value: Any, length: int = 120) -> str:
    """Cut long text to a fixed number of characters with an ellipsis."""
    text = " ".join(str(value or "").split())
    if length <= 0 or len(text) <= length:
        return text
    return text[: max(length - 1, 0)].rstrip() + "…"


def date_tr(value: Any) -> str:
    """Format date-like values as Turkish day month year, e.g. 21 Haziran 2026."""
    parsed = _parse_datetime(value)
    if parsed is None:
        return ""
    return f"{parsed.day} {TR_MONTHS.get(parsed.month, parsed.strftime('%B'))} {parsed.year}"


def humanize_time(value: Any) -> str:
    """Return Turkish relative time such as '3 saat önce'."""
    parsed = _parse_datetime(value)
    if parsed is None:
        return ""
    try:
        return arrow.get(parsed).humanize(locale="tr")
    except Exception:
        logger.warning("Could not humanize time value=%r", value, exc_info=True)
        return date_tr(parsed)


def safe_url(value: Any) -> str:
    """Return a usable URL or '#' when a URL is absent."""
    text = str(value or "").strip()
    return text if text else "#"


def render_citation(article: dict[str, Any]) -> Markup:
    """Render citation/source metadata for one article as safe HTML."""
    citation = dict(article.get("citation") or {})
    citation_text = citation.get("citation_text")
    trust_badge = citation.get("trust_badge") or _trust_badge(citation.get("trust_score") or article.get("source_trust_score"))
    article_url = safe_url(citation.get("article_url") or article.get("url"))
    source_url = safe_url(citation.get("source_url") or article_url)

    if citation_text:
        return Markup(
            '<div class="citation">'
            f'<a href="{html.escape(article_url)}">{html.escape(str(citation_text))}</a>'
            '</div>'
        )

    source_name = citation.get("source_name") or citation.get("publisher") or article.get("source_name") or "Kaynak bilinmiyor"
    publisher = citation.get("publisher") or source_name
    author = citation.get("author")
    published = citation.get("published_human") or humanize_time(citation.get("published_at") or article.get("published_at")) or "Tarih bilinmiyor"

    parts = [
        f'<a href="{html.escape(source_url)}">{html.escape(str(source_name))}</a>',
    ]
    if publisher and publisher != source_name:
        parts.append(f"Yayıncı: {html.escape(str(publisher))}")
    if author:
        parts.append(f"Yazar: {html.escape(str(author))}")
    if published:
        parts.append(html.escape(str(published)))

    meta = " · ".join(parts)
    return Markup(
        '<div class="citation">'
        f'{meta}<span class="trust-badge">{html.escape(str(trust_badge))}</span>'
        '</div>'
    )


def _trust_badge(score: Any) -> str:
    """Map numeric trust score to the Turkish badge label."""
    try:
        value = float(score)
    except (TypeError, ValueError):
        value = 0.5
    if value >= 0.8:
        return "güvenilir"
    if value >= 0.5:
        return "orta"
    return "düşük"


def _parse_datetime(value: Any) -> datetime | None:
    """Parse datetime, date, Arrow-supported strings, or return None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    try:
        return arrow.get(str(value)).datetime
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    """Convert a value to int or return None."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
