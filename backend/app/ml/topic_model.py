"""LDA topic modeling for Module 7 Analytics & Recommendation.

The implementation uses gensim when available, but keeps a controlled fallback so
FastAPI can still boot on systems where the heavy NLP dependency is not yet
installed.
"""

from __future__ import annotations

import logging
import math
import pickle
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:  # Optional dependency. Do not break backend imports when missing.
    from gensim import corpora
    from gensim.models import CoherenceModel, LdaModel
except Exception:  # pragma: no cover - environment dependent
    corpora = None  # type: ignore[assignment]
    CoherenceModel = None  # type: ignore[assignment]
    LdaModel = None  # type: ignore[assignment]

TR_TOPIC_STOPS: set[str] = {
    "ve", "veya", "ile", "bir", "bu", "şu", "o", "da", "de", "mi", "mı",
    "için", "olarak", "olan", "gibi", "çok", "daha", "sonra", "son", "ilk",
    "en", "ama", "ancak", "ise", "olan", "oldu", "olacak", "var", "yok",
    "haber", "haberi", "açıklandı", "dedi", "göre", "üzere", "karşı",
}


class TopicModel:
    """Train and serve a gensim LDA topic model.

    Required algorithm defaults are preserved:
    - num_topics=20
    - passes=15
    - alpha="auto"
    - eta="auto"
    - Dictionary.filter_extremes(no_below=5, no_above=0.5)
    - CoherenceModel(coherence="c_v")
    """

    NUM_TOPICS = 20
    PASSES = 15
    NO_BELOW = 5
    NO_ABOVE = 0.5
    COHERENCE_TARGET = 0.4

    def __init__(self) -> None:
        """Initialize an empty topic model wrapper."""
        self.dictionary: Any | None = None
        self.model: Any | None = None
        self.article_topics: dict[int, list[dict[str, float]]] = {}
        self.topic_words: list[dict[str, Any]] = []
        self.coherence: float | None = None
        self.trained_at: str | None = None
        self.last_error: str | None = None

    @property
    def is_available(self) -> bool:
        """Return True when gensim objects are importable."""
        return corpora is not None and LdaModel is not None

    @property
    def is_trained(self) -> bool:
        """Return True when an LDA model is available in memory."""
        return self.model is not None and self.dictionary is not None

    def tokenize(self, text: str) -> list[str]:
        """Tokenize Turkish-compatible text for topic modeling."""
        cleaned = re.sub(r"[^\w\sçğıöşüÇĞİÖŞÜ]", " ", (text or "").lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return [token for token in cleaned.split() if len(token) > 2 and not token.isdigit() and token not in TR_TOPIC_STOPS]

    def train(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        """Train LDA topics from article documents.

        Args:
            documents: Items with ``article_id`` and ``text`` keys.

        Returns:
            Training status, topic list, coherence and diagnostics.
        """
        self.last_error = None
        if not self.is_available:
            self.last_error = "gensim-not-installed"
            logger.warning("Topic training skipped because gensim is not installed")
            return self._status(trained=False, reason=self.last_error, document_count=len(documents))

        article_ids: list[int] = []
        tokenized_docs: list[list[str]] = []
        for item in documents:
            try:
                article_id = int(item["article_id"])
                tokens = self.tokenize(str(item.get("text") or ""))
                if tokens:
                    article_ids.append(article_id)
                    tokenized_docs.append(tokens)
            except Exception:
                logger.warning("Skipping invalid topic document: %s", item, exc_info=True)

        if len(tokenized_docs) < 5:
            self.last_error = "insufficient-documents"
            return self._status(trained=False, reason=self.last_error, document_count=len(tokenized_docs))

        try:
            dictionary = corpora.Dictionary(tokenized_docs)
            original_token_count = len(dictionary)
            # Required PDF-guide filtering settings.
            dictionary.filter_extremes(no_below=self.NO_BELOW, no_above=self.NO_ABOVE)
            if len(dictionary) == 0:
                # Keep the required call above, but recover safely for small local/dev datasets.
                logger.warning(
                    "LDA dictionary became empty after filter_extremes(no_below=%s, no_above=%s); using relaxed fallback for small dataset",
                    self.NO_BELOW,
                    self.NO_ABOVE,
                )
                dictionary = corpora.Dictionary(tokenized_docs)
                dictionary.filter_extremes(no_below=1, no_above=0.95)

            corpus = [dictionary.doc2bow(tokens) for tokens in tokenized_docs]
            corpus = [bow for bow in corpus if bow]
            if not corpus or len(dictionary) == 0:
                self.last_error = "empty-corpus-after-filtering"
                return self._status(trained=False, reason=self.last_error, document_count=len(tokenized_docs))

            num_topics = min(self.NUM_TOPICS, max(1, len(dictionary)))
            lda = LdaModel(
                corpus=corpus,
                id2word=dictionary,
                num_topics=num_topics,
                passes=self.PASSES,
                alpha="auto",
                eta="auto",
                random_state=42,
            )
            coherence = self._calculate_coherence(lda, tokenized_docs, dictionary)
            self.dictionary = dictionary
            self.model = lda
            self.coherence = coherence
            self.trained_at = datetime.now(timezone.utc).isoformat()
            self.topic_words = self._extract_topic_words(lda, num_topics)
            self.article_topics = self._assign_article_topics(article_ids, corpus)
            return self._status(
                trained=True,
                reason="trained",
                document_count=len(tokenized_docs),
                original_token_count=original_token_count,
                dictionary_size=len(dictionary),
                corpus_size=len(corpus),
                num_topics=num_topics,
            )
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("Topic model training failed")
            return self._status(trained=False, reason=self.last_error, document_count=len(tokenized_docs))

    def infer_article_topics(self, text: str, top_n: int = 5) -> list[dict[str, float]]:
        """Infer topic probabilities for a new article text."""
        if not self.is_trained:
            return []
        try:
            bow = self.dictionary.doc2bow(self.tokenize(text))
            if not bow:
                return []
            topics = self.model.get_document_topics(bow, minimum_probability=0.0)
            ranked = sorted(topics, key=lambda item: item[1], reverse=True)[:top_n]
            return [{"topic_id": int(topic_id), "score": round(float(score), 6)} for topic_id, score in ranked]
        except Exception:
            logger.exception("Topic inference failed")
            return []

    def get_topics(self, top_n: int = 10) -> list[dict[str, Any]]:
        """Return model topics with top words."""
        if self.topic_words:
            return self.topic_words
        if not self.is_trained:
            return []
        self.topic_words = self._extract_topic_words(self.model, self.model.num_topics, top_n=top_n)
        return self.topic_words

    def save(self, path: str | Path) -> None:
        """Persist model wrapper state with pickle."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "dictionary": self.dictionary,
            "model": self.model,
            "article_topics": self.article_topics,
            "topic_words": self.topic_words,
            "coherence": self.coherence,
            "trained_at": self.trained_at,
            "last_error": self.last_error,
        }
        with target.open("wb") as fh:
            pickle.dump(payload, fh)

    def load(self, path: str | Path) -> bool:
        """Load model wrapper state if present."""
        source = Path(path)
        if not source.exists():
            return False
        try:
            with source.open("rb") as fh:
                payload = pickle.load(fh)
            self.dictionary = payload.get("dictionary")
            self.model = payload.get("model")
            self.article_topics = payload.get("article_topics", {})
            self.topic_words = payload.get("topic_words", [])
            self.coherence = payload.get("coherence")
            self.trained_at = payload.get("trained_at")
            self.last_error = payload.get("last_error")
            return self.is_trained
        except Exception:
            logger.exception("Could not load topic model from %s", source)
            return False

    def _calculate_coherence(self, model: Any, texts: list[list[str]], dictionary: Any) -> float | None:
        """Calculate c_v coherence and return None on failure."""
        if CoherenceModel is None:
            return None
        try:
            coherence_model = CoherenceModel(model=model, texts=texts, dictionary=dictionary, coherence="c_v")
            value = coherence_model.get_coherence()
            return round(float(value), 6) if value is not None and not math.isnan(float(value)) else None
        except Exception:
            logger.warning("Could not calculate c_v coherence", exc_info=True)
            return None

    def _extract_topic_words(self, model: Any, num_topics: int, top_n: int = 10) -> list[dict[str, Any]]:
        """Extract top words for each topic."""
        topics: list[dict[str, Any]] = []
        for topic_id in range(num_topics):
            words = [
                {"word": str(word), "weight": round(float(weight), 6)}
                for word, weight in model.show_topic(topic_id, topn=top_n)
            ]
            label = ", ".join(item["word"] for item in words[:3]) if words else f"Konu {topic_id}"
            topics.append({"topic_id": topic_id, "label": label, "words": words})
        return topics

    def _assign_article_topics(self, article_ids: list[int], corpus: list[Any], top_n: int = 5) -> dict[int, list[dict[str, float]]]:
        """Map article IDs to their strongest topics."""
        mapping: dict[int, list[dict[str, float]]] = {}
        for article_id, bow in zip(article_ids, corpus, strict=False):
            try:
                topics = self.model.get_document_topics(bow, minimum_probability=0.0)
                ranked = sorted(topics, key=lambda item: item[1], reverse=True)[:top_n]
                mapping[int(article_id)] = [
                    {"topic_id": int(topic_id), "score": round(float(score), 6)} for topic_id, score in ranked
                ]
            except Exception:
                logger.warning("Could not assign topics article_id=%s", article_id, exc_info=True)
        return mapping

    def _status(self, **extra: Any) -> dict[str, Any]:
        """Return current topic model diagnostics."""
        payload = {
            "available": self.is_available,
            "is_trained": self.is_trained,
            "num_topics_config": self.NUM_TOPICS,
            "passes": self.PASSES,
            "alpha": "auto",
            "eta": "auto",
            "filter_extremes": {"no_below": self.NO_BELOW, "no_above": self.NO_ABOVE},
            "coherence_method": "c_v",
            "coherence": self.coherence,
            "coherence_target": self.COHERENCE_TARGET,
            "coherence_target_met": self.coherence is not None and self.coherence > self.COHERENCE_TARGET,
            "trained_at": self.trained_at,
            "last_error": self.last_error,
            "topic_count": len(self.topic_words),
            "article_topic_count": len(self.article_topics),
        }
        payload.update(extra)
        return payload


def summarize_topics_from_texts(texts: list[str], top_n: int = 20) -> list[dict[str, Any]]:
    """Fallback keyword-topic summary when gensim is unavailable."""
    model = TopicModel()
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(model.tokenize(text))
    return [
        {"topic_id": idx, "label": word, "words": [{"word": word, "weight": float(count)}]}
        for idx, (word, count) in enumerate(counter.most_common(top_n))
    ]
