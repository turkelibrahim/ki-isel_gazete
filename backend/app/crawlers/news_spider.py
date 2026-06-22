"""Generic BeautifulSoup based news spider."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)

ARTICLE_SELECTORS = "article, .article, .news-item, .news-card, .post, .entry, li"
TITLE_SELECTORS = "h1, h2, h3, .title, .headline, .entry-title"
CONTENT_SELECTORS = "p, .summary, .description, .excerpt, .spot"
DATE_SELECTORS = "time, .date, .published, .published-at, .time"


class NewsSpider(BaseSpider):
    """Generic spider for common article-card HTML structures."""

    def parse(self, html: str, url: str) -> list[dict[str, Any]]:
        """Parse article cards from a news listing page."""
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(ARTICLE_SELECTORS)
        articles: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for item in items:
            if not isinstance(item, Tag):
                continue

            title = self._extract_title(item)
            article_url = self._extract_url(item, url)

            if not title or not article_url:
                continue
            if article_url in seen_urls:
                continue

            content = self._extract_content(item)
            published_at = self._extract_published_at(item)

            seen_urls.add(article_url)
            articles.append(
                {
                    "title": title,
                    "content": content,
                    "url": article_url,
                    "source_id": self.source_id,
                    "published_at": published_at,
                }
            )

        logger.info("Parsed %s articles from %s source_id=%s", len(articles), url, self.source_id)
        return articles

    def _extract_title(self, item: Tag) -> str | None:
        """Extract a required title from a card."""
        title_tag = item.select_one(TITLE_SELECTORS)
        if title_tag is None:
            return None
        title = title_tag.get_text(" ", strip=True)
        return title or None

    def _extract_content(self, item: Tag) -> str:
        """Extract optional summary/content text from a card."""
        content_parts = [tag.get_text(" ", strip=True) for tag in item.select(CONTENT_SELECTORS)]
        content = " ".join(part for part in content_parts if part)
        return content[:5000]

    def _extract_url(self, item: Tag, page_url: str) -> str | None:
        """Extract and normalize the first link URL from a card."""
        anchor = item.select_one("a[href]")
        if anchor is None:
            return None
        href = anchor.get("href")
        if not isinstance(href, str) or not href.strip():
            return None
        normalized = urljoin(page_url, href.strip())
        return normalized

    def _extract_published_at(self, item: Tag) -> datetime:
        """Best-effort published date extraction with UTC fallback."""
        date_tag = item.select_one(DATE_SELECTORS)
        raw_value: str | None = None

        if date_tag is not None:
            datetime_attr = date_tag.get("datetime")
            if isinstance(datetime_attr, str) and datetime_attr.strip():
                raw_value = datetime_attr.strip()
            else:
                raw_value = date_tag.get_text(" ", strip=True)

        if raw_value:
            try:
                normalized = raw_value.replace("Z", "+00:00")
                parsed = datetime.fromisoformat(normalized)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                logger.debug("Could not parse published_at value=%r", raw_value)

        return datetime.now(timezone.utc)
