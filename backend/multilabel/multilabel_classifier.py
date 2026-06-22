"""Dependency-free multi-label classifier for SmartNewspaper news articles."""

from __future__ import annotations

import math
import re
from typing import Any

from .label_rules import LABEL_KEYWORDS
from .models import ALLOWED_LABELS, MultiLabelConfig, MultiLabelPrediction
from .output_validator import validate_prediction
from .threshold_optimizer import normalize_thresholds

STOPWORDS = {
    "ve", "ile", "bir", "bu", "şu", "o", "da", "de", "ki", "için", "olan", "olarak", "gibi", "son", "yeni", "haber",
    "the", "and", "or", "for", "with", "from", "this", "that", "are", "was", "were", "has", "have", "had", "will", "would", "about", "news",
}


def safe_string(value: Any) -> str:
    """Convert unknown values to strings without raising."""

    return "" if value is None else str(value)


def strip_html(value: Any) -> str:
    """Remove HTML/script/style blocks from article text."""

    text = safe_string(value)
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    return re.sub(r"<[^>]+>", " ", text)


def normalize_text(value: Any) -> str:
    """Normalize text while preserving Turkish characters."""

    text = strip_html(value).replace("I", "ı").replace("İ", "i").lower()
    text = re.sub(r"https?://\S+|www\.\S+", " ", text, flags=re.I)
    text = re.sub(r"[^0-9a-zçğıöşüâîû\s]+", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def keyword_hit(normalized_text: str, normalized_keyword: str) -> bool:
    """Return whether a keyword is present as phrase or token."""

    if not normalized_keyword:
        return False
    if " " in normalized_keyword:
        return normalized_keyword in normalized_text
    return f" {normalized_keyword} " in f" {normalized_text} "


def article_text(article: dict[str, Any] | None) -> str:
    """Build the classifier text from title, summary, content and cluster main article."""

    article = article or {}
    main = article.get("main_article") or article.get("mainArticle") or {}
    fields = (
        article.get("title"),
        article.get("summary"),
        article.get("description"),
        article.get("content"),
        article.get("fullText"),
        article.get("displayTitle"),
        article.get("displaySummary"),
        article.get("originalTitle"),
        article.get("originalSummary"),
        main.get("title") if isinstance(main, dict) else None,
        main.get("summary") if isinstance(main, dict) else None,
        main.get("description") if isinstance(main, dict) else None,
        main.get("content") if isinstance(main, dict) else None,
        main.get("fullText") if isinstance(main, dict) else None,
    )
    return "\n".join(safe_string(field) for field in fields if field)


def sigmoid(logit: float) -> float:
    """Stable sigmoid used for independent label probabilities."""

    if logit >= 40:
        return 1.0
    if logit <= -40:
        return 0.0
    return 1.0 / (1.0 + math.exp(-logit))


class MultiLabelClassifier:
    """Rule-first, ML-ready independent multi-label classifier."""

    def __init__(self, config: MultiLabelConfig | None = None) -> None:
        self.config = config or MultiLabelConfig(per_label_thresholds=normalize_thresholds())
        invalid = set(LABEL_KEYWORDS).difference(self.config.allowed_labels)
        if invalid:
            raise ValueError(f"Unsupported labels in rules: {sorted(invalid)}")

    def raw_rule_scores(self, text: str) -> tuple[dict[str, float], dict[str, list[str]]]:
        """Return unbounded rule scores and matched keywords per allowed label."""

        normalized = normalize_text(text)
        scores: dict[str, float] = {label: 0.0 for label in self.config.allowed_labels}
        hits: dict[str, list[str]] = {label: [] for label in self.config.allowed_labels}
        for label in self.config.allowed_labels:
            for keyword, weight in LABEL_KEYWORDS.get(label, {}).items():
                normalized_keyword = normalize_text(keyword)
                if keyword_hit(normalized, normalized_keyword):
                    scores[label] += float(weight or 1.0)
                    hits[label].append(keyword)
        return scores, hits

    def probability_scores(self, text: str) -> dict[str, float]:
        """Convert rule scores to independent sigmoid-like label probabilities."""

        raw_scores, hits = self.raw_rule_scores(text)
        probabilities: dict[str, float] = {}
        text_length_bonus = min(0.25, len(normalize_text(text)) / 700)
        for label in self.config.allowed_labels:
            score = raw_scores[label]
            hit_bonus = min(0.35, len(hits[label]) * 0.08)
            logit = -2.65 + score * 0.92 + hit_bonus + text_length_bonus
            probabilities[label] = round(sigmoid(logit), 4)
        return probabilities

    def classify(self, article: dict[str, Any] | None) -> MultiLabelPrediction:
        """Classify one article and return a validated multi-label prediction."""

        text = article_text(article)
        normalized = normalize_text(text)
        if len(normalized) < self.config.min_text_length:
            return validate_prediction({
                "labels": [],
                "label_scores": {label: 0.0 for label in self.config.allowed_labels},
                "is_multilabel_reliable": False,
                "label_source": "fallback",
                "fallback_category": (article or {}).get("category") or "Diğer",
            })

        scores = self.probability_scores(text)
        labels = [
            label
            for label in self.config.allowed_labels
            if scores[label] >= self.config.threshold_for(label)
        ]
        # Conservative precision guard: weak one-hit labels must be clearly above threshold.
        raw_scores, hits = self.raw_rule_scores(text)
        labels = [
            label
            for label in labels
            if raw_scores[label] >= 1.25 or len(hits[label]) >= 2 or scores[label] >= 0.72
        ]
        reliable = bool(labels) and max(scores[label] for label in labels) >= self.config.reliable_threshold
        return validate_prediction({
            "labels": labels,
            "label_scores": scores,
            "is_multilabel_reliable": reliable,
            "label_source": "keyword",
            "fallback_category": None if labels else (article or {}).get("category") or "Diğer",
        })

    def classify_many(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Attach multi-label fields to a batch of article dictionaries."""

        output: list[dict[str, Any]] = []
        for article in articles:
            enriched = dict(article or {})
            enriched.update(self.classify(enriched).to_dict())
            output.append(enriched)
        return output


def classify_article(article: dict[str, Any] | None) -> dict[str, Any]:
    """Convenience wrapper returning a JSON-serializable prediction."""

    return MultiLabelClassifier().classify(article).to_dict()


def classify_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convenience wrapper for batch classification."""

    return MultiLabelClassifier().classify_many(articles)
