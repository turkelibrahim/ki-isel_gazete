"""API routes for multi-label news classification."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.database import AsyncSessionLocal
from app.services.multilabel_service import (
    classify_multilabel_article,
    classify_multilabel_batch,
    get_multilabel_status,
    train_multilabel_model,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/multilabel", tags=["multilabel"])


class MultiLabelTrainingItem(BaseModel):
    """One supervised multi-label training example."""

    text: str = Field(..., min_length=1)
    labels: list[str] = Field(..., min_length=1)


class MultiLabelTrainRequest(BaseModel):
    """Optional request body for multi-label training."""

    items: list[MultiLabelTrainingItem] | None = None
    use_classifier_chain: bool = True


@router.post("/train")
async def train(request: MultiLabelTrainRequest | None = None) -> dict[str, Any]:
    """Train the multi-label classifier."""
    try:
        async with AsyncSessionLocal() as db:
            items = [item.model_dump() for item in request.items] if request and request.items else None
            use_chain = request.use_classifier_chain if request else True
            return await train_multilabel_model(db, items, use_classifier_chain=use_chain)
    except Exception as exc:
        logger.exception("Multi-label training failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Multi-label training failed: {exc}",
        ) from exc


@router.post("/articles/{article_id}/classify")
async def classify_one(article_id: int) -> dict[str, Any]:
    """Classify one article into multiple categories."""
    try:
        async with AsyncSessionLocal() as db:
            return await classify_multilabel_article(db, article_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Multi-label classification failed article_id=%s", article_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Multi-label classification failed: {exc}",
        ) from exc


@router.post("/batch")
async def classify_many(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
    """Classify a batch of articles with the multi-label model."""
    try:
        async with AsyncSessionLocal() as db:
            return await classify_multilabel_batch(db, limit=limit)
    except Exception as exc:
        logger.exception("Multi-label batch failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Multi-label batch failed: {exc}",
        ) from exc


@router.get("/status")
async def status_report() -> dict[str, Any]:
    """Return multi-label model status."""
    return get_multilabel_status()
