"""Spider orchestration and PostgreSQL persistence."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Source
from app.services.article_saver import save_article

from .news_spider import NewsSpider

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SpiderRunStats:
    """Aggregate spider run statistics."""

    crawled: int = 0
    errors: int = 0
    active_sources: int = 0
    last_crawl_time: datetime | None = None


_LAST_RUN: SpiderRunStats = SpiderRunStats()


class SpiderManager:
    """Load active sources, run spiders, and upsert articles."""

    async def run_all(self) -> dict[str, int]:
        """Run all active source spiders and return aggregate counters."""
        stats = SpiderRunStats(last_crawl_time=datetime.now(timezone.utc))

        async with AsyncSessionLocal() as session:
            sources = await self._load_active_sources(session)
            stats.active_sources = len(sources)

            for source in sources:
                try:
                    spider = self._build_spider(source)
                    result = await spider.crawl()
                    inserted_count = await self._upsert_articles(session, result.articles)
                    stats.crawled += inserted_count
                    stats.errors += result.errors
                except Exception:
                    stats.errors += 1
                    logger.exception("Source crawl failed source_id=%s", getattr(source, "id", "unknown"))

        self._save_last_run(stats)
        return {"crawled": stats.crawled, "errors": stats.errors}

    async def status(self) -> dict[str, int | str | None]:
        """Return latest crawl metadata and active source count."""
        async with AsyncSessionLocal() as session:
            active_sources = await self._count_active_sources(session)

        last_crawl_time = _LAST_RUN.last_crawl_time.isoformat() if _LAST_RUN.last_crawl_time else None
        return {
            "last_crawl_time": last_crawl_time,
            "last_error_count": _LAST_RUN.errors,
            "active_sources": active_sources,
        }

    async def _load_active_sources(self, session: AsyncSession) -> list[Source]:
        """Load all active sources from the database."""
        result = await session.execute(select(Source).where(Source.is_active.is_(True)))
        return list(result.scalars().all())

    async def _count_active_sources(self, session: AsyncSession) -> int:
        """Count active sources for status output."""
        result = await session.execute(select(func.count()).select_from(Source).where(Source.is_active.is_(True)))
        return int(result.scalar_one() or 0)

    def _build_spider(self, source: Source) -> NewsSpider:
        """Create the source-specific spider instance.

        The current implementation uses a generic ``NewsSpider``. More specific
        source spiders can be added later by mapping ``source.type`` or
        ``source.slug`` to custom subclasses while preserving the same manager.
        """
        start_urls = self._source_urls(source)
        return NewsSpider(source_id=int(source.id), start_urls=start_urls, base_url=source.base_url)

    def _source_urls(self, source: Source) -> list[str]:
        """Return crawl seed URLs from a source row."""
        if source.start_urls:
            if isinstance(source.start_urls, list):
                return [str(url) for url in source.start_urls]
            if isinstance(source.start_urls, str):
                return [url.strip() for url in source.start_urls.split(",") if url.strip()]
        return [source.base_url] if source.base_url else []

    async def _upsert_articles(self, session: AsyncSession, articles: Iterable[dict[str, Any]]) -> int:
        """Persist articles through the shared saver with language detection."""
        inserted_count = 0

        for article in articles:
            try:
                if await save_article(session, article):
                    inserted_count += 1
            except Exception:
                logger.exception("Article upsert failed url=%s", article.get("url"))
                continue

        return inserted_count

    def _save_last_run(self, stats: SpiderRunStats) -> None:
        """Persist process-local last-run metadata."""
        global _LAST_RUN
        _LAST_RUN = stats
