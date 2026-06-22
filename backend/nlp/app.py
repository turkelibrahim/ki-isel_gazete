"""Tiny optional NLP worker entrypoint for local processing."""
from __future__ import annotations

from datetime import datetime
from .language_processor import process_article
from .models import RawArticle


def process_payload(payload: dict) -> dict:
    """Process a JSON-like article payload."""
    raw = RawArticle(
        id=str(payload.get("id") or payload.get("url") or "article"),
        title=payload.get("title") or "",
        content=payload.get("content") or payload.get("fullText") or payload.get("summary") or "",
        summary=payload.get("summary"),
        source_name=payload.get("source_name") or payload.get("sourceName") or payload.get("source") or "",
        source_url=payload.get("source_url") or payload.get("url") or "",
        source_logo=payload.get("source_logo") or payload.get("sourceIcon"),
        category=payload.get("category"),
        country=payload.get("country"),
        city=payload.get("city"),
        fetched_at=datetime.utcnow(),
    )
    return process_article(raw).to_dict()
