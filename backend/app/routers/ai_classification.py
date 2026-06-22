"""API routes for zero-shot AI classification labels."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.ml.zero_shot_classifier import ZeroShotClassifier

router = APIRouter(prefix="/api/ai", tags=["ai-classification"])


class AddLabelRequest(BaseModel):
    """Request body for adding a zero-shot label."""

    label: str = Field(..., min_length=1, max_length=255)


@router.post("/add-label")
async def add_label(request: AddLabelRequest) -> dict[str, Any]:
    """Add a candidate label without retraining supervised models."""
    try:
        labels = ZeroShotClassifier().add_label(request.label)
        return {"added": request.label.strip(), "labels": labels, "training_required": False}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/labels")
async def labels() -> dict[str, Any]:
    """Return active zero-shot candidate labels."""
    return {"labels": ZeroShotClassifier().get_labels()}
