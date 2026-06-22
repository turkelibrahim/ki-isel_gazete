"""Deterministic article language detection service."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

try:
    from langdetect import DetectorFactory, LangDetectException, detect_langs
except ImportError:  # Keeps the app importable before ``pip install langdetect``.
    DetectorFactory = None  # type: ignore[assignment]
    LangDetectException = Exception  # type: ignore[assignment]
    detect_langs = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

if DetectorFactory is not None:
    DetectorFactory.seed = 42

MIN_CHARS = 20
SUPPORTED = ["tr", "en", "de", "fr", "ar", "ru"]


class LanguageDetector:
    """Singleton wrapper around langdetect's N-gram based detector."""

    _instance: ClassVar["LanguageDetector | None"] = None

    def __new__(cls) -> "LanguageDetector":
        """Return a single detector instance for the process."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def detect(self, text: str) -> tuple[str, float]:
        """Detect language from the first 500 characters of text.

        Returns:
            A ``(language_code, confidence)`` tuple. Language codes outside the
            supported list are normalized to ``other``. Very short or invalid
            input returns ``("unknown", 0.0)``.
        """
        sample = (text or "").strip()[:500]
        if len(sample) < MIN_CHARS:
            return ("unknown", 0.0)

        if detect_langs is None:
            logger.warning("langdetect is not installed; returning unknown language")
            return ("unknown", 0.0)

        try:
            candidates: list[Any] = detect_langs(sample)
            if not candidates:
                return ("unknown", 0.0)

            best = candidates[0]
            lang = str(best.lang)
            prob = float(best.prob)
            if lang not in SUPPORTED:
                return ("other", prob)
            return (lang, prob)
        except (LangDetectException, Exception) as exc:
            logger.warning("Language detection failed: %s", exc)
            return ("unknown", 0.0)
