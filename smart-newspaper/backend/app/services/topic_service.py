"""Topic modeling service for Module 7 Analytics & Recommendation."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.topic_model import TopicModel, summarize_topics_from_texts
from app.models import Article, Source, UserEvent
from app.services.trending_service import TrendingService

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BACKEND_DIR / "models" / "topics"
TOPIC_MODEL_PATH = MODEL_DIR / "topic_model.pkl"


class TopicService:
    """Train, load and query article topic models."""

    def __init__(self, model_path: str | Path = TOPIC_MODEL_PATH) -> None:
        """Initialize topic service with a persisted model path."""
        self.model_path = Path(model_path)
        self.model = TopicModel()
        self._loaded = False

    async def train_topics(self, db: AsyncSession, limit: int = 5000) -> dict[str, Any]:
        """Train LDA topics from non-duplicate articles and persist the model."""
        documents = await self._load_article_documents(db, limit=limit)
        result = self.model.train(documents)
        if result.get("trained"):
            try:
                self.model.save(self.model_path)
                self._loaded = True
                result["model_path"] = str(self.model_path.relative_to(BACKEND_DIR))
            except Exception:
                logger.exception("Topic model trained but could not be saved")
                result["saved"] = False
        else:
            result["model_path"] = str(self.model_path.relative_to(BACKEND_DIR))
        return result

    async def get_topics(self, db: AsyncSession, limit: int = 20) -> list[dict[str, Any]]:
        """Return trained topics or a safe keyword fallback when no model exists."""
        if self._ensure_loaded():
            return self.model.get_topics()[: max(1, min(limit, 100))]
        documents = await self._load_article_documents(db, limit=1000)
        return summarize_topics_from_texts([doc["text"] for doc in documents], top_n=max(1, min(limit, 100)))

    async def get_article_topics(self, db: AsyncSession, article_id: int) -> dict[str, Any]:
        """Return topic distribution for one article."""
        if self._ensure_loaded() and int(article_id) in self.model.article_topics:
            return {"article_id": int(article_id), "topics": self.model.article_topics[int(article_id)], "source": "trained-model"}
        article = (await db.execute(select(Article).where(Article.id == article_id))).scalar_one_or_none()
        if article is None:
            return {"article_id": int(article_id), "topics": [], "source": "not-found"}
        if self._ensure_loaded():
            text = self._article_text(article)
            return {"article_id": int(article_id), "topics": self.model.infer_article_topics(text), "source": "inference"}
        return {"article_id": int(article_id), "topics": [], "source": "no-model"}

    async def get_trending_topics(self, db: AsyncSession, days: int = 7, limit: int = 10) -> list[dict[str, Any]]:
        """Aggregate trending scores by topic for recent articles."""
        safe_days = max(1, min(days, 30))
        safe_limit = max(1, min(limit, 50))
        since = datetime.now(timezone.utc) - timedelta(days=safe_days)
        stmt = (
            select(Article)
            .where(Article.is_duplicate.is_(False), Article.published_at >= since)
            .order_by(desc(Article.published_at))
            .limit(1000)
        )
        articles = list((await db.execute(stmt)).scalars().all())
        if not articles:
            return []

        self._ensure_loaded()
        score_by_topic: dict[int, float] = defaultdict(float)
        article_count_by_topic: dict[int, int] = defaultdict(int)
        labels_by_topic = {int(topic["topic_id"]): topic.get("label") for topic in self.model.get_topics()} if self.model.is_trained else {}
        trending_service = TrendingService()
        for article in articles:
            topics = self.model.article_topics.get(int(article.id), []) if self.model.is_trained else []
            if not topics and self.model.is_trained:
                topics = self.model.infer_article_topics(self._article_text(article), top_n=3)
            if not topics:
                continue
            trend_score = trending_service.calculate_trend_score(article)
            for topic in topics[:3]:
                topic_id = int(topic.get("topic_id", 0))
                topic_score = float(topic.get("score", 0.0))
                score_by_topic[topic_id] += trend_score * topic_score
                article_count_by_topic[topic_id] += 1
        ranked = sorted(score_by_topic.items(), key=lambda item: item[1], reverse=True)[:safe_limit]
        return [
            {
                "topic_id": topic_id,
                "label": labels_by_topic.get(topic_id, f"Konu {topic_id}"),
                "trend_score": round(float(score), 4),
                "article_count": int(article_count_by_topic.get(topic_id, 0)),
            }
            for topic_id, score in ranked
        ]

    def get_status(self) -> dict[str, Any]:
        """Return topic model file and configuration status."""
        self._ensure_loaded()
        status = self.model._status()  # Keep all PDF-guide diagnostics in one place.
        status.update(
            {
                "model_path": str(self.model_path.relative_to(BACKEND_DIR)),
                "model_exists": self.model_path.exists(),
                "endpoints": [
                    "POST /api/topics/train",
                    "GET /api/topics",
                    "GET /api/topics/trending",
                    "GET /api/topics/article/{article_id}",
                    "GET /api/topics/status",
                ],
            }
        )
        return status

    async def _load_article_documents(self, db: AsyncSession, limit: int = 5000) -> list[dict[str, Any]]:
        """Load non-duplicate articles as topic-model documents."""
        safe_limit = max(10, min(limit, 20000))
        stmt = (
            select(Article)
            .where(Article.is_duplicate.is_(False))
            .order_by(desc(Article.published_at))
            .limit(safe_limit)
        )
        articles = list((await db.execute(stmt)).scalars().all())
        return [{"article_id": int(article.id), "text": self._article_text(article)} for article in articles]

    def _article_text(self, article: Article) -> str:
        """Create the topic-model article text."""
        return " ".join(
            part for part in [article.title, article.summary or "", (article.content or "")[:1000]] if part
        )

    def _ensure_loaded(self) -> bool:
        """Lazy-load the model once from disk."""
        if self._loaded:
            return self.model.is_trained
        self._loaded = True
        if self.model_path.exists():
            return self.model.load(self.model_path)
        return False


topic_service = TopicService()
