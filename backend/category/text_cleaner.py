"""Text cleaning helpers that preserve Turkish characters."""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Iterable, List

HTML_TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
TOKEN_RE = re.compile(r"[0-9A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+", re.UNICODE)

TR_HINTS = {"ve", "bir", "için", "türkiye", "açıklama", "son", "dakika", "bakan", "dolar"}
EN_HINTS = {"the", "and", "for", "with", "from", "government", "market", "president", "company"}

TR_STOPWORDS = {
    "ve", "ile", "bir", "bu", "şu", "o", "da", "de", "ki", "için", "olan", "olarak", "gibi",
    "daha", "çok", "az", "son", "yeni", "haber", "göre", "ise", "ama", "fakat", "ancak",
}
EN_STOPWORDS = {
    "the", "and", "or", "for", "with", "from", "this", "that", "are", "was", "were", "has", "have",
    "had", "will", "would", "about", "after", "before", "into", "over", "under", "news",
}


def strip_html(value: str) -> str:
    """Remove HTML tags and decode HTML entities."""

    return HTML_TAG_RE.sub(" ", html.unescape(str(value or "")))


def normalize_text(value: str) -> str:
    """Normalize text for matching without corrupting Turkish characters."""

    cleaned = strip_html(value)
    cleaned = URL_RE.sub(" ", cleaned)
    cleaned = unicodedata.normalize("NFC", cleaned)
    cleaned = cleaned.replace("I", "ı").replace("İ", "i")
    cleaned = cleaned.lower()
    cleaned = re.sub(r"[^0-9a-zçğıöşüâîû\s]+", " ", cleaned, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


def tokenize(value: str, *, remove_stopwords: bool = True) -> List[str]:
    """Tokenize Turkish/English text into normalized words."""

    tokens = TOKEN_RE.findall(normalize_text(value))
    if not remove_stopwords:
        return tokens
    stopwords = TR_STOPWORDS | EN_STOPWORDS
    return [token for token in tokens if len(token) >= 2 and token not in stopwords]


def detect_language(value: str, fallback: str = "unknown") -> str:
    """Detect whether the article is Turkish or English using lightweight signals."""

    normalized = normalize_text(value)
    if not normalized:
        return fallback
    tokens = normalized.split()
    tr_chars = sum(1 for char in value if char in "çğıİöşüÇĞÖŞÜ")
    tr_score = tr_chars * 2 + sum(1 for token in tokens if token in TR_HINTS)
    en_score = sum(1 for token in tokens if token in EN_HINTS)
    if tr_score >= 2:
        return "tr"
    if en_score >= 2 or (len(tokens) >= 8 and tr_chars == 0):
        return "en"
    return fallback


def contains_phrase(text: str, phrases: Iterable[str]) -> List[str]:
    """Return matching normalized phrases from a normalized text."""

    normalized = normalize_text(text)
    return [phrase for phrase in phrases if normalize_text(phrase) and normalize_text(phrase) in normalized]
