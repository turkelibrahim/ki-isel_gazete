"""Dedupe helpers for multilingual articles."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import RawArticle

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "ref", "source"}


def canonicalize_url(url: str) -> str:
    """Remove tracking parameters and normalize URL."""
    try:
        parts = urlsplit(url or "")
        query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k not in TRACKING_PARAMS])
        path = parts.path.rstrip("/")
        return urlunsplit(("https", parts.netloc.lower(), path, query, "")).lower()
    except Exception:
        return (url or "").strip().lower()


def normalize_title(title: str) -> str:
    """Normalize title while preserving Turkish characters."""
    value = (title or "").lower()
    value = re.sub(r"\b(son dakika|breaking|özel haber|canlı|video)\b", " ", value)
    value = re.sub(r"[^\w\sçğıöşüÇĞİÖŞÜ]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def build_dedupe_key(raw: RawArticle, lang: str) -> str:
    """Build deterministic dedupe key from normalized title, language and day."""
    date = raw.published_at or raw.fetched_at or datetime.utcnow()
    day = date.date().isoformat()
    base = f"{normalize_title(raw.title)}|{lang}|{day}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:24]


def title_similarity(a: str, b: str) -> float:
    """Compute simple Jaccard title similarity."""
    sa = set(normalize_title(a).split())
    sb = set(normalize_title(b).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)
