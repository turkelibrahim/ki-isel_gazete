"""Module 7 advanced recommendation API endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.database import AsyncSessionLocal
from app.services.recommendation_service import get_personalized_feed, get_recommendation_debug
from app.services.recommender_training_service import RecommenderTrainingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])
training_service = RecommenderTrainingService()


@router.post("/train")
async def train_recommenders() -> dict[str, Any]:
    """Train IBCF and SVD models from TrackingService implicit ratings."""
    try:
        async with AsyncSessionLocal() as db:
            return await training_service.train_recommenders(db)
    except Exception as exc:
        logger.exception("Recommendation model training failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not train recommenders") from exc


@router.get("/status")
async def recommender_status() -> dict[str, Any]:
    """Return model file and configuration status."""
    return training_service.get_status()


@router.get("/user/{user_id}")
async def recommendations_for_user(user_id: str, limit: int = Query(default=30, ge=1, le=100)) -> dict[str, Any]:
    """Return personalized recommendations for one user."""
    try:
        async with AsyncSessionLocal() as db:
            return await get_personalized_feed(db, user_id=user_id, limit=limit)
    except Exception as exc:
        logger.exception("Could not load recommendations user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load recommendations") from exc


@router.get("/debug/{user_id}")
async def recommendation_debug(user_id: str) -> dict[str, Any]:
    """Return non-sensitive debug details for one user's recommender path."""
    try:
        async with AsyncSessionLocal() as db:
            debug = await get_recommendation_debug(db, user_id=user_id)
            debug["module7_models"] = training_service.get_status()
            return debug
    except Exception as exc:
        logger.exception("Could not load recommendation debug user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load recommendation debug") from exc
