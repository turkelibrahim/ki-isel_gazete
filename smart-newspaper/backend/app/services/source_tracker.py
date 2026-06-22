"""Source metadata extraction and citation helpers.

The extractor follows a defensive priority chain because each publisher may use
Open Graph, Twitter, Dublin Core, HTML time tags, or only a bare URL. It never
raises for malformed HTML; callers receive safe fallback values instead.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import arrow
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)

PUBLISHER_TAGS = [
    "og:site_name",
    "article:publisher",
    "twitter:site",
    "application-name",
]

DATE_TAGS = [
    "article:published_time",
    "article:modified_time",
    "og:updated_time",
    "DC.Date",
]

AUTHOR_TAGS = [
    "author",
    "article:author",
    "DC.Creator",
    "byline",
]


class MetadataExtractor:
    """Extract publisher, publication date, author, and trust badge metadata."""

    def extract(self, html: str, url: str) -> dict[str, Any]:
        """Extract citation metadata from HTML and URL fallback values.

        Args:
            html: Raw HTML string. Plain text is accepted and simply yields
                fallback metadata.
            url: Article URL used as the publisher fallback.

        Returns:
            A dictionary with publisher, author, published_at and
            published_human keys.
        """
        soup = BeautifulSoup(html or "", "html.parser")
        published_at = self._extract_published_at(soup)
        return {
            "publisher": self._extract_publisher(soup, url),
            "author": self._extract_author(soup),
            "published_at": published_at,
            "published_human": self.humanize_date(published_at),
        }

    def _extract_publisher(self, soup: BeautifulSoup, url: str) -> str:
        """Extract publisher using the configured meta tag priority chain."""
        for tag in PUBLISHER_TAGS:
            content = self._find_meta_content(soup, tag)
            if content:
                return self._clean_text(content)
        return self._publisher_from_url(url)

    def _extract_published_at(self, soup: BeautifulSoup) -> datetime | None:
        """Extract and parse publication date from meta tags or <time>."""
        for tag in DATE_TAGS:
            content = self._find_meta_content(soup, tag)
            parsed = self._parse_datetime(content)
            if parsed is not None:
                return parsed

        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag is not None:
            parsed = self._parse_datetime(str(time_tag.get("datetime", "")))
            if parsed is not None:
                return parsed
        return None

    def _extract_author(self, soup: BeautifulSoup) -> str | None:
        """Extract author or byline metadata from common tags."""
        for tag in AUTHOR_TAGS:
            content = self._find_meta_content(soup, tag)
            if content:
                return self._clean_text(content)

        byline = soup.select_one(".byline, .author, [rel='author']")
        if byline is not None:
            text = self._clean_text(byline.get_text(" ", strip=True))
            return text or None
        return None

    def _find_meta_content(self, soup: BeautifulSoup, tag: str) -> str | None:
        """Find a meta tag by property first, then by name."""
        meta = soup.find("meta", property=tag) or soup.find("meta", attrs={"name": tag})
        if meta is None:
            return None
        content = meta.get("content")
        if content is None:
            return None
        cleaned = self._clean_text(str(content))
        return cleaned or None

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse a datetime string with dateutil without throwing outward."""
        if not value:
            return None
        try:
            return date_parser.parse(value)
        except (TypeError, ValueError, OverflowError) as exc:
            logger.warning("Could not parse publication date %r: %s", value, exc)
            return None

    def humanize_date(self, published_at: datetime | None) -> str | None:
        """Return a Turkish human-readable relative date such as '3 saat önce'."""
        if published_at is None:
            return None
        try:
            return arrow.get(published_at).humanize(locale="tr")
        except Exception as exc:  # pragma: no cover - arrow locale/runtime guard
            logger.warning("Could not humanize publication date %r: %s", published_at, exc)
            return None

    def trust_badge(self, trust_score: float | None) -> str:
        """Map a numeric source trust score to the Turkish badge label."""
        score = float(trust_score or 0.0)
        if score >= 0.8:
            return "güvenilir"
        if score >= 0.5:
            return "orta"
        return "düşük"

    def _publisher_from_url(self, url: str) -> str:
        """Build a safe publisher fallback from the URL domain."""
        try:
            netloc = urlparse(url).netloc or urlparse(f"https://{url}").netloc
            domain = netloc.replace("www.", "").split(".")[0]
            return domain.capitalize() if domain else "Unknown"
        except Exception as exc:  # pragma: no cover - defensive URL fallback
            logger.warning("Could not derive publisher from URL %r: %s", url, exc)
            return "Unknown"

    def _clean_text(self, value: str) -> str:
        """Normalize whitespace and trim text values."""
        return " ".join(value.split()).strip()
