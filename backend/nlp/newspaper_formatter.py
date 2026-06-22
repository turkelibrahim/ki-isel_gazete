"""Formatter for e-gazete/PDF friendly article fields."""
from __future__ import annotations

from .models import RawArticle


def _shorten(text: str, limit: int) -> str:
    value = " ".join((text or "").split())
    return value if len(value) <= limit else value[:limit].rsplit(" ", 1)[0] + "..."


def format_for_newspaper(raw: RawArticle, keywords: list[str] | None = None) -> dict:
    """Create clean newspaper display fields."""
    keywords = keywords or []
    title = _shorten(raw.title, 120) or "Başlıksız Haber"
    summary = _shorten(raw.summary or raw.content or title, 360)
    importance = min(0.99, 0.35 + min(0.25, len(keywords) * 0.025) + (0.1 if raw.source_logo else 0))
    return {
        "newspaper_title": title,
        "newspaper_summary": summary,
        "newspaper_excerpt": _shorten(summary, 180),
        "reading_lang": "tr",
        "page_category": raw.category or "Gündem",
        "importance_score": round(importance, 3),
    }
