"""Citation builder for personal newspaper layouts and APIs."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterable

import arrow

logger = logging.getLogger(__name__)


class CitationService:
    """Build source/citation metadata for article rows used in newspaper HTML."""

    def build_article_citation(self, article: Any) -> dict[str, Any]:
        """Build a citation dictionary for a single article-like object.

        Args:
            article: SQLAlchemy Article row, dictionary, or serialized article
                object. Source data can be attached as ``article.source`` or
                flattened via ``source_name``, ``source_url`` and
                ``source_trust_score`` keys.

        Returns:
            Citation metadata with source name, source URL, article URL,
            publication time, trust badge, and a user-facing citation string.
        """
        try:
            article_id = self._safe_int(self._get(article, "article_id", self._get(article, "id")))
            source = self._get(article, "source")
            source_name = (
                self._get(article, "source_name")
                or self._get(source, "name")
                or self._domain_fallback(self._get(article, "url") or self._get(article, "article_url"))
                or "Kaynak bilinmiyor"
            )
            source_url = (
                self._get(article, "source_url")
                or self._get(source, "base_url")
                or self._get(source, "url")
                or "#"
            )
            article_url = self._get(article, "article_url") or self._get(article, "url") or "#"
            published_at_raw = self._get(article, "published_at")
            published_human = self._humanize_published_at(published_at_raw)
            trust_score = self._safe_float(
                self._get(article, "trust_score", self._get(article, "source_trust_score", self._get(source, "trust_score"))),
                default=0.5,
            )
            trust_badge = self._trust_badge(trust_score)
            citation_text = f"{source_name} · {published_human} · Güven: {trust_badge}"
            return {
                "article_id": article_id,
                "source_name": source_name,
                "source_url": source_url or "#",
                "article_url": article_url or "#",
                "published_at": self._serialize_datetime(published_at_raw),
                "published_human": published_human,
                "trust_score": trust_score,
                "trust_badge": trust_badge,
                "citation_text": citation_text,
            }
        except Exception:
            logger.exception("Could not build citation for article=%r", article)
            return {
                "article_id": None,
                "source_name": "Kaynak bilinmiyor",
                "source_url": "#",
                "article_url": "#",
                "published_at": None,
                "published_human": "Tarih bilinmiyor",
                "trust_score": 0.5,
                "trust_badge": "orta",
                "citation_text": "Kaynak bilinmiyor · Tarih bilinmiyor · Güven: orta",
            }

    def build_citations(self, articles: Iterable[Any]) -> dict[int, dict[str, Any]]:
        """Build an article_id keyed citation dictionary for many articles."""
        citations: dict[int, dict[str, Any]] = {}
        for article in articles:
            citation = self.build_article_citation(article)
            article_id = self._safe_int(citation.get("article_id"))
            if article_id is not None:
                citations[article_id] = citation
        return citations

    def _humanize_published_at(self, value: Any) -> str:
        """Humanize publication time in Turkish or return a safe fallback."""
        if value is None:
            return "Tarih bilinmiyor"
        try:
            return arrow.get(value).humanize(locale="tr")
        except Exception:
            logger.warning("Could not humanize published_at=%r", value, exc_info=True)
            return "Tarih bilinmiyor"

    def _trust_badge(self, trust_score: float | None) -> str:
        """Map source trust score to a Turkish badge label."""
        score = self._safe_float(trust_score, default=0.5)
        if score >= 0.8:
            return "güvenilir"
        if score >= 0.5:
            return "orta"
        return "düşük"

    def _serialize_datetime(self, value: Any) -> str | None:
        """Serialize datetime-like values for API responses."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    def _domain_fallback(self, url: Any) -> str | None:
        """Return a simple publisher fallback from an article URL."""
        if not url:
            return None
        try:
            from urllib.parse import urlparse

            parsed = urlparse(str(url))
            netloc = parsed.netloc or urlparse(f"https://{url}").netloc
            domain = netloc.replace("www.", "").split(".")[0]
            return domain.capitalize() if domain else None
        except Exception:
            logger.warning("Could not derive source fallback from url=%r", url, exc_info=True)
            return None

    def _get(self, obj: Any, key: str, default: Any = None) -> Any:
        """Read a field from a dict or object safely."""
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _safe_int(self, value: Any) -> int | None:
        """Convert a value to int or return None."""
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _safe_float(self, value: Any, *, default: float) -> float:
        """Convert a value to float or return a default."""
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default
