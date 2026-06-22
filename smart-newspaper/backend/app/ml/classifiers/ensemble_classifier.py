"""Confidence-aware ensemble classifier for news categories."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.ml.classifiers.common import NB_MODEL_PATH, SVM_MODEL_PATH
from app.ml.classifiers.nb_classifier import NBClassifier
from app.ml.classifiers.svm_classifier import SVMClassifier

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ClassificationResult:
    """Normalized output returned by the ensemble classifier."""

    category: str
    confidence: float
    model: str
    needs_review: bool
    nb_category: str | None = None
    nb_confidence: float | None = None
    svm_category: str | None = None
    svm_confidence: float | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize the classification result for API responses."""
        return {
            "category": self.category,
            "confidence": self.confidence,
            "model": self.model,
            "needs_review": self.needs_review,
            "nb_category": self.nb_category,
            "nb_confidence": self.nb_confidence,
            "svm_category": self.svm_category,
            "svm_confidence": self.svm_confidence,
            "reason": self.reason,
        }


class EnsembleClassifier:
    """Decision layer combining calibrated SVM and Naive Bayes classifiers."""

    def __init__(self, nb: NBClassifier | None = None, svm: SVMClassifier | None = None) -> None:
        """Create the ensemble with optional prebuilt model wrappers."""
        self.nb = nb or NBClassifier()
        self.svm = svm or SVMClassifier()

    def load(self, nb_path: str = NB_MODEL_PATH, svm_path: str = SVM_MODEL_PATH) -> None:
        """Load both persisted model pipelines from disk."""
        self.nb.load(nb_path)
        self.svm.load(svm_path)

    def load_if_available(self, nb_path: str = NB_MODEL_PATH, svm_path: str = SVM_MODEL_PATH) -> bool:
        """Load persisted models if both model files exist."""
        if Path(nb_path).exists() and Path(svm_path).exists():
            self.load(nb_path, svm_path)
            return True
        return False

    def predict(self, text: str) -> ClassificationResult:
        """Classify one article using the SVM-first ensemble policy.

        Decision logic:
        - If SVM confidence is >= 0.85, accept SVM directly.
        - If SVM confidence is lower, cross-check with Naive Bayes.
        - If the two agree, accept as ensemble.
        - If they disagree, keep SVM as temporary category and request moderation.
        """
        svm_proba = self.svm.predict_proba(text)
        svm_category, svm_confidence = self._top_label(svm_proba)

        if svm_confidence >= 0.85:
            return ClassificationResult(
                category=svm_category,
                confidence=svm_confidence,
                model="svm",
                needs_review=False,
                svm_category=svm_category,
                svm_confidence=svm_confidence,
                reason="svm_confidence_ge_0_85",
            )

        nb_proba = self.nb.predict_proba(text)
        nb_category, nb_confidence = self._top_label(nb_proba)

        if nb_category == svm_category:
            return ClassificationResult(
                category=svm_category,
                confidence=max(svm_confidence, nb_confidence),
                model="ensemble",
                needs_review=False,
                nb_category=nb_category,
                nb_confidence=nb_confidence,
                svm_category=svm_category,
                svm_confidence=svm_confidence,
                reason="nb_svm_agree",
            )

        return ClassificationResult(
            category=svm_category,
            confidence=svm_confidence,
            model="ensemble",
            needs_review=True,
            nb_category=nb_category,
            nb_confidence=nb_confidence,
            svm_category=svm_category,
            svm_confidence=svm_confidence,
            reason="nb_svm_disagree_low_confidence",
        )

    def _top_label(self, probabilities: dict[str, float]) -> tuple[str, float]:
        """Return the highest-probability label and confidence."""
        if not probabilities:
            raise ValueError("probability dictionary is empty")
        label, confidence = max(probabilities.items(), key=lambda item: item[1])
        return str(label), float(confidence)
