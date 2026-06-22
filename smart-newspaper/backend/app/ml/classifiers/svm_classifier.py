"""Linear SVM classifier with Platt scaling probability calibration."""

from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from app.ml.classifiers.common import SVM_MODEL_PATH, TFIDF_PARAMS


class SVMClassifier:
    """TF-IDF + LinearSVC classifier calibrated with sigmoid Platt scaling."""

    def __init__(self) -> None:
        """Create an unfitted calibrated LinearSVC pipeline."""
        self.pipeline: Pipeline = self._build_pipeline()
        self.is_fitted = False

    def fit(self, texts: list[str], labels: list[str]) -> None:
        """Fit the calibrated SVM model with article texts and labels."""
        if len(texts) != len(labels):
            raise ValueError("texts and labels must have the same length")
        if len(set(labels)) < 2:
            raise ValueError("at least two distinct labels are required for SVM training")
        self.pipeline.fit(texts, labels)
        self.is_fitted = True

    def predict(self, text: str) -> str:
        """Predict the most likely category label for one article text."""
        self._ensure_fitted()
        return str(self.pipeline.predict([text])[0])

    def predict_proba(self, text: str) -> dict[str, float]:
        """Return calibrated class probabilities keyed by category label."""
        self._ensure_fitted()
        classifier = self.pipeline.named_steps["classifier"]
        classes = list(classifier.classes_)
        probabilities = self.pipeline.predict_proba([text])[0]
        return {str(label): float(prob) for label, prob in zip(classes, probabilities, strict=False)}

    def save(self, path: str = SVM_MODEL_PATH) -> None:
        """Persist the fitted SVM pipeline to disk."""
        self._ensure_fitted()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, path)

    def load(self, path: str = SVM_MODEL_PATH) -> None:
        """Load a previously saved calibrated SVM pipeline from disk."""
        self.pipeline = joblib.load(path)
        self.is_fitted = True

    def _build_pipeline(self) -> Pipeline:
        """Build the TF-IDF + Calibrated LinearSVC pipeline."""
        svm = LinearSVC(C=1.0, max_iter=2000, class_weight="balanced")
        classifier = CalibratedClassifierCV(estimator=svm, cv=3, method="sigmoid")
        return Pipeline(
            steps=[
                ("tfidf", TfidfVectorizer(**TFIDF_PARAMS)),
                ("classifier", classifier),
            ]
        )

    def _ensure_fitted(self) -> None:
        """Raise a clear error if prediction is attempted before training."""
        if not self.is_fitted:
            raise RuntimeError("SVMClassifier is not fitted or loaded")
