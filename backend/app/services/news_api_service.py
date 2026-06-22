"""NewsAPI-based breaking-news ingestion service."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source
from app.services.article_saver import save_article

logger = logging.getLogger(__name__)


class NewsAPIService:
    """Fetch breaking-news articles from a configurable NewsAPI endpoint."""

    def __init__(self) -> None:
        """Read provider configuration from environment variables."""
        self.api_key = os.getenv("NEWS_API_KEY", "")
        self.endpoint = os.getenv("NEWS_API_ENDPOINT", "https://newsapi.org/v2/top-headlines")
        self.country = os.getenv("NEWS_API_COUNTRY", "tr")
        self.page_size = int(os.getenv("NEWS_API_PAGE_SIZE", "20"))
        self.rate_limit_seconds = float(os.getenv("NEWSAPI_RATE_LIMIT_SECONDS", "36"))

    async def fetch(self, db: AsyncSession) -> dict[str, int]:
        """Fetch breaking news and save non-duplicate articles."""
        if not self.api_key:
            logger.warning("NEWS_API_KEY is not set; fetch_breaking_news skipped")
            return {"fetched": 0, "errors": 0}

        source_id = await self._ensure_source(db)
        params = {
            "apiKey": self.api_key,
            "country": self.country,
            "pageSize": self.page_size,
        }

        fetched = 0
        errors = 0
        if self.rate_limit_seconds > 0:
            logger.info("NewsAPI rate-limit wait seconds=%s", self.rate_limit_seconds)
            await asyncio.sleep(self.rate_limit_seconds)

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            try:
                response = await client.get(self.endpoint, params=params)
                response.raise_for_status()
                payload = response.json()
            except Exception:
                logger.exception("NewsAPI breaking-news fetch failed")
                return {"fetched": 0, "errors": 1}

        for raw in payload.get("articles", []):
            try:
                article = self._normalize_article(raw, source_id)
                if not article:
                    continue
                if await save_article(db, article):
                    fetched += 1
            except Exception:
                errors += 1
                logger.exception("NewsAPI article save failed")

        return {"fetched": fetched, "errors": errors}

    async def _ensure_source(self, db: AsyncSession) -> int:
        """Create or return the dedicated NewsAPI source row."""
        result = await db.execute(select(Source).where(Source.name == "NewsAPI Breaking"))
        source = result.scalar_one_or_none()
        if source is not None:
            return int(source.id)

        source = Source(
            name="NewsAPI Breaking",
            base_url="https://newsapi.org",
            start_urls=[self.endpoint],
            is_active=True,
        )
        db.add(source)
        await db.flush()
        return int(source.id)

    def _normalize_article(self, raw: dict[str, Any], source_id: int) -> dict[str, Any] | None:
        """Convert NewsAPI JSON to the local Article shape."""
        title = (raw.get("title") or "").strip()
        url = (raw.get("url") or "").strip()
        if not title or not url:
            return None

        content = raw.get("content") or raw.get("description") or ""
        published_at = self._parse_date(raw.get("publishedAt"))
        return {
            "title": title,
            "content": str(content),
            "url": url,
            "source_id": source_id,
            "published_at": published_at,
        }

    def _parse_date(self, value: Any) -> datetime:
        """Parse provider dates with UTC fallback."""
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                logger.debug("Could not parse NewsAPI date value=%r", value)
        return datetime.now(timezone.utc)
