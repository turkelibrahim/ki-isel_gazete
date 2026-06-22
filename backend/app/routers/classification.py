"""API routes for training and running news classification models."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.database import AsyncSessionLocal
from app.services.classification_service import (
    classify_article,
    classify_batch,
    get_model_status,
    train_models,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/classification", tags=["classification"])


class TrainingItem(BaseModel):
    """One supervised training example."""

    text: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)


class TrainRequest(BaseModel):
    """Optional request body for manual model training."""

    items: list[TrainingItem] | None = None


@router.post("/train")
async def train(request: TrainRequest | None = None) -> dict[str, Any]:
    """Train NB and SVM models from provided items or available human labels."""
    try:
        async with AsyncSessionLocal() as db:
            items = [item.model_dump() for item in request.items] if request and request.items else None
            return await train_models(db, items)
    except Exception as exc:
        logger.exception("Classification training failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification training failed: {exc}",
        ) from exc


@router.post("/articles/{article_id}/classify")
async def classify_one(article_id: int) -> dict[str, Any]:
    """Classify one article and persist its category assignment."""
    try:
        async with AsyncSessionLocal() as db:
            return await classify_article(db, article_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Article classification failed article_id=%s", article_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Article classification failed: {exc}",
        ) from exc


@router.post("/batch")
async def classify_many(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
    """Classify a batch of unclassified articles."""
    try:
        async with AsyncSessionLocal() as db:
            return await classify_batch(db, limit=limit)
    except Exception as exc:
        logger.exception("Batch classification failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch classification failed: {exc}",
        ) from exc


@router.get("/models/status")
async def models_status() -> dict[str, Any]:
    """Return local model file availability and ensemble policy metadata."""
    return get_model_status()
