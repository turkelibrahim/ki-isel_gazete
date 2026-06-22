"""Lazy singleton zero-shot NLI classifier for news categories.

The Hugging Face model is intentionally not loaded at import time.  The first
real prediction request creates the ``transformers.pipeline`` once and all
following requests reuse that same pipeline instance.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

from app.ml.classifiers.ensemble_classifier import EnsembleClassifier

logger = logging.getLogger(__name__)

DEFAULT_CANDIDATE_LABELS: list[str] = [
    "teknoloji ve bilişim",
    "siyaset ve politika",
    "spor",
    "ekonomi ve finans",
    "sağlık ve tıp",
    "eğitim",
    "dünya haberleri",
    "yaşam ve kültür",
]

HYPOTHESIS_TEMPLATE = "Bu metin {} hakkındadır."
MODEL_NAME = "facebook/bart-large-mnli"
LABEL_STORE_PATH = Path("models/zero_shot_labels.json")
TEXT_LIMIT = 512


class ZeroShotClassifier:
    """Singleton wrapper around a zero-shot NLI classification pipeline."""

    _instance: "ZeroShotClassifier | None" = None
    _instance_lock = Lock()

    def __new__(cls) -> "ZeroShotClassifier":
        """Return one shared classifier object for the whole process."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize label state once without loading the heavy model."""
        if getattr(self, "_initialized", False):
            return
        self._pipeline: Any | None = None
        self._pipeline_lock = Lock()
        self._labels = self._load_labels()
        self._initialized = True

    def get_labels(self) -> list[str]:
        """Return currently active candidate labels."""
        return list(self._labels)

    def add_label(self, label: str) -> list[str]:
        """Add a new zero-shot label without retraining any model."""
        clean = " ".join(label.strip().split())
        if not clean:
            raise ValueError("label cannot be empty")
        if clean not in self._labels:
            self._labels.append(clean)
            self._save_labels()
            logger.info("Added zero-shot candidate label: %s", clean)
        return self.get_labels()

    def predict(self, text: str, multi_label: bool = False) -> dict[str, Any]:
        """Predict a category using NLI entailment scores.

        If the heavy model cannot be loaded or inference fails, the method falls
        back to the existing SVM/NB ensemble when available.  The application
        returns a safe low-confidence result instead of crashing.
        """
        cleaned = (text or "")[:TEXT_LIMIT].strip()
        if not cleaned:
            return {"label": "unknown", "score": 0.0, "all_scores": [], "model": "zero_shot"}

        try:
            classifier = self._get_pipeline()
            raw = classifier(
                cleaned,
                candidate_labels=self._labels,
                hypothesis_template=HYPOTHESIS_TEMPLATE,
                multi_label=multi_label,
            )
            labels = [str(label) for label in raw.get("labels", [])]
            scores = [float(score) for score in raw.get("scores", [])]
            all_scores = [
                {"label": label, "score": score}
                for label, score in zip(labels, scores, strict=False)
            ]
            if not all_scores:
                return {"label": "unknown", "score": 0.0, "all_scores": [], "model": "zero_shot"}
            best = all_scores[0]
            return {
                "label": best["label"],
                "score": best["score"],
                "all_scores": all_scores,
                "model": "zero_shot",
                "multi_label": multi_label,
                "hypothesis_template": HYPOTHESIS_TEMPLATE,
            }
        except Exception as exc:  # pragma: no cover - depends on optional model runtime
            logger.exception("Zero-shot NLI prediction failed, trying ensemble fallback")
            return self._predict_with_ensemble_fallback(cleaned, exc)

    def _get_pipeline(self) -> Any:
        """Load and cache the transformers pipeline on first use only."""
        if self._pipeline is not None:
            return self._pipeline
        with self._pipeline_lock:
            if self._pipeline is not None:
                return self._pipeline
            try:
                import torch  # type: ignore
                from transformers import pipeline  # type: ignore

                device = 0 if torch.cuda.is_available() else -1
                logger.info("Loading zero-shot model=%s device=%s", MODEL_NAME, device)
                self._pipeline = pipeline(
                    "zero-shot-classification",
                    model=MODEL_NAME,
                    device=device,
                )
                return self._pipeline
            except Exception:
                logger.exception("Could not load zero-shot model=%s", MODEL_NAME)
                raise

    def _predict_with_ensemble_fallback(self, text: str, exc: Exception) -> dict[str, Any]:
        """Return an ensemble prediction when zero-shot inference is unavailable."""
        try:
            ensemble = EnsembleClassifier()
            if not ensemble.load_if_available():
                raise RuntimeError("ensemble model files are not available")
            result = ensemble.predict(text)
            payload = result.to_dict()
            payload.update(
                {
                    "label": result.category,
                    "score": result.confidence,
                    "all_scores": [],
                    "model": "ensemble_fallback",
                    "fallback_reason": str(exc),
                }
            )
            return payload
        except Exception:
            logger.exception("Ensemble fallback after zero-shot failure also failed")
            return {
                "label": "unknown",
                "score": 0.0,
                "all_scores": [],
                "model": "zero_shot_unavailable",
                "fallback_reason": str(exc),
            }

    def _load_labels(self) -> list[str]:
        """Load labels from disk or return defaults."""
        try:
            if LABEL_STORE_PATH.exists():
                labels = json.loads(LABEL_STORE_PATH.read_text(encoding="utf-8"))
                if isinstance(labels, list):
                    clean = [str(label).strip() for label in labels if str(label).strip()]
                    return clean or list(DEFAULT_CANDIDATE_LABELS)
        except Exception:
            logger.warning("Could not read zero-shot label store, using defaults", exc_info=True)
        return list(DEFAULT_CANDIDATE_LABELS)

    def _save_labels(self) -> None:
        """Persist labels so new categories survive process restarts."""
        LABEL_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LABEL_STORE_PATH.write_text(
            json.dumps(self._labels, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
