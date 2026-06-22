"""Item-based collaborative filtering recommender using Surprise KNNWithMeans."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

try:  # Optional heavy dependency: keep backend import-safe when not installed.
    import joblib
except Exception:  # pragma: no cover
    joblib = None  # type: ignore[assignment]

try:  # pragma: no cover - availability depends on runtime environment.
    import pandas as pd
    from surprise import Dataset, KNNWithMeans, Reader
except Exception:  # pragma: no cover
    pd = None  # type: ignore[assignment]
    Dataset = None  # type: ignore[assignment]
    KNNWithMeans = None  # type: ignore[assignment]
    Reader = None  # type: ignore[assignment]

MODEL_NAME = "ibcf.pkl"


class IBCFRecommender:
    """Item-Based Collaborative Filtering recommender.

    The model follows the Prompt 32 specification: Surprise ``KNNWithMeans``
    with cosine similarity, ``user_based=False``, ``k=20`` and
    ``min_support=3``.  All heavy imports are optional so deployments without
    scikit-surprise can still run the rest of the application.
    """

    def __init__(self) -> None:
        """Initialize an empty IBCF recommender."""
        self.model: Any | None = None
        self.is_trained: bool = False
        self.trainset_size: int = 0
        self.user_count: int = 0
        self.article_count: int = 0

    @property
    def is_available(self) -> bool:
        """Return whether Surprise and pandas are importable."""
        return Dataset is not None and KNNWithMeans is not None and Reader is not None and pd is not None

    def fit(self, ratings: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """Train the item-based KNNWithMeans model from implicit ratings."""
        rows = self._normalize_rows(ratings)
        if not self.is_available:
            logger.warning("scikit-surprise is not installed; IBCF training skipped")
            return {"trained": False, "reason": "scikit-surprise-not-installed", "trainset_size": len(rows)}
        if len(rows) < 10:
            logger.warning("IBCF training skipped: only %s rating rows", len(rows))
            return {"trained": False, "reason": "insufficient-data", "trainset_size": len(rows)}

        dataframe = pd.DataFrame(rows, columns=["user_id", "article_id", "rating"])
        reader = Reader(rating_scale=(0, 2.0))
        data = Dataset.load_from_df(dataframe[["user_id", "article_id", "rating"]], reader)
        trainset = data.build_full_trainset()
        model = KNNWithMeans(
            k=20,
            sim_options={"name": "cosine", "user_based": False, "min_support": 3},
        )
        model.fit(trainset)
        self.model = model
        self.is_trained = True
        self.trainset_size = len(rows)
        self.user_count = int(dataframe["user_id"].nunique())
        self.article_count = int(dataframe["article_id"].nunique())
        return {
            "trained": True,
            "trainset_size": self.trainset_size,
            "user_count": self.user_count,
            "article_count": self.article_count,
            "algorithm": "KNNWithMeans-item-based",
            "k": 20,
            "min_support": 3,
        }

    def predict_for_user(self, user_id: str | int, candidate_article_ids: Iterable[int]) -> dict[int, float]:
        """Predict IBCF scores for candidate article ids."""
        if not self.is_trained or self.model is None:
            return {}
        predictions: dict[int, float] = {}
        for article_id in candidate_article_ids:
            try:
                pred = self.model.predict(str(user_id), str(article_id))
                predictions[int(article_id)] = float(pred.est)
            except Exception:
                logger.debug("IBCF prediction failed user_id=%s article_id=%s", user_id, article_id, exc_info=True)
        return predictions

    def save(self, path: str | Path) -> None:
        """Persist the trained recommender with joblib."""
        if joblib is None:
            raise RuntimeError("joblib is not installed")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str | Path) -> "IBCFRecommender":
        """Load a recommender from disk, returning an empty model on failure."""
        path = Path(path)
        if joblib is None or not path.exists():
            return cls()
        try:
            loaded = joblib.load(path)
            if isinstance(loaded, cls):
                return loaded
        except Exception:
            logger.warning("Could not load IBCF model from %s", path, exc_info=True)
        return cls()

    def _normalize_rows(self, ratings: Iterable[dict[str, Any]]) -> list[tuple[str, str, float]]:
        """Normalize rating dicts into Surprise-compatible rows."""
        rows: list[tuple[str, str, float]] = []
        for row in ratings:
            try:
                user_id = str(row["user_id"])
                article_id = str(int(row["article_id"]))
                rating = max(0.0, min(float(row["rating"]), 2.0))
            except (KeyError, TypeError, ValueError):
                continue
            rows.append((user_id, article_id, rating))
        return rows
