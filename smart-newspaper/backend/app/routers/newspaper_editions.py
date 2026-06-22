"""Personal newspaper edition generation and preview APIs."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from app.database import AsyncSessionLocal
from app.models import NewspaperEdition
from app.services.edition_pipeline_service import EditionPipelineService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/newspaper/editions", tags=["newspaper-editions"])


class GenerateEditionRequest(BaseModel):
    """Request body for daily edition generation."""

    user_id: int | str = Field(..., description="User id whose edition will be generated")
    filters: dict[str, Any] | None = Field(default=None, description="Optional article filter object")


@router.post("/generate")
async def generate_edition(payload: GenerateEditionRequest) -> dict[str, Any]:
    """Generate or update today's daily newspaper edition for a user."""
    try:
        async with AsyncSessionLocal() as db:
            return await EditionPipelineService().generate_daily_edition(
                db,
                user_id=str(payload.user_id),
                filters=payload.filters or None,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Edition generation failed user_id=%s", payload.user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Edition generation failed") from exc


@router.get("/me")
async def my_editions(
    user_id: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict[str, Any]:
    """Return recent editions for a user.

    The project has no auth dependency yet, so ``user_id`` is passed explicitly.
    This keeps the endpoint ready to be replaced by authenticated ``current_user``
    later without changing the storage model.
    """
    try:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(NewspaperEdition)
                .where(NewspaperEdition.user_id == user_id)
                .order_by(desc(NewspaperEdition.edition_date), desc(NewspaperEdition.created_at))
                .limit(limit)
            )
            editions = list((await db.execute(stmt)).scalars().all())
            return {"user_id": user_id, "count": len(editions), "items": [_serialize_edition(item, include_html=False) for item in editions]}
    except Exception as exc:
        logger.exception("Could not list editions user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list editions") from exc


@router.get("/{edition_id}")
async def get_edition(edition_id: int, include_html: bool = Query(default=True)) -> dict[str, Any]:
    """Return one edition with HTML preview content by default."""
    try:
        async with AsyncSessionLocal() as db:
            edition = await db.get(NewspaperEdition, edition_id)
            if edition is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edition not found")
            return _serialize_edition(edition, include_html=include_html)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not read edition_id=%s", edition_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not read edition") from exc


@router.delete("/{edition_id}")
async def delete_edition(edition_id: int) -> dict[str, Any]:
    """Delete a stored newspaper edition."""
    try:
        async with AsyncSessionLocal() as db:
            edition = await db.get(NewspaperEdition, edition_id)
            if edition is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edition not found")
            await db.delete(edition)
            await db.commit()
            return {"edition_id": edition_id, "deleted": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not delete edition_id=%s", edition_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete edition") from exc


def _serialize_edition(edition: NewspaperEdition, *, include_html: bool = True) -> dict[str, Any]:
    """Serialize a NewspaperEdition ORM row for API responses."""
    payload = {
        "edition_id": edition.id,
        "user_id": edition.user_id,
        "edition_date": _date_to_iso(getattr(edition, "edition_date", None)),
        "frequency": getattr(edition, "frequency", "daily"),
        "language": edition.language,
        "pdf_path": getattr(edition, "pdf_path", None),
        "metadata": edition.metadata_json or {},
        "created_at": _dt_to_iso(getattr(edition, "created_at", None)),
        "updated_at": _dt_to_iso(getattr(edition, "updated_at", None)),
    }
    if include_html:
        payload["html_content"] = edition.html_content
    return payload


def _dt_to_iso(value: Any) -> str | None:
    """Return datetime-like values as ISO text."""
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def _date_to_iso(value: Any) -> str | None:
    """Return date-like values as ISO text."""
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return None
    return str(value)
