"""Shared constants for TF-IDF based news classifiers."""

from __future__ import annotations

TFIDF_PARAMS: dict[str, object] = {
    "max_features": 50000,
    "ngram_range": (1, 2),
    "sublinear_tf": True,
    "min_df": 2,
    "strip_accents": "unicode",
}

DEFAULT_MODEL_DIR = "models"
NB_MODEL_PATH = f"{DEFAULT_MODEL_DIR}/nb.pkl"
SVM_MODEL_PATH = f"{DEFAULT_MODEL_DIR}/svm.pkl"

MULTILABEL_MODEL_PATH = f"{DEFAULT_MODEL_DIR}/multilabel.pkl"
