"""Two-layer content moderation service: keyword filter + optional ML toxicity."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, AuditLog, ModerationQueue

logger = logging.getLogger(__name__)

BLOCKED_KEYWORDS = [
    "hakaret_kelime_1",
    "tehdit_kelime_1",
    "nefret_kelime_1",
]

CONTENT_MODERATION_REASONS = {
    "BLOCKED_KEYWORD",
    "HIGH_TOXICITY",
    "NEEDS_HUMAN_REVIEW",
    "LOW_RISK",
}


class ContentModerationService:
    """Moderate text with a fast keyword pass and lazy ML toxicity classifier.

    The service is deliberately dependency-tolerant: if ``transformers`` or
    ``torch`` is missing, keyword moderation continues and responses include
    ``ml_available=False`` instead of crashing the backend.
    """

    _pipeline: Any | None = None
    _pipeline_load_attempted: bool = False

    def moderate_text(self, text: str, article_id: int | None = None) -> dict[str, Any]:
        """Run keyword and ML checks, then return a moderation decision."""
        clean_text = (text or "").strip()
        if not clean_text:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="text is required")

        keyword_result = self.keyword_filter(clean_text)
        ml_result = self.ml_toxicity_score(clean_text)
        ml_score = float(ml_result.get("toxicity_score") or 0.0)
        decision = self.decide_status(score=ml_score, keyword_blocked=bool(keyword_result.get("blocked")))
        toxicity_score = max(float(decision["toxicity_score"]), ml_score)

        return {
            "article_id": article_id,
            "status": decision["status"],
            "reason": decision["reason"],
            "toxicity_score": round(toxicity_score, 4),
            "keyword_blocked": bool(keyword_result.get("blocked")),
            "matched_keywords": keyword_result.get("matched_keywords", []),
            "keyword_filter": keyword_result,
            "ml_available": bool(ml_result.get("ml_available")),
            "ml_result": ml_result,
            "moderated_at": datetime.now(timezone.utc).isoformat(),
        }

    def keyword_filter(self, text: str) -> dict[str, Any]:
        """Fast blocked-keyword pre-filter.

        TODO: Move BLOCKED_KEYWORDS to a database/config-backed policy list and
        expand it with legal/product-specific moderation terms.
        """
        lowered = (text or "").lower()
        matched = [keyword for keyword in BLOCKED_KEYWORDS if keyword.lower() in lowered]
        return {"blocked": bool(matched), "matched_keywords": matched}

    def ml_toxicity_score(self, text: str) -> dict[str, Any]:
        """Return ML toxicity score using a lazy Turkish text-classification model."""
        pipeline = self._get_pipeline()
        if pipeline is None:
            return {
                "ml_available": False,
                "toxicity_score": 0.0,
                "label": None,
                "score": None,
                "model": "savasy/bert-base-turkish-sentiment-cased",
                "message": "ML model unavailable; keyword-only moderation used",
            }
        try:
            raw = pipeline((text or "")[:512])
            item = raw[0] if isinstance(raw, list) and raw else raw
            label = str(item.get("label", "")).lower() if isinstance(item, dict) else ""
            score = float(item.get("score", 0.0)) if isinstance(item, dict) else 0.0
            if "neg" in label or "negative" in label:
                toxicity = score
            elif "pos" in label or "positive" in label:
                toxicity = 1.0 - score
            else:
                toxicity = score if score >= 0.70 else 0.0
            return {
                "ml_available": True,
                "toxicity_score": round(max(0.0, min(1.0, toxicity)), 4),
                "label": label,
                "score": round(max(0.0, min(1.0, score)), 4),
                "model": "savasy/bert-base-turkish-sentiment-cased",
            }
        except Exception as exc:  # pragma: no cover - depends on runtime model
            logger.warning("ML toxicity scoring failed; using keyword-only fallback: %s", exc)
            return {
                "ml_available": False,
                "toxicity_score": 0.0,
                "label": None,
                "score": None,
                "model": "savasy/bert-base-turkish-sentiment-cased",
                "message": "ML scoring failed; keyword-only moderation used",
            }

    def decide_status(self, score: float, keyword_blocked: bool) -> dict[str, Any]:
        """Apply moderation thresholds to a toxicity score."""
        safe_score = max(0.0, min(1.0, float(score or 0.0)))
        if keyword_blocked:
            return {"status": "REJECTED", "reason": "BLOCKED_KEYWORD", "toxicity_score": max(safe_score, 0.95)}
        if safe_score >= 0.95:
            return {"status": "REJECTED", "reason": "HIGH_TOXICITY", "toxicity_score": safe_score}
        if safe_score >= 0.70:
            return {"status": "PENDING", "reason": "NEEDS_HUMAN_REVIEW", "toxicity_score": safe_score}
        return {"status": "APPROVED", "reason": "LOW_RISK", "toxicity_score": safe_score}

    async def create_moderation_queue_item(self, db: AsyncSession, article_id: int, result: dict[str, Any]) -> dict[str, Any]:
        """Persist a PENDING/REJECTED content moderation result.

        APPROVED rows are intentionally not queued by default. REJECTED rows mark
        the article ``is_duplicate=True`` so the existing feed/search paths hide
        it without requiring an ``article.status`` migration.
        """
        article = await self._get_article_or_404(db, article_id)
        moderation_status = str(result.get("status") or "PENDING").upper()
        reason = str(result.get("reason") or "NEEDS_HUMAN_REVIEW")
        toxicity_score = max(0.0, min(1.0, float(result.get("toxicity_score") or 0.0)))
        if moderation_status == "APPROVED":
            return {"status": "skipped", "queued": False, "article_id": int(article_id), "reason": "APPROVED_NOT_QUEUED"}

        existing = (
            await db.execute(
                select(ModerationQueue).where(
                    ModerationQueue.article_id == int(article_id),
                    ModerationQueue.flagged_reason.in_(list(CONTENT_MODERATION_REASONS)),
                    ModerationQueue.status.in_(["PENDING", "REJECTED"]),
                )
            )
        ).scalar_one_or_none()
        item = existing or ModerationQueue(article_id=int(article_id), predicted_category_id=None)
        item.confidence = toxicity_score
        item.toxicity_score = toxicity_score
        item.reason = reason
        item.flagged_reason = reason
        item.status = moderation_status
        if moderation_status == "REJECTED":
            article.is_duplicate = True
        if existing is None:
            db.add(item)
        await db.commit()
        await db.refresh(item)
        return self._queue_item_to_dict(item)

    async def approve_item(self, db: AsyncSession, moderation_id: int, reviewer_id: int | str) -> dict[str, Any]:
        """Approve a content moderation item and audit the review."""
        item = await self._get_moderation_item_or_404(db, moderation_id)
        old_status = item.status
        item.status = "APPROVED"
        item.reviewed_by = str(reviewer_id)
        item.reviewed_at = datetime.now(timezone.utc)
        await self._write_audit_log(
            db,
            reviewer_id,
            "APPROVE_MODERATION",
            item,
            {"old_status": old_status, "new_status": item.status, "toxicity_score": self._toxicity_value(item)},
        )
        await db.commit()
        await db.refresh(item)
        return self._queue_item_to_dict(item)

    async def reject_item(self, db: AsyncSession, moderation_id: int, reviewer_id: int | str) -> dict[str, Any]:
        """Reject a content moderation item, hide the article and audit the review."""
        item = await self._get_moderation_item_or_404(db, moderation_id)
        old_status = item.status
        item.status = "REJECTED"
        item.reviewed_by = str(reviewer_id)
        item.reviewed_at = datetime.now(timezone.utc)
        article = await db.get(Article, int(item.article_id))
        if article is not None:
            article.is_duplicate = True
        await self._write_audit_log(
            db,
            reviewer_id,
            "REJECT_MODERATION",
            item,
            {"old_status": old_status, "new_status": item.status, "toxicity_score": self._toxicity_value(item)},
        )
        await db.commit()
        await db.refresh(item)
        return self._queue_item_to_dict(item)

    async def list_queue(self, db: AsyncSession, status_filter: str | None = None, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        """Return content moderation queue rows newest first."""
        page, page_size = _normalize_pagination(page, page_size)
        stmt = select(ModerationQueue, Article.title).outerjoin(Article, Article.id == ModerationQueue.article_id)
        count_stmt = select(func.count(ModerationQueue.id))
        conditions = [ModerationQueue.flagged_reason.in_(list(CONTENT_MODERATION_REASONS))]
        if status_filter:
            conditions.append(ModerationQueue.status == status_filter.strip().upper())
        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        total = int((await db.execute(count_stmt)).scalar_one() or 0)
        rows = (
            await db.execute(stmt.order_by(desc(ModerationQueue.created_at)).offset((page - 1) * page_size).limit(page_size))
        ).all()
        items = []
        for item, title in rows:
            payload = self._queue_item_to_dict(item)
            payload["article_title"] = title
            items.append(payload)
        return {"items": items, "page": page, "page_size": page_size, "total": total, "has_next": page * page_size < total}

    async def get_stats(self, db: AsyncSession) -> dict[str, Any]:
        """Return content moderation counters for admin dashboard."""
        rows = (
            await db.execute(
                select(ModerationQueue.status, func.count(ModerationQueue.id))
                .where(ModerationQueue.flagged_reason.in_(list(CONTENT_MODERATION_REASONS)))
                .group_by(ModerationQueue.status)
            )
        ).all()
        by_status = {str(status_value or "UNKNOWN").upper(): int(count or 0) for status_value, count in rows}
        avg_score = (
            await db.execute(
                select(func.avg(ModerationQueue.toxicity_score)).where(
                    ModerationQueue.flagged_reason.in_(list(CONTENT_MODERATION_REASONS))
                )
            )
        ).scalar_one_or_none()
        return {
            "pending": by_status.get("PENDING", 0),
            "approved": by_status.get("APPROVED", 0),
            "rejected": by_status.get("REJECTED", 0),
            "total": sum(by_status.values()),
            "avg_toxicity_score": round(float(avg_score or 0.0), 4),
            "thresholds": {"rejected": ">=0.95 or keyword", "pending": "0.70-0.95", "approved": "<0.70"},
            "ml_model": "savasy/bert-base-turkish-sentiment-cased",
        }

    @classmethod
    def _get_pipeline(cls) -> Any | None:
        if cls._pipeline is not None:
            return cls._pipeline
        if cls._pipeline_load_attempted:
            return None
        cls._pipeline_load_attempted = True
        try:  # pragma: no cover - real model availability is environment-specific
            from transformers import pipeline  # type: ignore

            cls._pipeline = pipeline("text-classification", model="savasy/bert-base-turkish-sentiment-cased")
            return cls._pipeline
        except Exception as exc:
            logger.warning("Could not load toxicity model; keyword-only moderation remains active: %s", exc)
            cls._pipeline = None
            return None

    async def _get_article_or_404(self, db: AsyncSession, article_id: int) -> Article:
        article = await db.get(Article, int(article_id))
        if article is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        return article

    async def _get_moderation_item_or_404(self, db: AsyncSession, moderation_id: int) -> ModerationQueue:
        item = await db.get(ModerationQueue, int(moderation_id))
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moderation item not found")
        return item

    async def _write_audit_log(
        self,
        db: AsyncSession,
        reviewer_id: int | str,
        action: str,
        item: ModerationQueue,
        details: dict[str, Any],
    ) -> None:
        db.add(
            AuditLog(
                action=action,
                resource_type="moderation_queue",
                resource_id=str(item.id),
                details={**details, "article_id": int(item.article_id), "reviewer_id": str(reviewer_id)},
                created_by=str(reviewer_id),
                created_at=datetime.now(timezone.utc),
            )
        )

    def _queue_item_to_dict(self, item: ModerationQueue) -> dict[str, Any]:
        return {
            "id": int(item.id),
            "article_id": int(item.article_id),
            "toxicity_score": round(self._toxicity_value(item), 4),
            "flagged_reason": item.flagged_reason or item.reason,
            "reason": item.reason,
            "status": item.status,
            "reviewed_by": item.reviewed_by,
            "reviewed_at": _dt_to_iso(item.reviewed_at),
            "created_at": _dt_to_iso(item.created_at),
        }

    @staticmethod
    def _toxicity_value(item: ModerationQueue) -> float:
        value = item.toxicity_score if item.toxicity_score is not None else item.confidence
        return max(0.0, min(1.0, float(value or 0.0)))


def _normalize_pagination(page: int, page_size: int) -> tuple[int, int]:
    return max(int(page or 1), 1), min(max(int(page_size or 20), 1), 100)


def _dt_to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
