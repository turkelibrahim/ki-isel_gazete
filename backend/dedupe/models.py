"""Typed data models used by the SmartNewspaper deduplication pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return default


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    """Parse RSS/API datetime values without throwing on malformed input."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@dataclass(slots=True)
class RawNewsArticle:
    """Normalized input article accepted from RSS, API or local database records."""

    id: str
    title: str = ""
    content: str = ""
    summary: str = ""
    source_name: str = ""
    source_logo: str = ""
    source_url: str = ""
    url: str = ""
    published_at: str = ""
    category: str = ""
    region: str = ""
    language: str = ""
    trust_score: float = 50.0
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RawNewsArticle":
        """Build a ``RawNewsArticle`` from the mixed camelCase/snake_case project shape."""
        source_url = str(_first(payload, "source_url", "sourceUrl", "url", "link", default="") or "")
        article_id = str(_first(payload, "id", "article_id", "articleId", default=source_url or _first(payload, "title", default="")) or "")
        title = str(_first(payload, "title", "displayTitle", "translatedTitle", "originalTitle", default="") or "")
        content = str(_first(payload, "content", "fullText", "description", "displayContent", "translatedContent", "originalContent", default="") or "")
        summary = str(_first(payload, "summary", "description", "displaySummary", "translatedSummary", "originalSummary", default="") or "")
        return cls(
            id=article_id,
            title=title,
            content=content,
            summary=summary,
            source_name=str(_first(payload, "source_name", "sourceName", "source", default="Kaynak") or "Kaynak"),
            source_logo=str(_first(payload, "source_logo", "sourceLogo", "sourceIcon", "icon", default="") or ""),
            source_url=source_url,
            url=str(_first(payload, "url", "link", default=source_url) or source_url),
            published_at=str(_first(payload, "published_at", "publishedAt", "date", default="") or ""),
            category=str(_first(payload, "category", default="") or ""),
            region=str(_first(payload, "region", "sourceRegion", "detectedEventRegion", default="") or ""),
            language=str(_first(payload, "language", "originalLanguage", default="") or ""),
            trust_score=float(_first(payload, "trust_score", "trustScore", "sourceTrustScore", default=50.0) or 50.0),
            raw=dict(payload),
        )

    @property
    def body_text(self) -> str:
        """Return the strongest available article body text."""
        return self.content or self.summary or ""

    @property
    def parsed_published_at(self) -> datetime | None:
        """Return parsed publication time when available."""
        return _parse_datetime(self.published_at)


@dataclass(slots=True)
class SourceVersion:
    """A single source's version of the same clustered news story."""

    article_id: str
    source_name: str
    source_logo: str
    source_url: str
    title: str
    published_at: str
    summary: str = ""
    duplicate_score: float = 1.0
    dedupe_status: str = "main"
    additional_info: str = ""

    @classmethod
    def from_article(
        cls,
        article: RawNewsArticle,
        *,
        duplicate_score: float = 1.0,
        dedupe_status: str = "main",
        additional_info: str = "",
    ) -> "SourceVersion":
        """Create a card-friendly source version from a raw article."""
        return cls(
            article_id=str(article.id),
            source_name=article.source_name or "Kaynak",
            source_logo=article.source_logo,
            source_url=article.source_url or article.url,
            title=article.title,
            published_at=article.published_at,
            summary=article.summary or article.content[:260],
            duplicate_score=round(float(duplicate_score), 4),
            dedupe_status=dedupe_status,
            additional_info=additional_info,
        )

    def to_payload(self) -> dict[str, Any]:
        """Return both snake_case and legacy camelCase fields expected by the UI."""
        return {
            "article_id": self.article_id,
            "articleId": self.article_id,
            "id": self.article_id,
            "source_name": self.source_name,
            "sourceName": self.source_name,
            "source": self.source_name,
            "source_logo": self.source_logo,
            "sourceLogo": self.source_logo,
            "sourceIcon": self.source_logo,
            "icon": self.source_logo,
            "source_url": self.source_url,
            "sourceUrl": self.source_url,
            "url": self.source_url,
            "title": self.title,
            "published_at": self.published_at,
            "publishedAt": self.published_at,
            "summary": self.summary,
            "duplicate_score": self.duplicate_score,
            "duplicateScore": self.duplicate_score,
            "dedupe_status": self.dedupe_status,
            "dedupeStatus": self.dedupe_status,
            "additional_info": self.additional_info,
            "additionalInfo": self.additional_info,
        }


@dataclass(slots=True)
class ClusteredNewsArticle:
    """A duplicate-free news story with all source versions preserved."""

    cluster_id: str
    main_article: RawNewsArticle
    sources: list[SourceVersion]
    duplicate_score: float = 0.0
    dedupe_status: str = "unique"
    additional_source_info: list[dict[str, str]] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        """Return the API payload used by /api/feed and card rendering."""
        source_payload = [source.to_payload() for source in self.sources]
        main = dict(self.main_article.raw) if self.main_article.raw else {}
        main.update(
            {
                "id": self.main_article.id,
                "title": self.main_article.title,
                "summary": self.main_article.summary,
                "fullText": self.main_article.content or self.main_article.summary,
                "sourceName": self.main_article.source_name,
                "sourceUrl": self.main_article.source_url or self.main_article.url,
                "publishedAt": self.main_article.published_at,
                "category": self.main_article.category,
            }
        )
        main["cluster_id"] = self.cluster_id
        main["clusterId"] = self.cluster_id
        main["main_article"] = main.copy()
        main["mainArticle"] = main["main_article"]
        main["mainArticleId"] = self.main_article.id
        main["main_article_id"] = self.main_article.id
        main["source_count"] = len(source_payload)
        main["sourceCount"] = len(source_payload)
        main["sources"] = source_payload
        main["duplicate_score"] = round(float(self.duplicate_score), 4)
        main["duplicateScore"] = round(float(self.duplicate_score), 4)
        main["dedupe_status"] = self.dedupe_status
        main["dedupeStatus"] = self.dedupe_status
        main["additional_source_info"] = self.additional_source_info
        main["additionalSourceInfo"] = self.additional_source_info
        return main
