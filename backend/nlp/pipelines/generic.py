"""Generic fallback NLP pipeline that never depends on heavy models."""
from __future__ import annotations

import re
from collections import Counter

GENERIC_STOPWORDS = {"the", "and", "or", "for", "with", "from", "bir", "ve", "ile", "için"}


def clean_text(text: str) -> str:
    """Strip html-like tags and normalize whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def tokenize(text: str) -> list[str]:
    """Tokenize while preserving Turkish/Unicode letters."""
    cleaned = re.sub(r"[^\w\sçğıöşüÇĞİÖŞÜ]", " ", clean_text(text).lower(), flags=re.UNICODE)
    return [t for t in cleaned.split() if len(t) >= 2 and t not in GENERIC_STOPWORDS]


def extract_keywords(tokens: list[str], limit: int = 12) -> list[str]:
    """Return most frequent keywords."""
    return [item for item, _ in Counter(tokens).most_common(limit)]


def extract_entities(text: str) -> list[dict]:
    """Extract simple capitalized entity candidates."""
    matches = re.findall(r"\b[A-ZÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ]+(?:\s+[A-ZÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ]+)?", text or "")
    return [{"text": m, "label": "ENTITY"} for m in dict.fromkeys(matches).keys()][:20]


def process(text: str) -> dict:
    """Process text with dependency-free fallback logic."""
    tokens = tokenize(text)
    return {
        "tokens": tokens,
        "lemmas": [],
        "entities": extract_entities(text),
        "keywords": extract_keywords(tokens),
        "cleaned_text": clean_text(text),
        "status": "partial",
    }
