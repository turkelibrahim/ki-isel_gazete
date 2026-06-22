"""Human-in-the-loop moderation and manual reclassification service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ArticleCategory, AuditLog, Category, ModerationQueue, User
from app.services.classification_service import get_or_create_category

logger = logging.getLogger(__name__)
PENDING_STATUS = "pending"
REVIEWED_STATUS = "REVIEWED"
MIN_HUMAN_LABELS_FOR_RETRAIN = 50


async def require_admin(db: AsyncSession, admin_user_id: str) -> User:
    """Return the admin user or raise PermissionError for non-admin access."""
    user = await db.get(User, admin_user_id)
    if user is None or (getattr(user, "role", "USER") or "USER").upper() != "ADMIN":
        raise PermissionError("ADMIN role required")
    return user


async def get_pending_items(db: AsyncSession) -> list[dict[str, Any]]:
    """Return pending moderation queue items with article/category context."""
    stmt = (
        select(ModerationQueue, Article, Category)
        .join(Article, Article.id == ModerationQueue.article_id)
        .join(Category, Category.id == ModerationQueue.predicted_category_id)
        .where(ModerationQueue.status == PENDING_STATUS)
        .order_by(ModerationQueue.created_at.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": item.id,
            "article_id": item.article_id,
            "title": article.title,
            "url": article.url,
            "predicted_category_id": category.id,
            "predicted_category": category.name,
            "confidence": item.confidence,
            "reason": item.reason,
            "status": item.status,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item, article, category in rows
    ]


async def approve_category(
    db: AsyncSession,
    article_id: int,
    category_id: int,
    admin_user_id: str,
) -> dict[str, Any]:
    """Approve or set a category as a human label for an article."""
    await require_admin(db, admin_user_id)
    article = await db.get(Article, article_id)
    category = await db.get(Category, category_id)
    if article is None:
        raise ValueError(f"Article {article_id} not found")
    if category is None:
        raise ValueError(f"Category {category_id} not found")

    old_categories = await _current_category_names(db, article_id)
    await _replace_with_human_label(db, article_id, category_id)
    await _mark_article_pending_items_reviewed(db, article_id, admin_user_id)
    await _write_audit_log(db, article_id, old_categories, [category.name], admin_user_id)
    await db.commit()

    human_count = await count_human_labels(db)
    return {
        "article_id": article_id,
        "category_id": category_id,
        "category": category.name,
        "is_human_label": True,
        "confidence": 1.0,
        "human_label_count": human_count,
        "retrain_ready": human_count >= MIN_HUMAN_LABELS_FOR_RETRAIN,
    }


async def reject_or_change_category(
    db: AsyncSession,
    article_id: int,
    category_id: int,
    admin_user_id: str,
) -> dict[str, Any]:
    """Change an article category and store the correction as a human label."""
    return await approve_category(db, article_id, category_id, admin_user_id)


async def mark_reviewed(db: AsyncSession, moderation_id: int, admin_user_id: str) -> dict[str, Any]:
    """Mark a queue item reviewed without changing its category assignment."""
    await require_admin(db, admin_user_id)
    item = await db.get(ModerationQueue, moderation_id)
    if item is None:
        raise ValueError(f"Moderation item {moderation_id} not found")
    item.status = REVIEWED_STATUS
    item.reviewed_by = str(admin_user_id)
    item.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": item.id, "status": item.status, "reviewed_by": item.reviewed_by}


async def approve_moderation_item(
    db: AsyncSession,
    moderation_id: int,
    admin_user_id: str,
    category_id: int | None = None,
) -> dict[str, Any]:
    """Approve a moderation queue item, optionally overriding the category."""
    item = await db.get(ModerationQueue, moderation_id)
    if item is None:
        raise ValueError(f"Moderation item {moderation_id} not found")
    selected_category_id = category_id or item.predicted_category_id
    return await approve_category(db, item.article_id, selected_category_id, admin_user_id)


async def reclassify_moderation_item(
    db: AsyncSession,
    moderation_id: int,
    category_id: int,
    admin_user_id: str,
) -> dict[str, Any]:
    """Apply an admin-selected category to a moderation item."""
    item = await db.get(ModerationQueue, moderation_id)
    if item is None:
        raise ValueError(f"Moderation item {moderation_id} not found")
    return await reject_or_change_category(db, item.article_id, category_id, admin_user_id)


async def count_human_labels(db: AsyncSession) -> int:
    """Count human-labeled category rows available for retraining."""
    stmt = select(func.count(ArticleCategory.id)).where(ArticleCategory.is_human_label.is_(True))
    return int((await db.execute(stmt)).scalar_one() or 0)


async def get_moderation_stats(db: AsyncSession) -> dict[str, Any]:
    """Return moderation queue and active-learning counters."""
    pending_stmt = select(func.count(ModerationQueue.id)).where(ModerationQueue.status == PENDING_STATUS)
    reviewed_stmt = select(func.count(ModerationQueue.id)).where(ModerationQueue.status == REVIEWED_STATUS)
    human_count = await count_human_labels(db)
    return {
        "pending": int((await db.execute(pending_stmt)).scalar_one() or 0),
        "reviewed": int((await db.execute(reviewed_stmt)).scalar_one() or 0),
        "human_label_count": human_count,
        "retrain_threshold": MIN_HUMAN_LABELS_FOR_RETRAIN,
        "retrain_ready": human_count >= MIN_HUMAN_LABELS_FOR_RETRAIN,
        "uncertainty_threshold": 0.65,
    }


async def _replace_with_human_label(db: AsyncSession, article_id: int, category_id: int) -> ArticleCategory:
    """Remove automatic labels and upsert one confidence=1.0 human label."""
    await db.execute(delete(ArticleCategory).where(ArticleCategory.article_id == article_id))
    assignment = ArticleCategory(
        article_id=article_id,
        category_id=category_id,
        confidence=1.0,
        model="human",
        is_human_label=True,
    )
    db.add(assignment)
    await db.flush()
    return assignment


async def _current_category_names(db: AsyncSession, article_id: int) -> list[str]:
    """Return current category names for audit logging."""
    stmt = (
        select(Category.name)
        .join(ArticleCategory, ArticleCategory.category_id == Category.id)
        .where(ArticleCategory.article_id == article_id)
    )
    return [str(name) for name in (await db.execute(stmt)).scalars().all()]


async def _mark_article_pending_items_reviewed(
    db: AsyncSession,
    article_id: int,
    admin_user_id: str,
) -> None:
    """Mark all pending moderation rows for an article as reviewed."""
    stmt = select(ModerationQueue).where(
        ModerationQueue.article_id == article_id,
        ModerationQueue.status == PENDING_STATUS,
    )
    items = list((await db.execute(stmt)).scalars().all())
    now = datetime.now(timezone.utc)
    for item in items:
        item.status = REVIEWED_STATUS
        item.reviewed_by = str(admin_user_id)
        item.reviewed_at = now


async def _write_audit_log(
    db: AsyncSession,
    article_id: int,
    old_categories: list[str],
    new_categories: list[str],
    admin_user_id: str,
) -> None:
    """Record one manual reclassification audit event."""
    db.add(
        AuditLog(
            action="MANUAL_RECLASSIFICATION",
            resource_type="article",
            resource_id=str(article_id),
            details={
                "old_category": old_categories,
                "new_category": new_categories,
                "admin_user_id": admin_user_id,
            },
            created_by=str(admin_user_id),
        )
    )


async def ensure_category_by_name(db: AsyncSession, name: str) -> Category:
    """Resolve or create a category by display name for admin tools."""
    return await get_or_create_category(db, name)
