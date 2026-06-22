"""Bookmark service with optimistic insert semantics."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, UserBookmark, UserEvent

logger = logging.getLogger(__name__)


class BookmarkService:
    """Manage user bookmarks and feed the recommender with bookmark events."""

    async def add_bookmark(self, db: AsyncSession, user_id: str | int, article_id: int) -> dict[str, Any]:
        """Optimistically insert a bookmark and catch duplicate-key IntegrityError.

        The method intentionally does not run a SELECT against user_bookmarks before
        INSERT. The UNIQUE(user_id, article_id) constraint is the source of truth.
        """
        normalized_user_id = _normalize_user_id(user_id)
        article = await self._get_bookmarkable_article(db, article_id)

        bookmark = UserBookmark(user_id=normalized_user_id, article_id=article.id)
        db.add(bookmark)
        try:
            await db.flush()
            db.add(
                UserEvent(
                    user_id=normalized_user_id,
                    article_id=article.id,
                    event_type="BOOKMARKED",
                    created_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            await db.refresh(bookmark)
            return {
                "status": "added",
                "bookmarked": True,
                "user_id": normalized_user_id,
                "article_id": article.id,
                "bookmark_id": bookmark.id,
                "created_at": _dt_to_iso(bookmark.created_at),
            }
        except IntegrityError:
            await db.rollback()
            logger.info("Bookmark already exists user_id=%s article_id=%s", normalized_user_id, article_id)
            return {"status": "already_exists", "bookmarked": True, "user_id": normalized_user_id, "article_id": article_id}
        except Exception:
            await db.rollback()
            logger.exception("Could not add bookmark user_id=%s article_id=%s", normalized_user_id, article_id)
            raise

    async def remove_bookmark(self, db: AsyncSession, user_id: str | int, article_id: int) -> dict[str, Any]:
        """Remove a bookmark if it exists; missing bookmarks are not errors."""
        normalized_user_id = _normalize_user_id(user_id)
        result = await db.execute(
            select(UserBookmark).where(
                UserBookmark.user_id == normalized_user_id,
                UserBookmark.article_id == article_id,
            )
        )
        bookmark = result.scalar_one_or_none()
        if bookmark is None:
            return {"status": "not_found", "bookmarked": False, "user_id": normalized_user_id, "article_id": article_id}

        await db.delete(bookmark)
        db.add(
            UserEvent(
                user_id=normalized_user_id,
                article_id=article_id,
                event_type="UNBOOKMARKED",
                created_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
        return {"status": "removed", "bookmarked": False, "user_id": normalized_user_id, "article_id": article_id}

    async def list_bookmarks(
        self,
        db: AsyncSession,
        user_id: str | int,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """List a user's bookmarks ordered by bookmark creation time descending."""
        normalized_user_id = _normalize_user_id(user_id)
        page = max(int(page), 1)
        page_size = max(min(int(page_size), 100), 1)
        offset = (page - 1) * page_size

        base_stmt = (
            select(UserBookmark, Article)
            .join(Article, Article.id == UserBookmark.article_id)
            .where(UserBookmark.user_id == normalized_user_id, Article.is_duplicate.is_(False))
        )
        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await db.execute(total_stmt)).scalar_one() or 0)

        rows = list(
            (
                await db.execute(
                    base_stmt.order_by(desc(UserBookmark.created_at)).offset(offset).limit(page_size)
                )
            ).all()
        )
        items = [_serialize_bookmark(bookmark, article) for bookmark, article in rows]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next": offset + len(items) < total,
            "user_id": normalized_user_id,
        }

    async def is_bookmarked(self, db: AsyncSession, user_id: str | int, article_id: int) -> bool:
        """Return whether a user has bookmarked an article."""
        normalized_user_id = _normalize_user_id(user_id)
        result = await db.execute(
            select(UserBookmark.id).where(
                UserBookmark.user_id == normalized_user_id,
                UserBookmark.article_id == article_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def toggle_bookmark(self, db: AsyncSession, user_id: str | int, article_id: int) -> dict[str, Any]:
        """Add a bookmark if missing, otherwise remove it."""
        if await self.is_bookmarked(db, user_id, article_id):
            return await self.remove_bookmark(db, user_id, article_id)
        return await self.add_bookmark(db, user_id, article_id)

    async def _get_bookmarkable_article(self, db: AsyncSession, article_id: int) -> Article:
        """Validate that the article exists and is not a duplicate row."""
        result = await db.execute(select(Article).where(Article.id == article_id))
        article = result.scalar_one_or_none()
        if article is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        if bool(getattr(article, "is_duplicate", False)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate articles cannot be bookmarked")
        return article


def _normalize_user_id(user_id: str | int) -> str:
    """Normalize temporary query-param user identifiers for the current schema."""
    cleaned = str(user_id).strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")
    return cleaned


def _serialize_bookmark(bookmark: UserBookmark, article: Article) -> dict[str, Any]:
    """Serialize a bookmark and its joined article."""
    published_at = getattr(article, "published_at", None)
    return {
        "id": bookmark.id,
        "bookmark_id": bookmark.id,
        "user_id": bookmark.user_id,
        "article_id": article.id,
        "bookmarked": True,
        "created_at": _dt_to_iso(bookmark.created_at),
        "article": {
            "id": article.id,
            "title": article.title,
            "summary": getattr(article, "summary", None),
            "url": article.url,
            "language": getattr(article, "language", "unknown"),
            "source_id": article.source_id,
            "view_count": int(getattr(article, "view_count", 0) or 0),
            "published_at": _dt_to_iso(published_at),
        },
    }


def _dt_to_iso(value: Any) -> str | None:
    """Return datetime-like values as ISO strings."""
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)
