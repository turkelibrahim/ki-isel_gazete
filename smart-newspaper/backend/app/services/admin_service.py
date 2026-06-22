"""Admin CRUD, soft-delete and audit-log service for Module 8."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, AuditLog, Source, User

logger = logging.getLogger(__name__)

VALID_ROLES = {"ADMIN", "EDITOR", "USER"}


class AdminService:
    """Backend management service for users, sources, articles and audit logs.

    The service follows the existing schema. It never changes ``database.py`` and
    uses soft-delete style updates where the current tables allow it.
    """

    async def list_users(self, db: AsyncSession, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        """Return paginated users for the admin panel."""
        page, page_size = _normalize_pagination(page, page_size)
        total = int((await db.execute(select(func.count()).select_from(User))).scalar_one() or 0)
        stmt = select(User).order_by(desc(User.created_at)).offset((page - 1) * page_size).limit(page_size)
        users = (await db.execute(stmt)).scalars().all()
        return _page_response(
            [
                {
                    "id": str(user.id),
                    "email": user.email,
                    "language_preference": user.language_preference,
                    "role": user.role,
                    "created_at": _dt_to_iso(user.created_at),
                }
                for user in users
            ],
            page,
            page_size,
            total,
        )

    async def update_user_role(self, db: AsyncSession, user_id: str | int, role: str, admin_user_id: str | int) -> dict[str, Any]:
        """Update a user's role and audit the action.

        Admins are not allowed to change their own role because that can lock the
        last admin out of the system by accident.
        """
        normalized_user_id = _normalize_id(user_id)
        normalized_admin_id = _normalize_id(admin_user_id)
        normalized_role = _normalize_role(role)
        if normalized_user_id == normalized_admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admins cannot change their own role from this endpoint",
            )

        user = await self._get_user_or_404(db, normalized_user_id)
        old_role = user.role
        user.role = normalized_role
        await self.create_audit_log(
            db,
            user_id=normalized_admin_id,
            action="UPDATE_USER_ROLE",
            resource_type="user",
            resource_id=normalized_user_id,
            details={"old_role": old_role, "new_role": normalized_role},
            commit=False,
        )
        await db.commit()
        await db.refresh(user)
        return {
            "status": "updated",
            "action": "UPDATE_USER_ROLE",
            "resource_type": "user",
            "resource_id": str(user.id),
            "details": {"old_role": old_role, "new_role": user.role},
        }

    async def list_sources(self, db: AsyncSession, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        """Return paginated sources for the admin panel."""
        page, page_size = _normalize_pagination(page, page_size)
        total = int((await db.execute(select(func.count()).select_from(Source))).scalar_one() or 0)
        stmt = select(Source).order_by(desc(Source.created_at)).offset((page - 1) * page_size).limit(page_size)
        sources = (await db.execute(stmt)).scalars().all()
        return _page_response(
            [
                {
                    "id": int(source.id),
                    "name": source.name,
                    "base_url": source.base_url,
                    "is_active": bool(source.is_active),
                    "trust_score": float(source.trust_score or 0.0),
                    "created_at": _dt_to_iso(source.created_at),
                }
                for source in sources
            ],
            page,
            page_size,
            total,
        )

    async def deactivate_source(self, db: AsyncSession, source_id: int, admin_user_id: str | int) -> dict[str, Any]:
        """Soft-delete/deactivate a source instead of hard deleting it."""
        source = await self._get_source_or_404(db, source_id)
        old_value = bool(source.is_active)
        source.is_active = False
        await self.create_audit_log(
            db,
            user_id=_normalize_id(admin_user_id),
            action="DEACTIVATE_SOURCE",
            resource_type="source",
            resource_id=source.id,
            details={"old_is_active": old_value, "new_is_active": False},
            commit=False,
        )
        await db.commit()
        await db.refresh(source)
        return _action_response("DEACTIVATE_SOURCE", "source", source.id, {"is_active": bool(source.is_active)})

    async def activate_source(self, db: AsyncSession, source_id: int, admin_user_id: str | int) -> dict[str, Any]:
        """Activate a previously deactivated source."""
        source = await self._get_source_or_404(db, source_id)
        old_value = bool(source.is_active)
        source.is_active = True
        await self.create_audit_log(
            db,
            user_id=_normalize_id(admin_user_id),
            action="ACTIVATE_SOURCE",
            resource_type="source",
            resource_id=source.id,
            details={"old_is_active": old_value, "new_is_active": True},
            commit=False,
        )
        await db.commit()
        await db.refresh(source)
        return _action_response("ACTIVATE_SOURCE", "source", source.id, {"is_active": bool(source.is_active)})

    async def update_source_trust_score(
        self,
        db: AsyncSession,
        source_id: int,
        trust_score: float,
        admin_user_id: str | int,
    ) -> dict[str, Any]:
        """Update source trust score after validating the 0.0-1.0 badge range."""
        score = float(trust_score)
        if score < 0.0 or score > 1.0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="trust_score must be between 0.0 and 1.0")
        source = await self._get_source_or_404(db, source_id)
        old_score = float(source.trust_score or 0.0)
        source.trust_score = score
        await self.create_audit_log(
            db,
            user_id=_normalize_id(admin_user_id),
            action="UPDATE_SOURCE_TRUST",
            resource_type="source",
            resource_id=source.id,
            details={"old_trust_score": old_score, "new_trust_score": score},
            commit=False,
        )
        await db.commit()
        await db.refresh(source)
        return _action_response("UPDATE_SOURCE_TRUST", "source", source.id, {"old_trust_score": old_score, "trust_score": score})

    async def list_articles_admin(self, db: AsyncSession, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return paginated articles with admin filters."""
        filters = filters or {}
        page, page_size = _normalize_pagination(filters.get("page", 1), filters.get("page_size", 20))
        stmt = select(Article, Source.name.label("source_name")).outerjoin(Source, Source.id == Article.source_id)
        count_stmt = select(func.count(Article.id))

        conditions = []
        if filters.get("source_id") is not None:
            conditions.append(Article.source_id == int(filters["source_id"]))
        if filters.get("language"):
            conditions.append(Article.language == str(filters["language"]).strip().lower())
        if filters.get("is_duplicate") is not None:
            conditions.append(Article.is_duplicate.is_(bool(filters["is_duplicate"])))
        if filters.get("q"):
            like_query = f"%{str(filters['q']).strip()}%"
            conditions.append(Article.title.ilike(like_query))

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = int((await db.execute(count_stmt)).scalar_one() or 0)
        rows = (
            await db.execute(stmt.order_by(desc(Article.published_at)).offset((page - 1) * page_size).limit(page_size))
        ).all()
        items = [
            {
                "id": int(article.id),
                "title": article.title,
                "summary": article.summary,
                "url": article.url,
                "source_id": int(article.source_id),
                "source_name": source_name,
                "language": article.language,
                "view_count": int(article.view_count or 0),
                "is_duplicate": bool(article.is_duplicate),
                "published_at": _dt_to_iso(article.published_at),
                "created_at": _dt_to_iso(article.created_at),
            }
            for article, source_name in rows
        ]
        return _page_response(items, page, page_size, total)

    async def mark_article_duplicate(self, db: AsyncSession, article_id: int, admin_user_id: str | int) -> dict[str, Any]:
        """Mark an article duplicate without deleting the row."""
        article = await self._get_article_or_404(db, article_id)
        old_value = bool(article.is_duplicate)
        article.is_duplicate = True
        await self.create_audit_log(
            db,
            user_id=_normalize_id(admin_user_id),
            action="MARK_ARTICLE_DUPLICATE",
            resource_type="article",
            resource_id=article.id,
            details={"old_is_duplicate": old_value, "new_is_duplicate": True},
            commit=False,
        )
        await db.commit()
        await db.refresh(article)
        return _action_response("MARK_ARTICLE_DUPLICATE", "article", article.id, {"is_duplicate": bool(article.is_duplicate)})

    async def delete_article_safe(self, db: AsyncSession, article_id: int, admin_user_id: str | int) -> dict[str, Any]:
        """Safe delete an article by marking it duplicate instead of hard deleting."""
        article = await self._get_article_or_404(db, article_id)
        old_value = bool(article.is_duplicate)
        article.is_duplicate = True
        await self.create_audit_log(
            db,
            user_id=_normalize_id(admin_user_id),
            action="SAFE_DELETE_ARTICLE",
            resource_type="article",
            resource_id=article.id,
            details={"old_is_duplicate": old_value, "new_is_duplicate": True, "soft_delete_strategy": "is_duplicate=True"},
            commit=False,
        )
        await db.commit()
        await db.refresh(article)
        return _action_response("SAFE_DELETE_ARTICLE", "article", article.id, {"is_duplicate": bool(article.is_duplicate)})

    async def list_audit_logs(self, db: AsyncSession, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        """Return audit log rows newest first."""
        page, page_size = _normalize_pagination(page, page_size)
        total = int((await db.execute(select(func.count()).select_from(AuditLog))).scalar_one() or 0)
        stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
        return _page_response([_audit_to_dict(row) for row in rows], page, page_size, total)

    async def create_audit_log(
        self,
        db: AsyncSession,
        user_id: str | int,
        action: str,
        resource_type: str,
        resource_id: str | int,
        details: dict[str, Any] | None,
        *,
        commit: bool = True,
    ) -> None:
        """Insert an audit_log row for a critical admin operation."""
        audit = AuditLog(
            action=str(action).strip().upper(),
            resource_type=str(resource_type).strip().lower(),
            resource_id=str(resource_id),
            details=details or {},
            created_by=_normalize_id(user_id),
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit)
        if commit:
            await db.commit()

    async def _get_user_or_404(self, db: AsyncSession, user_id: str) -> User:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    async def _get_source_or_404(self, db: AsyncSession, source_id: int) -> Source:
        source = (await db.execute(select(Source).where(Source.id == int(source_id)))).scalar_one_or_none()
        if source is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
        return source

    async def _get_article_or_404(self, db: AsyncSession, article_id: int) -> Article:
        article = (await db.execute(select(Article).where(Article.id == int(article_id)))).scalar_one_or_none()
        if article is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        return article


def _normalize_role(role: str) -> str:
    normalized = str(role or "").strip().upper()
    if normalized not in VALID_ROLES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="role must be one of ADMIN, EDITOR, USER")
    return normalized


def _normalize_id(value: str | int) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")
    return normalized


def _normalize_pagination(page: Any, page_size: Any) -> tuple[int, int]:
    safe_page = max(int(page or 1), 1)
    safe_page_size = min(max(int(page_size or 20), 1), 100)
    return safe_page, safe_page_size


def _page_response(items: list[dict[str, Any]], page: int, page_size: int, total: int) -> dict[str, Any]:
    return {"items": items, "page": page, "page_size": page_size, "total": total, "has_next": page * page_size < total}


def _action_response(action: str, resource_type: str, resource_id: str | int, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok",
        "action": action,
        "resource_type": resource_type,
        "resource_id": str(resource_id),
        "details": details,
    }


def _audit_to_dict(row: AuditLog) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "user_id": getattr(row, "created_by", None),
        "action": row.action,
        "resource_type": row.resource_type,
        "resource_id": str(row.resource_id),
        "details": row.details,
        "timestamp": _dt_to_iso(row.created_at),
    }


def _dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
