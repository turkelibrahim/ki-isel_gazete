"""Matrix-factorization recommender using Surprise SVD."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

try:
    import joblib
except Exception:  # pragma: no cover
    joblib = None  # type: ignore[assignment]

try:  # pragma: no cover
    import pandas as pd
    from surprise import Dataset, Reader, SVD
except Exception:  # pragma: no cover
    pd = None  # type: ignore[assignment]
    Dataset = None  # type: ignore[assignment]
    Reader = None  # type: ignore[assignment]
    SVD = None  # type: ignore[assignment]

MODEL_NAME = "svd.pkl"


class SVDRecommender:
    """SVD recommender for implicit user-article ratings.

    It implements ``r_hat(u,i) = μ + b_u + b_i + p_u · q_i`` through the
    Surprise SVD algorithm with the Prompt 32 parameters.
    """

    def __init__(self) -> None:
        """Initialize an empty SVD recommender."""
        self.model: Any | None = None
        self.is_trained: bool = False
        self.trainset_size: int = 0
        self.user_count: int = 0
        self.article_count: int = 0

    @property
    def is_available(self) -> bool:
        """Return whether Surprise and pandas are importable."""
        return Dataset is not None and Reader is not None and SVD is not None and pd is not None

    def fit(self, ratings: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """Train SVD(n_factors=50, n_epochs=20, lr_all=0.005, reg_all=0.02)."""
        rows = self._normalize_rows(ratings)
        if not self.is_available:
            logger.warning("scikit-surprise is not installed; SVD training skipped")
            return {"trained": False, "reason": "scikit-surprise-not-installed", "trainset_size": len(rows)}
        if len(rows) < 10:
            logger.warning("SVD training skipped: only %s rating rows", len(rows))
            return {"trained": False, "reason": "insufficient-data", "trainset_size": len(rows)}

        dataframe = pd.DataFrame(rows, columns=["user_id", "article_id", "rating"])
        reader = Reader(rating_scale=(0, 2.0))
        data = Dataset.load_from_df(dataframe[["user_id", "article_id", "rating"]], reader)
        trainset = data.build_full_trainset()
        model = SVD(n_factors=50, n_epochs=20, lr_all=0.005, reg_all=0.02)
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
            "algorithm": "SVD",
            "n_factors": 50,
            "n_epochs": 20,
            "lr_all": 0.005,
            "reg_all": 0.02,
        }

    def predict_for_user(self, user_id: str | int, candidate_article_ids: Iterable[int]) -> dict[int, float]:
        """Predict SVD scores for candidate article ids."""
        if not self.is_trained or self.model is None:
            return {}
        predictions: dict[int, float] = {}
        for article_id in candidate_article_ids:
            try:
                pred = self.model.predict(str(user_id), str(article_id))
                predictions[int(article_id)] = float(pred.est)
            except Exception:
                logger.debug("SVD prediction failed user_id=%s article_id=%s", user_id, article_id, exc_info=True)
        return predictions

    def save(self, path: str | Path) -> None:
        """Persist the trained recommender with joblib."""
        if joblib is None:
            raise RuntimeError("joblib is not installed")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str | Path) -> "SVDRecommender":
        """Load a recommender from disk, returning an empty model on failure."""
        path = Path(path)
        if joblib is None or not path.exists():
            return cls()
        try:
            loaded = joblib.load(path)
            if isinstance(loaded, cls):
                return loaded
        except Exception:
            logger.warning("Could not load SVD model from %s", path, exc_info=True)
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
