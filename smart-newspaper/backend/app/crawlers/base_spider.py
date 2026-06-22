"""Reusable asynchronous crawler base classes.

This module implements the Template Method pattern. Subclasses only override
``parse`` while the shared workflow keeps rate limiting, user-agent rotation,
robots.txt checks, HTTP fetching, and error handling in one place.
"""

from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

UA_LIST: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) "
    "Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:126.0) "
    "Gecko/20100101 Firefox/126.0",
]


@dataclass(slots=True)
class CrawlResult:
    """Result object returned from a spider crawl."""

    articles: list[dict[str, Any]] = field(default_factory=list)
    errors: int = 0
    skipped: int = 0


class BaseSpider(ABC):
    """Base class for asynchronous news spiders.

    Subclasses must provide ``parse``. All non-source-specific crawler behavior
    remains in this class so every spider follows the same safe workflow.
    """

    start_urls: list[str]
    source_id: int

    def __init__(self, source_id: int, start_urls: list[str], base_url: str | None = None) -> None:
        """Create a spider for one source.

        Args:
            source_id: Database id of the source being crawled.
            start_urls: Seed URLs to crawl.
            base_url: Optional source root URL used for robots.txt lookup.
        """
        self.source_id = source_id
        self.start_urls = [url for url in start_urls if url]
        self.base_url = (base_url or self._infer_base_url()).rstrip("/")
        self._robots_cache: dict[str, RobotFileParser | None] = {}

    @abstractmethod
    def parse(self, html: str, url: str) -> list[dict[str, Any]]:
        """Parse HTML and return article dictionaries.

        Args:
            html: Raw HTML returned from the requested URL.
            url: Final URL that produced the HTML.
        """

    async def crawl(self) -> CrawlResult:
        """Crawl all start URLs without letting one failure stop the source."""
        result = CrawlResult()

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for url in self.start_urls:
                try:
                    if not await self._can_fetch(url):
                        result.skipped += 1
                        logger.warning("robots.txt disallowed crawl url=%s source_id=%s", url, self.source_id)
                        continue

                    html = await self._request(client, url)
                    if not html:
                        result.errors += 1
                        continue

                    parsed_items = self.parse(html, url)
                    result.articles.extend(parsed_items)
                except Exception:
                    result.errors += 1
                    logger.exception("Spider failed for url=%s source_id=%s", url, self.source_id)

        return result

    async def _request(self, client: httpx.AsyncClient, url: str) -> str | None:
        """Fetch one URL with random pre-request delay and UA rotation."""
        await asyncio.sleep(random.uniform(1.5, 3.5))
        selected_user_agent = random.choice(UA_LIST)

        try:
            response = await client.get(url, headers={"User-Agent": selected_user_agent})
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "HTTP status error while crawling url=%s status=%s source_id=%s",
                url,
                exc.response.status_code,
                self.source_id,
            )
        except httpx.RequestError:
            logger.exception("HTTP request failed while crawling url=%s source_id=%s", url, self.source_id)
        return None

    async def _can_fetch(self, url: str) -> bool:
        """Check robots.txt for a URL; fail-open if robots cannot be read."""
        robots_url = self._robots_url_for(url)
        parser = self._robots_cache.get(robots_url)

        if robots_url not in self._robots_cache:
            parser = RobotFileParser()
            parser.set_url(robots_url)
            try:
                await asyncio.to_thread(parser.read)
            except Exception:
                logger.warning("Could not read robots.txt at %s; failing open", robots_url)
                parser = None
            self._robots_cache[robots_url] = parser

        if parser is None:
            return True

        try:
            return parser.can_fetch("*", url)
        except Exception:
            logger.warning("robots.txt parsing failed for url=%s; failing open", url)
            return True

    def _robots_url_for(self, url: str) -> str:
        """Build the robots.txt URL for a target URL."""
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        return f"{self.base_url}/robots.txt"

    def _infer_base_url(self) -> str:
        """Infer source base URL from the first configured start URL."""
        if not self.start_urls:
            return ""
        parsed = urlparse(self.start_urls[0])
        if not parsed.scheme or not parsed.netloc:
            return ""
        return f"{parsed.scheme}://{parsed.netloc}"
