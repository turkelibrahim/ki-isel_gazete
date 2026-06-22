"""RSS ingestion service for active source rows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source
from app.services.article_saver import save_article

logger = logging.getLogger(__name__)


class RSSService:
    """Fetch RSS/Atom URLs from all active sources."""

    async def fetch_all(self, db: AsyncSession) -> dict[str, int]:
        """Fetch every active source's RSS/start URLs and persist new articles."""
        result = await db.execute(select(Source).where(Source.is_active.is_(True)))
        sources = list(result.scalars().all())

        fetched = 0
        errors = 0
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for source in sources:
                for url in self._source_urls(source):
                    try:
                        count = await self._fetch_source_url(client, db, source, url)
                        fetched += count
                    except Exception:
                        errors += 1
                        logger.exception("RSS fetch failed source_id=%s url=%s", getattr(source, "id", None), url)

        return {"fetched": fetched, "errors": errors}

    async def _fetch_source_url(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        source: Source,
        url: str,
    ) -> int:
        """Fetch and persist one RSS/Atom URL."""
        response = await client.get(url, headers={"User-Agent": "SmartNewspaperBot/1.0 (+scheduled-rss)"})
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "xml")
        entries = soup.find_all("item") or soup.find_all("entry")
        inserted = 0

        for entry in entries:
            article = self._normalize_entry(entry, int(source.id))
            if not article:
                continue
            if await save_article(db, article):
                inserted += 1

        logger.info("RSS parsed source_id=%s url=%s inserted=%s", source.id, url, inserted)
        return inserted

    def _source_urls(self, source: Source) -> list[str]:
        """Extract RSS URLs from a source row."""
        urls: list[str] = []
        if source.start_urls:
            if isinstance(source.start_urls, list):
                urls.extend(str(url) for url in source.start_urls if url)
            elif isinstance(source.start_urls, str):
                urls.extend(url.strip() for url in source.start_urls.split(",") if url.strip())
        elif source.base_url:
            urls.append(str(source.base_url))
        return urls

    def _normalize_entry(self, entry: Any, source_id: int) -> dict[str, Any] | None:
        """Normalize an RSS/Atom item to the Article shape."""
        title = self._text(entry, "title")
        url = self._entry_url(entry)
        if not title or not url:
            return None

        content = (
            self._text(entry, "description")
            or self._text(entry, "summary")
            or self._text(entry, "content")
            or ""
        )
        published_raw = self._text(entry, "pubDate") or self._text(entry, "published") or self._text(entry, "updated")
        return {
            "title": title,
            "content": content,
            "url": url,
            "source_id": source_id,
            "published_at": self._parse_date(published_raw),
        }

    def _text(self, entry: Any, tag_name: str) -> str:
        """Return stripped text for an RSS tag."""
        tag = entry.find(tag_name)
        return tag.get_text(" ", strip=True) if tag else ""

    def _entry_url(self, entry: Any) -> str:
        """Extract canonical link from RSS or Atom entry."""
        link = entry.find("link")
        if link is None:
            return ""
        href = link.get("href")
        if href:
            return str(href).strip()
        return link.get_text(" ", strip=True)

    def _parse_date(self, value: str) -> datetime:
        """Parse common RSS/Atom date formats with UTC fallback."""
        if value:
            try:
                parsed = parsedate_to_datetime(value)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError, IndexError):
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
                except ValueError:
                    logger.debug("Could not parse RSS date value=%r", value)
        return datetime.now(timezone.utc)
