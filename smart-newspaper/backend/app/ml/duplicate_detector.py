"""MinHash + LSH duplicate detection for crawled news articles.

The detector keeps a lightweight in-memory LSH index of canonical, non-duplicate
articles. New articles are converted to 5-character shingles, represented as a
128-permutation MinHash signature, queried against the LSH index, then verified
with exact Jaccard similarity before being marked as duplicates.

``datasketch`` is the production implementation. If the optional dependency is
not installed yet, the service degrades safely by returning ``duplicate=False``
instead of crashing the ingestion pipeline.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article

try:  # Optional at import time so the app can still boot before pip install.
    from datasketch import MinHash, MinHashLSH
except ImportError:  # pragma: no cover - exercised only before dependency install
    MinHash = None  # type: ignore[assignment]
    MinHashLSH = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

NUM_PERM = 128
LSH_THRESHOLD = 0.8
JACCARD_THRESHOLD = 0.8
SHINGLE_K = 5


@dataclass(frozen=True)
class DuplicateResult:
    """Structured result returned by ``DuplicateDetector.is_duplicate``."""

    is_duplicate: bool
    matched_article_id: int | None = None
    score: float = 0.0
    candidates: list[int] | None = None


class DuplicateDetector:
    """Singleton MinHash/LSH detector for near-duplicate news articles."""

    _instance: ClassVar["DuplicateDetector | None"] = None

    def __new__(cls) -> "DuplicateDetector":
        """Return the shared singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the LSH index once per process."""
        if self._initialized:
            return
        self._minhashes: dict[int, Any] = {}
        self._shingles_by_id: dict[int, set[str]] = {}
        self._lsh: Any | None = None
        self._initialized = True
        self._reset_lsh()

    def clear(self) -> None:
        """Clear the in-memory index and all article mappings."""
        self._minhashes.clear()
        self._shingles_by_id.clear()
        self._reset_lsh()

    def normalize_text(self, text: str) -> str:
        """Normalize punctuation, case, and whitespace before shingling."""
        normalized = re.sub(r"[^\w\s]", "", (text or "").lower().strip())
        return re.sub(r"\s+", " ", normalized).strip()

    def create_shingles(self, text: str, k: int = SHINGLE_K) -> set[str]:
        """Create a set of k-character shingles using k=5 by default.

        k=5 is a balanced choice for news text: shorter shingles are too loose,
        while much longer shingles can miss near-identical articles with small
        wording changes.
        """
        normalized = self.normalize_text(text)
        if len(normalized) < k:
            return set()
        return {normalized[i : i + k] for i in range(len(normalized) - k + 1)}

    def create_minhash(self, shingles: set[str]) -> Any | None:
        """Create a 128-permutation MinHash signature from shingle strings."""
        if not shingles or MinHash is None:
            return None

        signature = MinHash(num_perm=NUM_PERM)
        for shingle in shingles:
            signature.update(shingle.encode("utf-8"))
        return signature

    def is_duplicate(self, text: str) -> DuplicateResult:
        """Return whether text is a near duplicate of an indexed article.

        The LSH query produces candidates first; exact Jaccard similarity is then
        computed on shingles to prevent false-positive duplicate labels.
        """
        try:
            if self._lsh is None:
                logger.warning("datasketch is not installed; duplicate detection is disabled")
                return DuplicateResult(is_duplicate=False, candidates=[])

            shingles = self.create_shingles(text)
            minhash = self.create_minhash(shingles)
            if minhash is None:
                return DuplicateResult(is_duplicate=False, candidates=[])

            candidate_keys = self._lsh.query(minhash)
            candidate_ids = [self._parse_article_key(key) for key in candidate_keys]
            candidate_ids = [article_id for article_id in candidate_ids if article_id is not None]

            best_id: int | None = None
            best_score = 0.0
            for article_id in candidate_ids:
                score = self._jaccard(shingles, self._shingles_by_id.get(article_id, set()))
                if score > best_score:
                    best_score = score
                    best_id = article_id

            if best_id is not None and best_score >= JACCARD_THRESHOLD:
                return DuplicateResult(
                    is_duplicate=True,
                    matched_article_id=best_id,
                    score=best_score,
                    candidates=candidate_ids,
                )

            return DuplicateResult(is_duplicate=False, score=best_score, candidates=candidate_ids)
        except Exception:
            logger.exception("Duplicate detection failed; falling back to duplicate=False")
            return DuplicateResult(is_duplicate=False, candidates=[])

    def add(self, article_id: int, text: str) -> bool:
        """Add a non-duplicate article to the in-memory LSH index.

        Returns ``True`` when the article was indexed, otherwise ``False``.
        """
        try:
            if self._lsh is None:
                logger.warning("datasketch is not installed; article %s was not indexed", article_id)
                return False

            shingles = self.create_shingles(text)
            minhash = self.create_minhash(shingles)
            if minhash is None:
                return False

            key = self._article_key(article_id)
            if article_id in self._minhashes:
                return True

            self._lsh.insert(key, minhash)
            self._minhashes[article_id] = minhash
            self._shingles_by_id[article_id] = shingles
            return True
        except Exception:
            logger.exception("Could not add article_id=%s to duplicate LSH index", article_id)
            return False

    async def load_from_db(self, db: AsyncSession) -> int:
        """Load existing non-duplicate articles from the database into LSH.

        Only ``title + content[:500]`` is indexed so startup remains bounded even
        when articles contain large full text bodies.
        """
        self.clear()
        loaded = 0
        try:
            result = await db.execute(
                select(Article).where(Article.is_duplicate.is_(False)).order_by(Article.id.asc())
            )
            for article in result.scalars().all():
                text = f"{article.title} {str(article.content or '')[:500]}"
                if self.add(int(article.id), text):
                    loaded += 1
            logger.info("Loaded %s non-duplicate articles into MinHash LSH index", loaded)
            return loaded
        except Exception:
            logger.exception("Could not load duplicate detector index from database")
            return loaded

    def serialize_minhash(self, minhash: Any | None) -> bytes | None:
        """Serialize a datasketch MinHash signature for ``articles.minhash_signature``."""
        if minhash is None:
            return None
        try:
            return minhash.hashvalues.tobytes()
        except Exception:
            logger.exception("Could not serialize MinHash signature")
            return None

    def build_signature_for_text(self, text: str) -> bytes | None:
        """Build serialized MinHash bytes for a text without inserting it."""
        try:
            shingles = self.create_shingles(text)
            return self.serialize_minhash(self.create_minhash(shingles))
        except Exception:
            logger.exception("Could not build MinHash signature for text")
            return None

    def _reset_lsh(self) -> None:
        """Recreate the LSH object using threshold=0.8 and num_perm=128."""
        if MinHashLSH is None:
            self._lsh = None
            return
        self._lsh = MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)

    def _jaccard(self, left: set[str], right: set[str]) -> float:
        """Compute exact Jaccard similarity for candidate verification."""
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    def _article_key(self, article_id: int) -> str:
        """Create an LSH key for an article id."""
        return f"art_{article_id}"

    def _parse_article_key(self, key: str) -> int | None:
        """Parse an article id from an LSH key like ``art_123``."""
        try:
            return int(str(key).replace("art_", "", 1))
        except (TypeError, ValueError):
            logger.warning("Invalid LSH article key: %r", key)
            return None
