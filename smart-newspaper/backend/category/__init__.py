"""SmartNewspaper automatic news category classification package."""

from .category_classifier import CategoryClassifier, classify_article, classify_batch
from .models import CategoryPrediction, NewsArticle

__all__ = ["CategoryClassifier", "CategoryPrediction", "NewsArticle", "classify_article", "classify_batch"]
