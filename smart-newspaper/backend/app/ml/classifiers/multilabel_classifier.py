"""Multi-label news classifier using Binary Relevance and Classifier Chains.

A single news item can belong to more than one category. The implementation
uses one shared TF-IDF vectorizer, a Binary Relevance model for independent
category decisions, and an optional five-member ClassifierChain ensemble to
learn category correlations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.multioutput import ClassifierChain, MultiOutputClassifier
from sklearn.svm import LinearSVC

from app.ml.classifiers.common import MULTILABEL_MODEL_PATH

logger = logging.getLogger(__name__)

CATEGORIES: list[str] = [
    "Spor",
    "Ekonomi",
    "Teknoloji",
    "Siyaset",
    "Sağlık",
    "Eğitim",
    "Kültür",
    "Dünya",
]

MULTILABEL_TFIDF_PARAMS: dict[str, object] = {
    "max_features": 50000,
    "ngram_range": (1, 2),
    "sublinear_tf": True,
    "strip_accents": "unicode",
}

THRESHOLD = 0.40
CHAIN_RANDOM_STATES = [11, 23, 37, 41, 53]


def _make_calibrated_svc() -> CalibratedClassifierCV:
    """Create a calibrated LinearSVC compatible with old and new sklearn."""
    base = LinearSVC(C=1.0, class_weight="balanced", max_iter=2000)
    try:
        return CalibratedClassifierCV(estimator=base, cv=3, method="sigmoid")
    except TypeError:  # pragma: no cover - sklearn<1.2 compatibility
        return CalibratedClassifierCV(base_estimator=base, cv=3, method="sigmoid")


def _make_classifier_chain(random_state: int) -> ClassifierChain:
    """Create one random-order classifier chain with a calibrated SVM."""
    estimator = _make_calibrated_svc()
    try:
        return ClassifierChain(estimator=estimator, order="random", random_state=random_state)
    except TypeError:  # pragma: no cover - sklearn<1.2 compatibility
        return ClassifierChain(base_estimator=estimator, order="random", random_state=random_state)


class MultiLabelClassifier:
    """Binary relevance + classifier chain multi-label classifier."""

    def __init__(self, threshold: float = THRESHOLD, categories: list[str] | None = None, n_jobs: int = -1) -> None:
        """Initialize an empty multi-label classifier."""
        self.threshold = threshold
        self.categories = categories or CATEGORIES.copy()
        self.n_jobs = n_jobs
        self.vectorizer = TfidfVectorizer(**MULTILABEL_TFIDF_PARAMS)
        self.binary_relevance: MultiOutputClassifier | None = None
        self.chains: list[ClassifierChain] = []
        self.is_fitted = False

    def fit(
        self,
        texts: list[str],
        labels: list[list[int]],
        use_classifier_chain: bool = True,
    ) -> None:
        """Fit Binary Relevance and optional ClassifierChain models."""
        cleaned_texts = [text.strip() for text in texts if text and text.strip()]
        if len(cleaned_texts) != len(labels):
            raise ValueError("texts and labels must have the same length after cleaning")
        y = np.asarray(labels, dtype=int)
        self._validate_training_data(cleaned_texts, y)

        x_matrix = self.vectorizer.fit_transform(cleaned_texts)
        self.binary_relevance = MultiOutputClassifier(_make_calibrated_svc(), n_jobs=self.n_jobs)
        self.binary_relevance.fit(x_matrix, y)

        self.chains = []
        if use_classifier_chain:
            for random_state in CHAIN_RANDOM_STATES:
                chain = _make_classifier_chain(random_state)
                chain.fit(x_matrix, y)
                self.chains.append(chain)

        self.is_fitted = True
        logger.info(
            "Multi-label classifier trained samples=%s categories=%s chains=%s",
            len(cleaned_texts),
            len(self.categories),
            len(self.chains),
        )

    def predict(self, text: str) -> list[dict[str, float | str]]:
        """Return every category whose positive probability passes threshold."""
        if not self.is_fitted or self.binary_relevance is None:
            raise RuntimeError("Multi-label model is not trained")
        if not text or not text.strip():
            return []

        x_matrix = self.vectorizer.transform([text])
        br_probs = self._binary_relevance_probabilities(x_matrix)
        if self.chains:
            chain_probs = self._chain_probabilities(x_matrix)
            probabilities = (br_probs + chain_probs) / 2.0
        else:
            probabilities = br_probs

        results: list[dict[str, float | str]] = []
        for category, confidence in zip(self.categories, probabilities, strict=False):
            score = float(confidence)
            if score >= self.threshold:
                results.append({"category": category, "confidence": score})
        results.sort(key=lambda item: float(item["confidence"]), reverse=True)
        return results

    def save(self, path: str = MULTILABEL_MODEL_PATH) -> None:
        """Persist the fitted model bundle with joblib."""
        if not self.is_fitted:
            raise RuntimeError("Cannot save an unfitted multi-label model")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "threshold": self.threshold,
                "categories": self.categories,
                "vectorizer": self.vectorizer,
                "binary_relevance": self.binary_relevance,
                "chains": self.chains,
                "is_fitted": self.is_fitted,
                "n_jobs": self.n_jobs,
            },
            path,
        )

    def load(self, path: str = MULTILABEL_MODEL_PATH) -> None:
        """Load a previously saved model bundle."""
        bundle: dict[str, Any] = joblib.load(path)
        self.threshold = float(bundle.get("threshold", THRESHOLD))
        self.categories = list(bundle.get("categories", CATEGORIES))
        self.vectorizer = bundle["vectorizer"]
        self.binary_relevance = bundle["binary_relevance"]
        self.chains = list(bundle.get("chains", []))
        self.is_fitted = bool(bundle.get("is_fitted", True))
        self.n_jobs = int(bundle.get("n_jobs", -1))

    def load_if_available(self, path: str = MULTILABEL_MODEL_PATH) -> bool:
        """Load the model if the model file exists."""
        if not Path(path).exists():
            return False
        self.load(path)
        return True

    def _binary_relevance_probabilities(self, x_matrix: Any) -> np.ndarray:
        """Return positive-class probabilities for every category."""
        assert self.binary_relevance is not None
        probs: list[float] = []
        for estimator in self.binary_relevance.estimators_:
            if hasattr(estimator, "predict_proba"):
                class_probs = estimator.predict_proba(x_matrix)[0]
                classes = list(getattr(estimator, "classes_", [0, 1]))
                positive_index = classes.index(1) if 1 in classes else len(class_probs) - 1
                probs.append(float(class_probs[positive_index]))
            else:  # pragma: no cover - defensive fallback
                probs.append(float(estimator.predict(x_matrix)[0]))
        return np.asarray(probs, dtype=float)

    def _chain_probabilities(self, x_matrix: Any) -> np.ndarray:
        """Average positive probabilities from all classifier chains."""
        chain_outputs: list[np.ndarray] = []
        for chain in self.chains:
            if hasattr(chain, "predict_proba"):
                values = np.asarray(chain.predict_proba(x_matrix)[0], dtype=float)
            else:  # pragma: no cover - defensive fallback
                values = np.asarray(chain.predict(x_matrix)[0], dtype=float)
            chain_outputs.append(values)
        if not chain_outputs:
            return np.zeros(len(self.categories), dtype=float)
        return np.mean(chain_outputs, axis=0)

    def _validate_training_data(self, texts: list[str], y: np.ndarray) -> None:
        """Validate shape and class coverage for calibrated SVM training."""
        if len(texts) < 6:
            raise ValueError("Multi-label training requires at least 6 samples")
        if y.ndim != 2 or y.shape[1] != len(self.categories):
            raise ValueError(f"y must be a binary matrix with {len(self.categories)} columns")
        for index, category in enumerate(self.categories):
            positives = int(y[:, index].sum())
            negatives = int(len(y) - positives)
            if positives < 3 or negatives < 3:
                raise ValueError(
                    f"Category {category!r} needs at least 3 positive and 3 negative samples; "
                    f"got positives={positives}, negatives={negatives}"
                )


def labels_to_matrix(label_sets: list[list[str]], categories: list[str] | None = None) -> list[list[int]]:
    """Convert a list of category-name lists into a binary matrix."""
    category_list = categories or CATEGORIES
    matrix: list[list[int]] = []
    for labels in label_sets:
        normalized = {label.strip().lower() for label in labels if label and label.strip()}
        matrix.append([1 if category.lower() in normalized else 0 for category in category_list])
    return matrix
