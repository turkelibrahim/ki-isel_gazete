"""Model retraining service using accumulated human labels."""

from __future__ import annotations

import json
import logging
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.classifiers.common import NB_MODEL_PATH, SVM_MODEL_PATH
from app.ml.classifiers.nb_classifier import NBClassifier
from app.ml.classifiers.svm_classifier import SVMClassifier
from app.models import Article, ArticleCategory, Category
from app.services.classification_service import build_article_text
from app.services.moderation_service import MIN_HUMAN_LABELS_FOR_RETRAIN, count_human_labels

logger = logging.getLogger(__name__)
ACTIVE_MODEL_CONFIG = Path("models/active_model.json")


async def retrain_models_if_needed(db: AsyncSession, force: bool = False) -> dict[str, Any]:
    """Retrain NB/SVM models when at least 50 human labels are available."""
    human_count = await count_human_labels(db)
    if human_count < MIN_HUMAN_LABELS_FOR_RETRAIN and not force:
        return {
            "started": False,
            "reason": "not_enough_human_labels",
            "human_label_count": human_count,
            "required": MIN_HUMAN_LABELS_FOR_RETRAIN,
        }

    pairs = await _load_human_training_pairs(db)
    _validate_retrain_pairs(pairs)
    texts = [text for text, _label in pairs]
    labels = [label for _text, label in pairs]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_dir = Path("models")
    model_dir.mkdir(parents=True, exist_ok=True)
    nb_path = model_dir / f"nb_{timestamp}.pkl"
    svm_path = model_dir / f"svm_{timestamp}.pkl"

    nb = NBClassifier()
    nb.fit(texts, labels)
    nb.save(str(nb_path))

    svm = SVMClassifier()
    svm.fit(texts, labels)
    svm.save(str(svm_path))

    # Use copy instead of symlink for Windows compatibility.
    shutil.copy2(nb_path, NB_MODEL_PATH)
    shutil.copy2(svm_path, SVM_MODEL_PATH)

    ACTIVE_MODEL_CONFIG.write_text(
        json.dumps(
            {
                "active_nb": str(nb_path),
                "active_svm": str(svm_path),
                "alias_nb": NB_MODEL_PATH,
                "alias_svm": SVM_MODEL_PATH,
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "samples": len(texts),
                "label_counts": dict(Counter(labels)),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "started": True,
        "samples": len(texts),
        "human_label_count": human_count,
        "models": {"nb": str(nb_path), "svm": str(svm_path)},
        "active_aliases": {"nb": NB_MODEL_PATH, "svm": SVM_MODEL_PATH},
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_retrain_status(db: AsyncSession) -> dict[str, Any]:
    """Return retraining readiness and current active model metadata."""
    human_count = await count_human_labels(db)
    config: dict[str, Any] = {}
    if ACTIVE_MODEL_CONFIG.exists():
        try:
            config = json.loads(ACTIVE_MODEL_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Could not read active model config", exc_info=True)
    return {
        "human_label_count": human_count,
        "required": MIN_HUMAN_LABELS_FOR_RETRAIN,
        "retrain_ready": human_count >= MIN_HUMAN_LABELS_FOR_RETRAIN,
        "active_model": config,
    }


async def _load_human_training_pairs(db: AsyncSession) -> list[tuple[str, str]]:
    """Load human-labeled article/category pairs for supervised retraining."""
    stmt = (
        select(Article, Category)
        .join(ArticleCategory, Article.id == ArticleCategory.article_id)
        .join(Category, Category.id == ArticleCategory.category_id)
        .where(ArticleCategory.is_human_label.is_(True))
    )
    rows = (await db.execute(stmt)).all()
    return [(build_article_text(article), category.name) for article, category in rows if build_article_text(article)]


def _validate_retrain_pairs(pairs: list[tuple[str, str]]) -> None:
    """Validate sample count and class distribution before replacing models."""
    if len(pairs) < MIN_HUMAN_LABELS_FOR_RETRAIN:
        raise ValueError(f"At least {MIN_HUMAN_LABELS_FOR_RETRAIN} human labels are required")
    counts = Counter(label for _text, label in pairs)
    if len(counts) < 2:
        raise ValueError("At least two categories are required for retraining")
    too_small = {label: count for label, count in counts.items() if count < 3}
    if too_small:
        raise ValueError(f"Calibrated SVM cv=3 requires at least 3 samples per category: {too_small}")
