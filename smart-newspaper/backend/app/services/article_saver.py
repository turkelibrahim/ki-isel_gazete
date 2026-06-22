"""Article persistence helpers with duplicate-safe URL upsert."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.duplicate_detector import DuplicateDetector
from app.ml.language_detector import LanguageDetector
from app.models import Article

logger = logging.getLogger(__name__)

language_detector = LanguageDetector()
duplicate_detector = DuplicateDetector()


async def save_article(db: AsyncSession, data: dict[str, Any]) -> bool:
    """Save one article with URL conflict protection and language detection.

    Returns:
        ``True`` when a new row was inserted, ``False`` when the URL already
        existed or the insert was skipped.
    """
    article_data = dict(data)

    combined = f"{article_data.get('title', '')} {str(article_data.get('content', ''))[:200]}"
    article_data["language"] = language_detector.detect(combined)[0]

    article_data.setdefault("content", "")
    article_data.setdefault("published_at", datetime.now(timezone.utc))

    duplicate_text = f"{article_data.get('title', '')} {str(article_data.get('content', ''))[:500]}"
    duplicate_result = duplicate_detector.is_duplicate(duplicate_text)
    article_data["is_duplicate"] = bool(duplicate_result.is_duplicate)
    article_data["minhash_signature"] = duplicate_detector.build_signature_for_text(duplicate_text)

    try:
        stmt = (
            insert(Article)
            .values(**article_data)
            .on_conflict_do_nothing(index_elements=["url"])
            .returning(Article.id)
        )
        result = await db.execute(stmt)
        inserted_id = result.scalar_one_or_none()
        inserted = inserted_id is not None
        await db.commit()

        if inserted and not article_data["is_duplicate"]:
            duplicate_detector.add(int(inserted_id), duplicate_text)

        return inserted
    except Exception:
        logger.exception("Article save failed url=%s", article_data.get("url"))
        await db.rollback()
        raise
