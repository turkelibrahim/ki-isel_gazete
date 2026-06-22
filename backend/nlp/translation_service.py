"""Translation field preparation with provider-safe fallback."""
from __future__ import annotations

import os
from .models import RawArticle, TranslationResult


def prepare_translation_fields(raw: RawArticle, original_lang: str) -> TranslationResult:
    """Prepare TR/EN display fields without requiring an external provider."""
    title = raw.title or ""
    content = raw.content or raw.summary or ""
    enabled = os.getenv("TRANSLATION_ENABLED", "false").lower() == "true"
    if original_lang == "tr":
        return TranslationResult("tr", title, content, title, content, None, None, "prepared", None, None)
    if original_lang == "en":
        return TranslationResult("en", title, content, None if not enabled else None, None if not enabled else None, title, content, "skipped" if not enabled else "queued", None, None)
    return TranslationResult(original_lang or "unknown", title, content, None, None, None, None, "skipped", None, None)
