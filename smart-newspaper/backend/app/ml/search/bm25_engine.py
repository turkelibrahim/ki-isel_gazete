"""Turkish-aware Okapi BM25 search engine for news articles.

The engine keeps an in-memory BM25 index for duplicate-free articles.  It uses
``rank_bm25.BM25Okapi`` when available and falls back to a small compatible
implementation so the application can still import and run in minimal test
environments.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised when dependency is installed in target env
    from rank_bm25 import BM25Okapi as _RankBM25Okapi
except Exception:  # pragma: no cover - fallback is tested in this sandbox
    _RankBM25Okapi = None


TR_STOPS: set[str] = {
    "ve",
    "veya",
    "ile",
    "bir",
    "bu",
    "şu",
    "o",
    "da",
    "de",
    "mi",
    "mı",
    "için",
    "olarak",
    "olan",
    "gibi",
    "çok",
    "daha",
    "sonra",
}


class _SimpleBM25Okapi:
    """Small BM25Okapi-compatible fallback used when rank-bm25 is unavailable."""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        """Build document frequencies and average document length."""
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.doc_freqs = [Counter(doc) for doc in corpus]
        self.doc_len = [len(doc) for doc in corpus]
        self.avgdl = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0.0
        self.idf = self._calculate_idf(corpus)

    def _calculate_idf(self, corpus: list[list[str]]) -> dict[str, float]:
        """Return BM25 IDF values with standard smoothing."""
        n_docs = len(corpus)
        df: Counter[str] = Counter()
        for doc in corpus:
            df.update(set(doc))
        return {term: math.log(1 + (n_docs - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        """Return BM25 scores for each document."""
        if not query_tokens or not self.corpus:
            return [0.0 for _ in self.corpus]
        scores: list[float] = []
        for doc_index, freqs in enumerate(self.doc_freqs):
            doc_len = self.doc_len[doc_index] or 1
            score = 0.0
            for term in query_tokens:
                term_freq = freqs.get(term, 0)
                if term_freq <= 0:
                    continue
                idf = self.idf.get(term, 0.0)
                denom = term_freq + self.k1 * (1 - self.b + self.b * doc_len / (self.avgdl or 1.0))
                score += idf * (term_freq * (self.k1 + 1)) / denom
            scores.append(float(score))
        return scores


class BM25Engine:
    """Singleton in-memory BM25 index with a Turkish-friendly tokenizer."""

    _instance: "BM25Engine | None" = None
    _instance_lock = RLock()

    def __new__(cls) -> "BM25Engine":
        """Return a single process-local BM25 engine instance."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        """Initialize mutable index state once."""
        if getattr(self, "_initialized", False):
            return
        self._lock = RLock()
        self.bm25: Any | None = None
        self.article_ids: list[int] = []
        self.tokenized_corpus: list[list[str]] = []
        self.last_rebuild_at: datetime | None = None
        self.is_ready = False
        self._initialized = True

    def tokenize(self, text: str) -> list[str]:
        """Tokenize Turkish text while preserving Turkish characters."""
        normalized = re.sub(r"[^\w\sçğıöşüÇĞİÖŞÜ]", " ", (text or "").lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        tokens = [token for token in normalized.split(" ") if len(token) >= 2 and token not in TR_STOPS]
        return tokens

    async def rebuild(self, db: AsyncSession) -> dict[str, Any]:
        """Rebuild the BM25 index from duplicate-free articles."""
        try:
            result = await db.execute(select(Article).where(Article.is_duplicate.is_(False)).order_by(Article.id.asc()))
            articles = list(result.scalars().all())
            tokenized: list[list[str]] = []
            ids: list[int] = []
            for article in articles:
                text = _article_index_text(article)
                tokens = self.tokenize(text)
                if not tokens:
                    continue
                tokenized.append(tokens)
                ids.append(int(article.id))

            with self._lock:
                self.tokenized_corpus = tokenized
                self.article_ids = ids
                bm25_cls = _RankBM25Okapi or _SimpleBM25Okapi
                self.bm25 = bm25_cls(tokenized, k1=1.5, b=0.75) if tokenized else None
                self.last_rebuild_at = datetime.now(timezone.utc)
                self.is_ready = bool(tokenized)

            logger.info("BM25 index rebuilt indexed_articles=%s", len(ids))
            return {
                "indexed_articles": len(ids),
                "last_rebuild_at": self.last_rebuild_at.isoformat(),
                "is_ready": self.is_ready,
                "tokenizer_language": "tr",
            }
        except Exception:
            logger.exception("BM25 index rebuild failed")
            raise

    def search(self, query: str, top_n: int = 20, min_score: float = 0.01) -> list[dict[str, Any]]:
        """Search the in-memory index and return article ids with BM25 scores."""
        tokens = self.tokenize(query)
        if not tokens:
            return []
        with self._lock:
            if self.bm25 is None or not self.article_ids:
                return []
            scores = list(self.bm25.get_scores(tokens))
            scored = [
                {"article_id": self.article_ids[index], "score": float(score)}
                for index, score in enumerate(scores)
                if float(score) >= min_score
            ]
        scored.sort(key=lambda item: item["score"], reverse=True)
        return [dict(item, rank=rank) for rank, item in enumerate(scored[: max(1, top_n)], start=1)]

    def add_or_update_article(self, article_id: int, text: str) -> None:
        """Add or update one article and rebuild the in-memory index from current corpus."""
        tokens = self.tokenize(text)
        if not tokens:
            return
        with self._lock:
            if article_id in self.article_ids:
                index = self.article_ids.index(article_id)
                self.tokenized_corpus[index] = tokens
            else:
                self.article_ids.append(article_id)
                self.tokenized_corpus.append(tokens)
            bm25_cls = _RankBM25Okapi or _SimpleBM25Okapi
            self.bm25 = bm25_cls(self.tokenized_corpus, k1=1.5, b=0.75)
            self.last_rebuild_at = datetime.now(timezone.utc)
            self.is_ready = True

    def clear(self) -> None:
        """Clear all in-memory BM25 state."""
        with self._lock:
            self.bm25 = None
            self.article_ids = []
            self.tokenized_corpus = []
            self.last_rebuild_at = None
            self.is_ready = False

    def status(self) -> dict[str, Any]:
        """Return transparent index status metadata."""
        with self._lock:
            return {
                "indexed_articles": len(self.article_ids),
                "last_rebuild_at": self.last_rebuild_at.isoformat() if self.last_rebuild_at else None,
                "is_ready": self.is_ready,
                "tokenizer_language": "tr",
            }


def _article_index_text(article: Article) -> str:
    """Return the canonical search text for an Article row."""
    return " ".join(
        [
            getattr(article, "title", "") or "",
            getattr(article, "summary", "") or "",
            (getattr(article, "content", "") or "")[:500],
        ]
    )
