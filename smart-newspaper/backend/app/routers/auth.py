"""JWT authentication endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import AsyncSessionLocal
from app.core.security import decode_token
from app.dependencies.auth import get_current_user
from app.models import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
auth_service = AuthService()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> dict[str, Any]:
    """Register a new USER and return access/refresh tokens."""
    try:
        async with AsyncSessionLocal() as db:
            return await auth_service.register(db, email=payload.email, password=payload.password)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Registration failed for email=%s", payload.email)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed") from exc


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> dict[str, Any]:
    """Authenticate with email/password and return access/refresh tokens."""
    try:
        async with AsyncSessionLocal() as db:
            return await auth_service.login(db, email=payload.email, password=payload.password)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Login failed for email=%s", payload.email)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed") from exc


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest) -> dict[str, Any]:
    """Exchange a refresh token for a new access/refresh token pair."""
    try:
        # Reject access tokens before opening a database session.
        decode_token(payload.refresh_token, expected_type="refresh")
        async with AsyncSessionLocal() as db:
            return await auth_service.refresh(db, refresh_token=payload.refresh_token)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Token refresh failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token refresh failed") from exc


@router.get("/me", response_model=CurrentUserResponse)
async def me(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Return the current user resolved from a valid access token."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "role": str(current_user.role or "USER").upper(),
        "language_preference": current_user.language_preference,
    }
