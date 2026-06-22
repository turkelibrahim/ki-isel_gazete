"""Language-aware article query helpers."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, User

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "tr"


async def get_articles_by_user_language(db: AsyncSession, user_id: int | str) -> list[Article]:
    """Return articles matching a user's language preference.

    If the user or preference is missing, Turkish is used as the safe default.
    """
    preference = DEFAULT_LANGUAGE

    try:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if user and getattr(user, "language_preference", None):
            preference = str(user.language_preference)
    except Exception:
        logger.warning("Could not read language preference for user_id=%s; falling back to %s", user_id, preference)

    article_result = await db.execute(
        select(Article)
        .where(Article.language == preference)
        .order_by(Article.published_at.desc())
    )
    return list(article_result.scalars().all())


async def get_articles_by_language(db: AsyncSession, language: str | None = None) -> list[Article]:
    """Return articles by explicit language code with Turkish as default."""
    selected_language = language or DEFAULT_LANGUAGE
    result = await db.execute(
        select(Article)
        .where(Article.language == selected_language)
        .order_by(Article.published_at.desc())
    )
    return list(result.scalars().all())
