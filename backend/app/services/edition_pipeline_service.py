"""End-to-end personal newspaper edition generation pipeline."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, NewspaperEdition, User
from app.schemas.article_filters import FilterParams
from app.services.article_filter_service import filter_articles
from app.services.citation_service import CitationService
from app.services.event_service import EventService
from app.services.layout_service import LayoutService
from app.services.prioritization_service import PrioritizationService
from app.services.recommendation_service import get_personalized_feed

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 30


class EditionPipelineService:
    """Generate and persist a daily personalized newspaper edition.

    The pipeline coordinates the recommender, filters, headline ranking, event
    collection, citations, and the Jinja2 layout renderer.  PDF generation is
    intentionally left to Module 4; this service stores PDF-ready HTML only.
    """

    def __init__(self) -> None:
        """Initialize stateless pipeline dependencies."""
        self.prioritization_service = PrioritizationService()
        self.citation_service = CitationService()
        self.layout_service = LayoutService()
        self.event_service = EventService()

    async def generate_daily_edition(
        self,
        db: AsyncSession,
        user_id: int | str,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate today's daily edition and upsert it into ``newspaper_editions``.

        Args:
            db: A fresh AsyncSession owned by the caller.
            user_id: User id whose personalized newspaper will be generated.
            filters: Optional article filters such as category, source, date and language.

        Returns:
            A response dictionary containing the edition id, user id, date,
            article/event counts, HTML content, and generation status.
        """
        user_key = str(user_id)
        user = await db.get(User, user_key)
        if user is None:
            raise ValueError(f"User not found: {user_key}")

        language = self._resolve_language(user, filters)
        limit = self._resolve_limit(filters)

        feed = await get_personalized_feed(db, user_id=user_key, limit=max(limit, DEFAULT_LIMIT))
        articles = [dict(item) for item in feed.get("items", [])]

        if filters:
            articles = await self._apply_filters(db, user_key, language, articles, filters, limit)

        ranked_articles = self.prioritization_service.rank(articles)[:limit]
        events = await self._load_events(db, user_key, filters)
        citations = self.citation_service.build_citations(ranked_articles)
        user_payload = self._serialize_user(user)
        edition_day = self._resolve_edition_date(filters)

        html_content = self.layout_service.render_daily(
            articles=ranked_articles,
            events=events,
            user=user_payload,
            edition_date=edition_day,
            edition_title="Kişisel Gazete",
            citations=citations,
        )

        edition = await self._upsert_edition(
            db=db,
            user_id=user_key,
            edition_date=edition_day,
            language=language,
            html_content=html_content,
            metadata={
                "pipeline": "module3_p17",
                "frequency": "daily",
                "filters": filters or {},
                "feed_algorithm": feed.get("algorithm"),
                "article_count": len(ranked_articles),
                "event_count": len(events),
                "headline_article_id": ranked_articles[0].get("id") if ranked_articles else None,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {
            "edition_id": edition.id,
            "user_id": user_key,
            "edition_date": edition.edition_date.isoformat(),
            "frequency": edition.frequency,
            "article_count": len(ranked_articles),
            "event_count": len(events),
            "html_content": html_content,
            "pdf_path": edition.pdf_path,
            "status": "generated",
        }

    async def _apply_filters(
        self,
        db: AsyncSession,
        user_id: str,
        language: str,
        personalized_articles: list[dict[str, Any]],
        filters: dict[str, Any],
        limit: int,
    ) -> list[dict[str, Any]]:
        """Apply ArticleFilterService and preserve personalized ordering when possible."""
        filter_payload = dict(filters or {})
        filter_payload.setdefault("user_id", user_id)
        filter_payload.setdefault("language", language)
        filter_payload.setdefault("page", 1)
        filter_payload.setdefault("page_size", min(max(limit * 3, limit), 100))
        params = FilterParams(**filter_payload)
        filtered = await filter_articles(db, params)
        filtered_items = [dict(item) for item in filtered.get("items", [])]
        allowed_ids = {self._safe_int(item.get("id") or item.get("article_id")) for item in filtered_items}
        allowed_ids.discard(None)

        if not personalized_articles:
            return filtered_items[:limit]

        matched = [
            item
            for item in personalized_articles
            if self._safe_int(item.get("id") or item.get("article_id")) in allowed_ids
        ]
        if matched:
            return matched[:limit]

        # If personalization candidates are exhausted by strict filters, return
        # the filtered list so the user still receives a valid edition.
        return filtered_items[:limit]

    async def _load_events(
        self,
        db: AsyncSession,
        user_id: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Load the next seven days of user/global events for the newspaper layout."""
        try:
            upcoming_events = await self.event_service.get_upcoming_events(db, days=7)
            category = (filters or {}).get("event_category") or (filters or {}).get("category")
            selected: list[Event] = []
            for event in upcoming_events:
                event_user_id = getattr(event, "user_id", None)
                if event_user_id not in (None, user_id):
                    continue
                if category and str(getattr(event, "category", "")) != str(category):
                    continue
                selected.append(event)
                if len(selected) >= 10:
                    break
            return [self._serialize_event(event) for event in selected]
        except Exception:
            logger.warning("Could not load events for user_id=%s", user_id, exc_info=True)
            return []

    async def _upsert_edition(
        self,
        db: AsyncSession,
        user_id: str,
        edition_date: date,
        language: str,
        html_content: str,
        metadata: dict[str, Any],
    ) -> NewspaperEdition:
        """Update today's existing daily edition or create a new one."""
        stmt = (
            select(NewspaperEdition)
            .where(NewspaperEdition.user_id == user_id)
            .where(NewspaperEdition.edition_date == edition_date)
            .where(NewspaperEdition.frequency == "daily")
            .order_by(desc(NewspaperEdition.created_at))
            .limit(1)
        )
        existing = (await db.execute(stmt)).scalars().first()
        now = datetime.now(timezone.utc)
        if existing is not None:
            existing.html_content = html_content
            existing.language = language
            existing.metadata_json = metadata
            existing.pdf_path = None
            existing.updated_at = now
            edition = existing
        else:
            edition = NewspaperEdition(
                user_id=user_id,
                edition_date=edition_date,
                frequency="daily",
                html_content=html_content,
                pdf_path=None,
                language=language,
                metadata_json=metadata,
                created_at=now,
                updated_at=now,
            )
            db.add(edition)
        await db.commit()
        await db.refresh(edition)
        return edition

    def _resolve_language(self, user: User, filters: dict[str, Any] | None) -> str:
        """Resolve filter language first, then user language preference, then Turkish."""
        language = (filters or {}).get("language") or getattr(user, "language_preference", None) or "tr"
        return str(language).strip().lower() or "tr"

    def _resolve_limit(self, filters: dict[str, Any] | None) -> int:
        """Resolve article limit from filters with safe bounds."""
        raw = (filters or {}).get("limit") or (filters or {}).get("page_size") or DEFAULT_LIMIT
        try:
            return max(1, min(int(raw), 100))
        except (TypeError, ValueError):
            return DEFAULT_LIMIT

    def _resolve_edition_date(self, filters: dict[str, Any] | None) -> date:
        """Resolve edition date from filters or use today's UTC date."""
        raw = (filters or {}).get("edition_date") or (filters or {}).get("date")
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, date):
            return raw
        if raw:
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
            except ValueError:
                logger.warning("Invalid edition_date=%r; using today", raw)
        return datetime.now(timezone.utc).date()

    def _serialize_user(self, user: User) -> dict[str, Any]:
        """Return safe user metadata for the newspaper masthead."""
        email = getattr(user, "email", None)
        name = str(email).split("@")[0] if email else str(user.id)
        return {
            "id": user.id,
            "name": name,
            "email": email,
            "language_preference": getattr(user, "language_preference", "tr"),
        }

    def _serialize_event(self, event: Event) -> dict[str, Any]:
        """Serialize an Event ORM row for the Jinja2 layout."""
        return {
            "id": event.id,
            "title": event.title,
            "description": event.description,
            "location": event.location,
            "category": event.category,
            "date": event.event_date.isoformat() if isinstance(event.event_date, datetime) else str(event.event_date),
            "event_date": event.event_date.isoformat() if isinstance(event.event_date, datetime) else str(event.event_date),
            "remind_at": event.remind_at.isoformat() if isinstance(event.remind_at, datetime) and event.remind_at else None,
        }

    def _safe_int(self, value: Any) -> int | None:
        """Convert a value to int or return None."""
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
