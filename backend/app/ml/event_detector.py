"""Event detection with spaCy NER, regex dates, and event keyword matching."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

try:  # Optional dependency: keep backend import-safe when spaCy is not installed.
    import spacy  # type: ignore
except Exception:  # pragma: no cover - dependency may be absent in lightweight envs.
    spacy = None  # type: ignore

try:  # Optional dependency: preferred parser for Turkish relative dates.
    import dateparser  # type: ignore
except Exception:  # pragma: no cover - dependency may be absent in lightweight envs.
    dateparser = None  # type: ignore

from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

from app.ml.event_category_classifier import EventCategoryClassifier

EVENT_KW: list[str] = [
    "etkinlik",
    "toplantı",
    "seminer",
    "konferans",
    "webinar",
    "sınav",
    "başvuru",
    "son tarih",
    "deadline",
    "duyuru",
    "konser",
    "festival",
    "tören",
    "eğitim",
    "atölye",
]

TURKISH_WEEKDAYS: dict[str, int] = {
    "pazartesi": 0,
    "salı": 1,
    "sali": 1,
    "çarşamba": 2,
    "carsamba": 2,
    "perşembe": 3,
    "persembe": 3,
    "cuma": 4,
    "cumartesi": 5,
    "pazar": 6,
}

TURKISH_MONTHS: dict[str, int] = {
    "ocak": 1,
    "şubat": 2,
    "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "agustos": 8,
    "eylül": 9,
    "eylul": 9,
    "ekim": 10,
    "kasım": 11,
    "kasim": 11,
    "aralık": 12,
    "aralik": 12,
}

DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b"),
    re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b"),
    re.compile(
        r"\b\d{1,2}\s+(?:ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos|eylül|eylul|ekim|kasım|kasim|aralık|aralik)(?:['’]?(?:da|de|ta|te))?(?:\s+\d{4})?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:bugün|bugun|yarın|yarin)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:pazartesi|salı|sali|çarşamba|carsamba|perşembe|persembe|cuma|cumartesi|pazar)(?:\s+günü|\s+gunu)?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bsaat\s+\d{1,2}:\d{2}\b", re.IGNORECASE),
)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
TIME_RE = re.compile(r"\bsaat\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})\b", re.IGNORECASE)


class EventDetector:
    """Detect dated event candidates from Turkish news or announcement text.

    The detector combines three signals:
    1. spaCy DATE entities when a model is available.
    2. Regex/dateparser/dateutil based date extraction.
    3. Event-related keyword matching.

    A sentence becomes an event candidate only when it contains at least one
    parsable date signal and at least one event keyword.
    """

    _instance: "EventDetector | None" = None
    _initialized: bool = False

    def __new__(cls) -> "EventDetector":
        """Return a singleton detector instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Load spaCy once, falling back to regex-only mode when unavailable."""
        if self.__class__._initialized:
            return
        self.nlp = self._load_spacy_model()
        self.regex_only = self.nlp is None
        self.category_classifier = EventCategoryClassifier()
        self.__class__._initialized = True

    def _load_spacy_model(self) -> Any | None:
        """Load Turkish spaCy model, multilingual fallback, or return None."""
        if spacy is None:
            logger.warning("spaCy is not installed; EventDetector will run in regex-only mode.")
            return None

        for model_name in ("tr_core_news_sm", "xx_ent_wiki_sm"):
            try:
                return spacy.load(model_name)
            except Exception:
                logger.warning("spaCy model %s could not be loaded; trying fallback.", model_name)

        logger.warning("No spaCy NER model available; EventDetector will run in regex-only mode.")
        return None

    def split_sentences(self, text: str) -> list[str]:
        """Split text into sentence-like chunks with a lightweight regex."""
        if not text or not text.strip():
            return []
        return [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part and part.strip()]

    def has_event_keyword(self, sentence: str) -> bool:
        """Return True when an event keyword appears in the sentence."""
        return self._keyword_count(sentence) > 0

    def _keyword_count(self, sentence: str) -> int:
        """Count distinct event keywords present in a sentence."""
        normalized = sentence.lower()
        return sum(1 for keyword in EVENT_KW if keyword in normalized)

    def _extract_ner_date_texts(self, sentence: str) -> list[str]:
        """Extract DATE entity texts from spaCy when NER is available."""
        if self.nlp is None:
            return []
        try:
            doc = self.nlp(sentence)
            return [ent.text for ent in doc.ents if ent.label_.upper() == "DATE"]
        except Exception:
            logger.exception("spaCy DATE extraction failed for sentence: %s", sentence)
            return []

    def extract_dates(self, sentence: str) -> list[datetime]:
        """Extract parsed datetimes from supported regex and NER date formats."""
        dates: list[datetime] = []
        candidates: list[str] = []

        for pattern in DATE_PATTERNS:
            candidates.extend(match.group(0) for match in pattern.finditer(sentence))
        candidates.extend(self._extract_ner_date_texts(sentence))

        for candidate in dict.fromkeys(candidates):  # keep order, remove duplicates
            parsed = self._parse_date_candidate(candidate, sentence)
            if parsed is not None:
                dates.append(parsed)
            else:
                logger.warning("Event date candidate could not be parsed: %s", candidate)

        # If a date and an explicit time appear separately, apply the time to the first date.
        time_match = TIME_RE.search(sentence)
        if dates and time_match:
            hour = int(time_match.group("hour"))
            minute = int(time_match.group("minute"))
            dates[0] = dates[0].replace(hour=hour, minute=minute, second=0, microsecond=0)

        return dates

    def _parse_date_candidate(self, candidate: str, sentence: str) -> datetime | None:
        """Parse one date candidate using dateparser, manual Turkish fallbacks, then dateutil."""
        now = datetime.now(timezone.utc)
        normalized = candidate.strip().lower()

        manual = self._parse_manual_relative(normalized, now)
        if manual is not None:
            return manual

        manual_turkish_date = self._parse_turkish_day_month(normalized, now)
        if manual_turkish_date is not None:
            return manual_turkish_date

        if dateparser is not None:
            try:
                parsed = dateparser.parse(
                    candidate,
                    languages=["tr", "en"],
                    settings={
                        "RETURN_AS_TIMEZONE_AWARE": True,
                        "PREFER_DATES_FROM": "future",
                        "RELATIVE_BASE": now,
                    },
                )
                if parsed is not None:
                    return parsed
            except Exception:
                logger.warning("dateparser failed for candidate %s", candidate)

        try:
            parsed_dt = dateutil_parser.parse(candidate, dayfirst=True, fuzzy=True)
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
            return parsed_dt
        except Exception:
            # For a pure time match such as "saat 14:00", use today's date.
            time_match = TIME_RE.search(sentence)
            if time_match and candidate.lower().startswith("saat"):
                return now.replace(
                    hour=int(time_match.group("hour")),
                    minute=int(time_match.group("minute")),
                    second=0,
                    microsecond=0,
                )
            return None


    def _parse_turkish_day_month(self, normalized: str, now: datetime) -> datetime | None:
        """Parse Turkish day-month expressions such as ``21 Haziran’da``."""
        cleaned = normalized.replace("’", "'")
        cleaned = re.sub(r"'(?:da|de|ta|te)$", "", cleaned)
        match = re.match(
            r"^(?P<day>\d{1,2})\s+(?P<month>[a-zçğıöşü]+)(?:\s+(?P<year>\d{4}))?$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        month_name = match.group("month").lower()
        month = TURKISH_MONTHS.get(month_name)
        if month is None:
            return None

        day = int(match.group("day"))
        year = int(match.group("year") or now.year)
        try:
            parsed = datetime(year, month, day, tzinfo=now.tzinfo)
            if match.group("year") is None and parsed < now.replace(hour=0, minute=0, second=0, microsecond=0):
                parsed = datetime(year + 1, month, day, tzinfo=now.tzinfo)
            return parsed
        except ValueError:
            return None

    def _parse_manual_relative(self, normalized: str, now: datetime) -> datetime | None:
        """Parse Turkish relative date words without external models."""
        if normalized in {"bugün", "bugun"}:
            return now
        if normalized in {"yarın", "yarin"}:
            return now + timedelta(days=1)

        weekday_key = normalized.replace(" günü", "").replace(" gunu", "").strip()
        if weekday_key in TURKISH_WEEKDAYS:
            target = TURKISH_WEEKDAYS[weekday_key]
            delta = (target - now.weekday()) % 7
            if delta == 0:
                delta = 7
            return now + timedelta(days=delta)
        return None

    def calculate_confidence(self, sentence: str, keyword_count: int, has_ner_date: bool) -> float:
        """Calculate confidence according to keyword/date evidence strength."""
        confidence = 0.85 if keyword_count > 1 else 0.65

        # The prompt asks for +0.05 when NER DATE and regex date both exist.
        if has_ner_date and self._has_regex_date(sentence):
            confidence += 0.05

        return min(confidence, 0.95)

    def _has_regex_date(self, sentence: str) -> bool:
        """Return True when one of the explicit regex patterns matches."""
        return any(pattern.search(sentence) for pattern in DATE_PATTERNS)

    def detect_events(self, text: str) -> list[dict[str, Any]]:
        """Detect event candidates from text.

        Returns a list of dictionaries with title, description, event_date,
        raw_sentence, confidence, and category. Sentences that contain only a date or only
        an event keyword are intentionally ignored to reduce false positives.
        """
        events: list[dict[str, Any]] = []
        for sentence in self.split_sentences(text):
            try:
                keyword_count = self._keyword_count(sentence)
                if keyword_count == 0:
                    continue

                dates = self.extract_dates(sentence)
                if not dates:
                    continue

                has_ner_date = bool(self._extract_ner_date_texts(sentence))
                confidence = self.calculate_confidence(sentence, keyword_count, has_ner_date)
                title = self._build_title(sentence)
                category_result = self.category_classifier.classify(sentence)

                events.append(
                    {
                        "title": title,
                        "description": sentence,
                        "event_date": dates[0].isoformat(),
                        "raw_sentence": sentence,
                        "confidence": confidence,
                        "category": category_result["category"],
                        "category_score": category_result["score"],
                        "matched_category_keywords": category_result["matched_keywords"],
                        "category_scores": category_result["all_scores"],
                    }
                )
            except Exception:
                logger.exception("Event detection failed for sentence: %s", sentence)
                continue
        return events

    def _build_title(self, sentence: str, max_chars: int = 100) -> str:
        """Build a compact event title from the original sentence."""
        cleaned = re.sub(r"\s+", " ", sentence).strip()
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max_chars - 1].rstrip() + "…"
