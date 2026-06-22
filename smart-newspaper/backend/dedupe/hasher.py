"""Hashing and URL canonicalization utilities for exact duplicate detection."""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .text_cleaner import normalize_text, normalize_title

_TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "dclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "yclid",
    "msclkid",
    "spm",
    "utm",
    "ref",
    "ref_src",
    "rss",
    "output",
}


def canonicalize_url(url: str | None) -> str:
    """Canonicalize URLs by removing tracking parameters and fragments."""
    if not url:
        return ""
    raw = str(url).strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
        scheme = (parsed.scheme or "https").lower()
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/")
        clean_params: list[tuple[str, str]] = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=False):
            lower_key = key.lower()
            if lower_key.startswith("utm_") or lower_key in _TRACKING_KEYS:
                continue
            clean_params.append((key, value))
        query = urlencode(sorted(clean_params), doseq=True)
        return urlunsplit((scheme, netloc, path, query, ""))
    except Exception:
        return raw.split("#", 1)[0]


def sha256_hash(value: str | bytes | None) -> str:
    """Return a SHA-256 hex digest for stable exact duplicate checks."""
    data = value if isinstance(value, bytes) else str(value or "").encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def exact_article_hash(title: str | None, content: str | None, summary: str | None = None) -> str:
    """Hash normalized title and body; Turkish characters are preserved before hashing."""
    body = normalize_text(content or summary or "")
    normalized = f"{normalize_title(title)}\n{body}"
    return sha256_hash(normalized)


def article_content_hash(content: str | None, summary: str | None = None) -> str:
    """Hash only the article body for same-content/different-title detection."""
    return sha256_hash(normalize_text(content or summary or ""))
