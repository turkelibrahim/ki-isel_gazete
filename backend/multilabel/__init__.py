"""Multi-label news classification package for SmartNewspaper."""

from .models import ALLOWED_LABELS, MultiLabelPrediction
from .multilabel_classifier import MultiLabelClassifier, classify_article, classify_articles
from .output_validator import validate_prediction

__all__ = [
    "ALLOWED_LABELS",
    "MultiLabelPrediction",
    "MultiLabelClassifier",
    "classify_article",
    "classify_articles",
    "validate_prediction",
]
