"""Naive Bayes classifier for article category prediction."""

from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from app.ml.classifiers.common import NB_MODEL_PATH, TFIDF_PARAMS


class NBClassifier:
    """TF-IDF + Multinomial Naive Bayes news classifier.

    ``alpha=0.1`` applies Laplace smoothing so words that were not present
    during training do not create zero-probability class paths.
    """

    def __init__(self) -> None:
        """Create an unfitted Naive Bayes pipeline."""
        self.pipeline: Pipeline = Pipeline(
            steps=[
                ("tfidf", TfidfVectorizer(**TFIDF_PARAMS)),
                ("classifier", MultinomialNB(alpha=0.1)),
            ]
        )
        self.is_fitted = False

    def fit(self, texts: list[str], labels: list[str]) -> None:
        """Fit the model with article texts and category labels."""
        if len(texts) != len(labels):
            raise ValueError("texts and labels must have the same length")
        if not texts:
            raise ValueError("at least one training sample is required")
        self.pipeline.fit(texts, labels)
        self.is_fitted = True

    def predict(self, text: str) -> str:
        """Predict the most likely category label for one article text."""
        self._ensure_fitted()
        return str(self.pipeline.predict([text])[0])

    def predict_proba(self, text: str) -> dict[str, float]:
        """Return class probabilities keyed by category label."""
        self._ensure_fitted()
        classifier = self.pipeline.named_steps["classifier"]
        classes = list(classifier.classes_)
        probabilities = self.pipeline.predict_proba([text])[0]
        return {str(label): float(prob) for label, prob in zip(classes, probabilities, strict=False)}

    def save(self, path: str = NB_MODEL_PATH) -> None:
        """Persist the fitted pipeline to disk."""
        self._ensure_fitted()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, path)

    def load(self, path: str = NB_MODEL_PATH) -> None:
        """Load a previously saved pipeline from disk."""
        self.pipeline = joblib.load(path)
        self.is_fitted = True

    def _ensure_fitted(self) -> None:
        """Raise a clear error if prediction is attempted before training."""
        if not self.is_fitted:
            raise RuntimeError("NBClassifier is not fitted or loaded")
