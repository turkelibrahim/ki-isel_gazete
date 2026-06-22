"""Text normalization helpers that preserve Turkish characters."""

from __future__ import annotations

import html
import re
import unicodedata

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_ALLOWED_RE = re.compile(r"[^0-9a-zA-ZçğıöşüÇĞİÖŞÜâîûÂÎÛ]+")


def strip_html(value: str | None) -> str:
    """Remove HTML tags and unescape entities without mutating Turkish letters."""
    if not value:
        return ""
    unescaped = html.unescape(str(value))
    return _TAG_RE.sub(" ", unescaped)


def normalize_text(value: str | None) -> str:
    """Normalize text for comparison while preserving Turkish characters."""
    if not value:
        return ""
    text = unicodedata.normalize("NFC", strip_html(value))
    text = text.replace("I", "ı").replace("İ", "i").lower()
    text = _ALLOWED_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def normalize_title(value: str | None) -> str:
    """Normalize titles for duplicate detection."""
    text = normalize_text(value)
    prefixes = ("son dakika", "breaking news", "canlı", "özel haber")
    for prefix in prefixes:
        if text.startswith(prefix + " "):
            text = text[len(prefix) + 1 :].strip()
    return text


def tokenize(value: str | None) -> list[str]:
    """Tokenize normalized text and drop tiny noise tokens."""
    normalized = normalize_text(value)
    return [token for token in normalized.split() if len(token) > 1 or token.isdigit()]


def shingle_tokens(value: str | None, n: int = 3) -> set[str]:
    """Return word shingles used by MinHash candidate generation."""
    tokens = tokenize(value)
    if not tokens:
        return set()
    if len(tokens) < n:
        return set(tokens)
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}
