"""TF-IDF + RAKE + YAKE ensemble keyword extraction."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import ClassVar

from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

TFIDF_WEIGHT = 0.40
RAKE_WEIGHT = 0.30
YAKE_WEIGHT = 0.30

TURKISH_STOP_WORDS = {
    "acaba", "ama", "ancak", "artık", "asla", "aslında", "az", "bazı", "belki", "biri", "birkaç",
    "birşey", "biz", "bu", "çok", "çünkü", "da", "daha", "de", "defa", "diye", "eğer", "en", "gibi",
    "hem", "hep", "hepsi", "her", "hiç", "için", "ile", "ise", "kez", "ki", "kim", "mı", "mu", "mü",
    "nasıl", "ne", "neden", "nerde", "nerede", "nereye", "niçin", "niye", "o", "sanki", "şey", "siz",
    "şu", "tüm", "ve", "veya", "ya", "yani", "yine",
}


class KeywordExtractor:
    """Singleton keyword extractor combining TF-IDF, RAKE and YAKE scores."""

    _instance: ClassVar["KeywordExtractor | None"] = None

    def __new__(cls) -> "KeywordExtractor":
        """Return one shared extractor instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def extract_tfidf(self, text: str) -> list[tuple[str, float]]:
        """Extract top keyword candidates using single-document TF-IDF."""
        cleaned = self._normalize_document(text)
        if len(cleaned) < 20:
            return []
        try:
            vectorizer = TfidfVectorizer(
                max_features=50000,
                ngram_range=(1, 3),
                sublinear_tf=True,
                stop_words=list(TURKISH_STOP_WORDS),
            )
            matrix = vectorizer.fit_transform([cleaned])
            names = vectorizer.get_feature_names_out()
            scores = matrix.toarray()[0]
            ranked = sorted(zip(names, scores, strict=False), key=lambda item: float(item[1]), reverse=True)
            return self._normalize_scores([(term, float(score)) for term, score in ranked[:50]])
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("TF-IDF keyword extraction failed: %s", exc)
            return []

    def extract_rake(self, text: str) -> list[tuple[str, float]]:
        """Extract phrase candidates with RAKE, falling back to simple phrases."""
        cleaned = self._normalize_document(text)
        if len(cleaned) < 20:
            return []
        try:
            from rake_nltk import Rake  # type: ignore

            rake = Rake(stopwords=TURKISH_STOP_WORDS, min_length=1, max_length=8)
            rake.extract_keywords_from_text(cleaned)
            items = [(phrase, float(score)) for score, phrase in rake.get_ranked_phrases_with_scores()[:50]]
            return self._normalize_scores(items)
        except Exception as exc:
            logger.warning("RAKE unavailable or failed, using fallback phrase extraction: %s", exc)
            return self._extract_rake_fallback(cleaned)

    def extract_yake(self, text: str) -> list[tuple[str, float]]:
        """Extract keyword candidates with YAKE and invert its lower-is-better score."""
        cleaned = self._normalize_document(text)
        if len(cleaned) < 20:
            return []
        try:
            import yake  # type: ignore

            extractor = yake.KeywordExtractor(lan="tr", n=3, top=30)
            keywords = extractor.extract_keywords(cleaned)
            items = [(keyword, 1.0 / (1.0 + float(score))) for keyword, score in keywords]
            return self._normalize_scores(items)
        except Exception as exc:
            logger.warning("YAKE unavailable or failed, using fallback keyword scoring: %s", exc)
            return self._extract_yake_fallback(cleaned)

    def extract(self, text: str, top_n: int = 15) -> list[dict[str, float | str]]:
        """Return the top ensemble-scored keywords or phrases."""
        if not text or len(text.strip()) < 20:
            return []

        buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"tfidf": 0.0, "rake": 0.0, "yake": 0.0})
        for keyword, score in self.extract_tfidf(text):
            clean = self._clean_keyword(keyword)
            if clean:
                buckets[clean]["tfidf"] = max(buckets[clean]["tfidf"], score)
        for keyword, score in self.extract_rake(text):
            clean = self._clean_keyword(keyword)
            if clean:
                buckets[clean]["rake"] = max(buckets[clean]["rake"], score)
        for keyword, score in self.extract_yake(text):
            clean = self._clean_keyword(keyword)
            if clean:
                buckets[clean]["yake"] = max(buckets[clean]["yake"], score)

        results: list[dict[str, float | str]] = []
        for keyword, scores in buckets.items():
            final_score = (
                TFIDF_WEIGHT * scores["tfidf"]
                + RAKE_WEIGHT * scores["rake"]
                + YAKE_WEIGHT * scores["yake"]
            )
            if final_score > 0:
                results.append({"keyword": keyword, "score": float(final_score)})

        results.sort(key=lambda item: float(item["score"]), reverse=True)
        return results[: max(1, top_n)]

    def _normalize_document(self, text: str) -> str:
        """Normalize whitespace while preserving Turkish characters."""
        return re.sub(r"\s+", " ", (text or "").strip())

    def _clean_keyword(self, keyword: str) -> str | None:
        """Normalize and validate one keyword candidate."""
        clean = re.sub(r"[^\w\sğüşöçıİĞÜŞÖÇ-]", " ", keyword.lower(), flags=re.UNICODE)
        clean = re.sub(r"\s+", " ", clean).strip(" -_")
        if len(clean) < 2 or clean.isdigit():
            return None
        if len(clean.split()) > 8:
            return None
        if clean in TURKISH_STOP_WORDS:
            return None
        return clean

    def _normalize_scores(self, items: list[tuple[str, float]]) -> list[tuple[str, float]]:
        """Normalize positive scores to the 0-1 range and clean duplicates."""
        cleaned: dict[str, float] = {}
        for keyword, score in items:
            clean = self._clean_keyword(keyword)
            if clean is None:
                continue
            cleaned[clean] = max(cleaned.get(clean, 0.0), max(float(score), 0.0))
        if not cleaned:
            return []
        max_score = max(cleaned.values()) or 1.0
        return [(keyword, score / max_score) for keyword, score in cleaned.items()]

    def _extract_rake_fallback(self, text: str) -> list[tuple[str, float]]:
        """Simple RAKE-like phrase scoring when rake-nltk is unavailable."""
        words = [word for word in re.findall(r"[\wğüşöçıİĞÜŞÖÇ]+", text.lower()) if word not in TURKISH_STOP_WORDS]
        phrases: dict[str, float] = defaultdict(float)
        for n in (3, 2, 1):
            for index in range(0, max(0, len(words) - n + 1)):
                phrase_words = words[index : index + n]
                phrase = " ".join(phrase_words)
                if self._clean_keyword(phrase):
                    phrases[phrase] += float(n * n)
        ranked = sorted(phrases.items(), key=lambda item: item[1], reverse=True)[:50]
        return self._normalize_scores(ranked)

    def _extract_yake_fallback(self, text: str) -> list[tuple[str, float]]:
        """Simple position/frequency score when YAKE is unavailable."""
        words = [word for word in re.findall(r"[\wğüşöçıİĞÜŞÖÇ]+", text.lower()) if word not in TURKISH_STOP_WORDS]
        scores: dict[str, float] = defaultdict(float)
        for position, word in enumerate(words):
            if self._clean_keyword(word):
                position_bonus = 1.0 / (1.0 + position / 30.0)
                scores[word] += position_bonus
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:50]
        return self._normalize_scores(ranked)
