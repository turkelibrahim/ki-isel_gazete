"""Training service for Module 7 collaborative recommender models."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.recommender.ibcf_recommender import IBCFRecommender
from app.ml.recommender.svd_recommender import SVDRecommender
from app.services.tracking_service import TrackingService

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BACKEND_DIR / "models" / "recommenders"
IBCF_MODEL_PATH = MODEL_DIR / "ibcf.pkl"
SVD_MODEL_PATH = MODEL_DIR / "svd.pkl"
MIN_RATING_ROWS = 10

try:  # Optional heavy dependency; do not break app import if unavailable.
    import pandas as pd
    from surprise import Dataset, Reader, SVD, KNNWithMeans
    from surprise.model_selection import cross_validate
except Exception:  # pragma: no cover
    pd = None  # type: ignore[assignment]
    Dataset = None  # type: ignore[assignment]
    Reader = None  # type: ignore[assignment]
    SVD = None  # type: ignore[assignment]
    KNNWithMeans = None  # type: ignore[assignment]
    cross_validate = None  # type: ignore[assignment]


class RecommenderTrainingService:
    """Train and evaluate IBCF + SVD models from implicit feedback."""

    def __init__(self, model_dir: str | Path = MODEL_DIR) -> None:
        """Initialize the service with a model directory."""
        self.model_dir = Path(model_dir)
        self.ibcf_path = self.model_dir / "ibcf.pkl"
        self.svd_path = self.model_dir / "svd.pkl"
        self.tracking_service = TrackingService()

    async def train_recommenders(self, db: AsyncSession) -> dict[str, Any]:
        """Train IBCF and SVD models, keeping old models on failure."""
        rating_rows = await self.tracking_service.get_user_ratings_matrix(db)
        positive_rows = [row for row in rating_rows if float(row.get("rating") or 0.0) > 0.0]
        summary = self._dataset_summary(positive_rows)
        if len(positive_rows) < MIN_RATING_ROWS:
            logger.warning("Recommender training skipped: insufficient rating rows=%s", len(positive_rows))
            return {
                "trained": False,
                "reason": "insufficient-data",
                **summary,
                "minimum_required": MIN_RATING_ROWS,
                "models_preserved": True,
            }

        self.model_dir.mkdir(parents=True, exist_ok=True)
        result: dict[str, Any] = {"trained": False, **summary, "models_preserved": True}
        try:
            evaluation = self.evaluate_models(positive_rows)
            ibcf = IBCFRecommender()
            svd = SVDRecommender()
            ibcf_result = ibcf.fit(positive_rows)
            svd_result = svd.fit(positive_rows)
            if ibcf_result.get("trained"):
                ibcf.save(self.ibcf_path)
            if svd_result.get("trained"):
                svd.save(self.svd_path)
            result.update(
                {
                    "trained": bool(ibcf_result.get("trained") or svd_result.get("trained")),
                    "ibcf": ibcf_result,
                    "svd": svd_result,
                    "evaluation": evaluation,
                    "model_paths": {
                        "ibcf": str(self.ibcf_path.relative_to(BACKEND_DIR)),
                        "svd": str(self.svd_path.relative_to(BACKEND_DIR)),
                    },
                }
            )
            return result
        except Exception as exc:
            logger.exception("Recommender training failed; keeping previous model files")
            result.update({"trained": False, "reason": str(exc), "models_preserved": True})
            return result

    def evaluate_models(self, rating_rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Evaluate IBCF and SVD with Surprise cross_validate RMSE/MAE."""
        if not self._surprise_available():
            return {"available": False, "reason": "scikit-surprise-not-installed"}
        normalized = self._normalize_rows(rating_rows)
        if len(normalized) < MIN_RATING_ROWS:
            return {"available": False, "reason": "insufficient-data"}
        dataframe = pd.DataFrame(normalized, columns=["user_id", "article_id", "rating"])
        reader = Reader(rating_scale=(0, 2.0))
        data = Dataset.load_from_df(dataframe[["user_id", "article_id", "rating"]], reader)
        cv = min(5, len(normalized))
        if cv < 2:
            return {"available": False, "reason": "not-enough-folds"}
        metrics: dict[str, Any] = {}
        algorithms = {
            "ibcf": KNNWithMeans(k=20, sim_options={"name": "cosine", "user_based": False, "min_support": 3}),
            "svd": SVD(n_factors=50, n_epochs=20, lr_all=0.005, reg_all=0.02),
        }
        for name, algorithm in algorithms.items():
            try:
                scores = cross_validate(algorithm, data, measures=["RMSE", "MAE"], cv=cv, verbose=False)
                rmse_values = list(scores.get("test_rmse", []))
                mae_values = list(scores.get("test_mae", []))
                metrics[name] = {
                    "rmse_mean": float(sum(rmse_values) / len(rmse_values)) if rmse_values else None,
                    "mae_mean": float(sum(mae_values) / len(mae_values)) if mae_values else None,
                    "cv": cv,
                }
            except Exception:
                logger.warning("cross_validate failed for %s", name, exc_info=True)
                metrics[name] = {"rmse_mean": None, "mae_mean": None, "cv": cv, "error": "evaluation_failed"}
        return {"available": True, **metrics}

    def get_status(self) -> dict[str, Any]:
        """Return persisted model status without loading the models."""
        return {
            "model_dir": str(self.model_dir.relative_to(BACKEND_DIR)) if self.model_dir.is_relative_to(BACKEND_DIR) else str(self.model_dir),
            "ibcf_exists": self.ibcf_path.exists(),
            "svd_exists": self.svd_path.exists(),
            "ibcf_path": str(self.ibcf_path.relative_to(BACKEND_DIR)),
            "svd_path": str(self.svd_path.relative_to(BACKEND_DIR)),
            "surprise_available": self._surprise_available(),
            "weights": {
                "content_based": 0.30,
                "ibcf": 0.35,
                "svd": 0.25,
                "trending": 0.10,
            },
        }

    def _dataset_summary(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Return count diagnostics for a ratings dataset."""
        users = {str(row.get("user_id")) for row in rows if row.get("user_id") is not None}
        articles = {int(row.get("article_id")) for row in rows if row.get("article_id") is not None}
        return {"trainset_size": len(rows), "user_count": len(users), "article_count": len(articles)}

    def _normalize_rows(self, ratings: list[dict[str, Any]]) -> list[tuple[str, str, float]]:
        """Normalize rating rows into Surprise-compatible tuples."""
        rows: list[tuple[str, str, float]] = []
        for row in ratings:
            try:
                rows.append((str(row["user_id"]), str(int(row["article_id"])), max(0.0, min(float(row["rating"]), 2.0))))
            except (KeyError, TypeError, ValueError):
                continue
        return rows

    def _surprise_available(self) -> bool:
        """Return True when scikit-surprise dependencies can be imported."""
        return all(obj is not None for obj in [pd, Dataset, Reader, SVD, KNNWithMeans, cross_validate])
