"""Multilingual language detection and pipeline orchestration."""
from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha1

from .models import DetectionResult, ProcessedArticle, RawArticle, TranslationResult
from .pipelines import english, generic, turkish
from .dedupe_service import build_dedupe_key, normalize_title
from .newspaper_formatter import format_for_newspaper
from .translation_service import prepare_translation_fields

LOGGER = logging.getLogger(__name__)
CONFIDENCE_THRESHOLD = float(os.getenv("NLP_CONFIDENCE_THRESHOLD", "0.85"))
MIN_TEXT_LENGTH = int(os.getenv("NLP_MIN_TEXT_LENGTH", "20"))
MAX_WORKERS = int(os.getenv("NLP_MAX_WORKERS", "4"))
PIPELINE_MAP = {"tr": "turkish", "en": "english", "de": "generic", "fr": "generic", "ar": "generic", "es": "generic", "ru": "generic"}
_CACHE: dict[str, ProcessedArticle] = {}

try:
    from langdetect import DetectorFactory, detect_langs  # type: ignore
    DetectorFactory.seed = 0
except Exception:  # pragma: no cover - optional dependency
    detect_langs = None

try:
    import langid  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    langid = None


def _clean_detection_text(text: str) -> str:
    """Clean text for language detection while preserving Unicode letters."""
    value = re.sub(r"https?://\S+|www\.\S+", " ", text or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\d+", " ", value)
    value = re.sub(r"[\U0001F300-\U0001FAFF]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def detect_language(text: str) -> DetectionResult:
    """Detect language using langdetect with langid fallback and deterministic output."""
    cleaned = _clean_detection_text(text)
    if len(cleaned) < MIN_TEXT_LENGTH:
        return DetectionResult("unknown", 0.0, False, False, [])
    candidates: list[dict] = []
    try:
        if detect_langs:
            langs = detect_langs(cleaned[:1200])
            candidates = [{"lang": item.lang, "prob": float(item.prob)} for item in langs]
            if candidates and candidates[0]["prob"] >= CONFIDENCE_THRESHOLD:
                return DetectionResult(candidates[0]["lang"], candidates[0]["prob"], True, False, candidates)
    except Exception as exc:
        LOGGER.warning("langdetect failed: %s", exc)

    try:
        if langid:
            lang, score = langid.classify(cleaned[:1200])
            prob = min(0.99, max(0.0, (float(score) + 100.0) / 100.0))
            if candidates and candidates[0]["lang"] == lang:
                return DetectionResult(lang, max(candidates[0]["prob"], prob), True, True, candidates)
            return DetectionResult(lang if prob >= CONFIDENCE_THRESHOLD else "unknown", prob, prob >= CONFIDENCE_THRESHOLD, True, candidates)
    except Exception as exc:
        LOGGER.warning("langid fallback failed: %s", exc)

    # Heuristic fallback for environments without optional packages.
    lower = cleaned.lower()
    if re.search(r"[çğıöşüİÇĞÖŞÜ]", cleaned) or any(w in f" {lower} " for w in [" ve ", " için ", " haber ", " türkiye "]):
        return DetectionResult("tr", 0.88, True, True, [{"lang": "tr", "prob": 0.88}])
    if any(w in f" {lower} " for w in [" the ", " and ", " with ", " from "]):
        return DetectionResult("en", 0.88, True, True, [{"lang": "en", "prob": 0.88}])
    return DetectionResult("unknown", 0.0, False, True, candidates)


def choose_pipeline(detection: DetectionResult) -> str:
    """Choose turkish, english or generic pipeline."""
    if not detection.is_reliable:
        return "generic"
    return PIPELINE_MAP.get(detection.detected_lang, "generic")


def _run_pipeline(name: str, text: str) -> dict:
    """Run selected pipeline safely."""
    if name == "turkish":
        return turkish.process(text)
    if name == "english":
        return english.process(text)
    return generic.process(text)


def process_article(raw: RawArticle) -> ProcessedArticle:
    """Process one article end-to-end without losing the raw article."""
    text = "\n".join([raw.title or "", raw.summary or "", raw.content or ""])
    cache_key = sha1(f"{raw.id}|{text[:1500]}".encode("utf-8")).hexdigest()
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    started = time.perf_counter()
    try:
        detection = detect_language(text)
        pipeline_name = choose_pipeline(detection)
        pipe_result = _run_pipeline(pipeline_name, text)
        translation = prepare_translation_fields(raw, detection.detected_lang)
        normalized = normalize_title(raw.title)
        dedupe = build_dedupe_key(raw, detection.detected_lang)
        newspaper = format_for_newspaper(raw, pipe_result.get("keywords", []))
        processed = ProcessedArticle(
            raw=raw,
            detection=detection,
            translation=translation,
            pipeline_name=pipeline_name,
            tokens=pipe_result.get("tokens", []),
            lemmas=pipe_result.get("lemmas", []),
            entities=pipe_result.get("entities", []),
            keywords=pipe_result.get("keywords", []),
            cleaned_text=pipe_result.get("cleaned_text", text),
            normalized_title=normalized,
            dedupe_key=dedupe,
            cluster_id=f"cluster_{dedupe[:14]}",
            processing_status=pipe_result.get("status", "partial"),
            error_message=None,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        LOGGER.info("article_id=%s source=%s lang=%s pipeline=%s status=%s duration_ms=%s newspaper_title=%s", raw.id, raw.source_name, detection.detected_lang, pipeline_name, processed.processing_status, elapsed_ms, newspaper.get("newspaper_title"))
        _CACHE[cache_key] = processed
        if len(_CACHE) > 1000:
            _CACHE.pop(next(iter(_CACHE)))
        return processed
    except Exception as exc:
        LOGGER.error("article processing failed article_id=%s error=%s", raw.id, exc)
        detection = DetectionResult("unknown", 0.0, False, True, [])
        return ProcessedArticle(raw, detection, None, "generic", [], [], [], [], text, normalize_title(raw.title), build_dedupe_key(raw, "unknown"), None, "failed", str(exc))


def process_batch(articles: list[RawArticle]) -> list[ProcessedArticle]:
    """Process a batch with bounded ThreadPoolExecutor."""
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_article, article) for article in articles]
        return [future.result() for future in as_completed(futures)]


def cache_size() -> int:
    """Return current processing cache size."""
    return len(_CACHE)
