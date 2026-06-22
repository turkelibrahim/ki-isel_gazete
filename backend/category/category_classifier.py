"""Automatic category classifier for SmartNewspaper feed articles."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .category_rules import classify_with_rules, normalize_category
from .model_loader import load_category_model
from .models import (
    MIN_CLASSIFIABLE_TEXT_LENGTH,
    RELIABLE_CONFIDENCE_THRESHOLD,
    CategoryPrediction,
    NewsArticle,
    SUPPORTED_CATEGORIES,
)
from .text_cleaner import detect_language, normalize_text


class CategoryClassifier:
    """Hybrid keyword + ML fallback classifier for Turkish and English news."""

    def __init__(self, reliable_threshold: float = RELIABLE_CONFIDENCE_THRESHOLD):
        self.reliable_threshold = reliable_threshold
        self.model = load_category_model()

    def classify(self, article: Mapping[str, Any] | NewsArticle) -> CategoryPrediction:
        """Classify a single article without mutating the input."""

        news_article = article if isinstance(article, NewsArticle) else NewsArticle.from_mapping(article)
        text = news_article.joined_text()
        normalized = normalize_text(text)
        detected_lang = detect_language(text, news_article.language or "unknown")

        if len(normalized) < MIN_CLASSIFIABLE_TEXT_LENGTH:
            return CategoryPrediction(
                category="Diğer",
                category_confidence=0.18 if normalized else 0.0,
                category_source="fallback",
                is_category_reliable=False,
                detected_lang=detected_lang,
                scores={},
            )

        rule_match = classify_with_rules(text)
        if rule_match.confidence >= self.reliable_threshold:
            return CategoryPrediction(
                category=normalize_category(rule_match.category),
                category_confidence=rule_match.confidence,
                category_source="keyword",
                is_category_reliable=True,
                detected_lang=detected_lang,
                scores=rule_match.scores,
            )

        model_category, model_confidence, model_scores = self.model.predict(text)
        best_category = normalize_category(model_category if model_confidence >= rule_match.confidence else rule_match.category)
        best_confidence = max(model_confidence, rule_match.confidence)
        source = "ml" if model_confidence >= rule_match.confidence else "keyword"

        # If the signal is weak, prefer Diğer to reduce wrong category risk.
        if best_confidence < 0.55:
            best_category = "Diğer"
            source = "fallback"

        return CategoryPrediction(
            category=best_category if best_category in SUPPORTED_CATEGORIES else "Diğer",
            category_confidence=max(0.0, min(0.98, best_confidence)),
            category_source=source,
            is_category_reliable=best_confidence >= self.reliable_threshold,
            detected_lang=detected_lang,
            scores={**rule_match.scores, **{f"ml_{key}": value for key, value in model_scores.items()}},
        )

    def classify_batch(self, articles: Sequence[Mapping[str, Any] | NewsArticle]) -> List[CategoryPrediction]:
        """Classify a batch of articles and keep order stable."""

        return [self.classify(article) for article in articles]

    def enrich_article(self, article: Mapping[str, Any]) -> Dict[str, Any]:
        """Return a copy of an article with category payload fields attached."""

        output = dict(article)
        prediction = self.classify(output)
        output.update(prediction.to_dict())
        return output

    def group_by_category(self, articles: Iterable[Mapping[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group enriched articles by category for e-gazete/PDF sections."""

        grouped: Dict[str, List[Dict[str, Any]]] = {category: [] for category in SUPPORTED_CATEGORIES}
        for article in articles:
            enriched = self.enrich_article(article)
            grouped.setdefault(enriched["category"], []).append(enriched)
        return {category: items for category, items in grouped.items() if items}


_DEFAULT_CLASSIFIER = CategoryClassifier()


def classify_article(article: Mapping[str, Any] | NewsArticle) -> CategoryPrediction:
    """Classify a single article using the process-wide classifier."""

    return _DEFAULT_CLASSIFIER.classify(article)


def classify_batch(articles: Sequence[Mapping[str, Any] | NewsArticle]) -> List[CategoryPrediction]:
    """Classify a batch of articles using the process-wide classifier."""

    return _DEFAULT_CLASSIFIER.classify_batch(articles)
