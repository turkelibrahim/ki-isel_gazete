"""JWT authentication service for register, login and token refresh."""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import User

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication use cases backed by the users table."""

    async def register(self, db: AsyncSession, email: str, password: str) -> dict:
        normalized_email = email.strip().lower()
        existing = await self.get_user_by_email(db, normalized_email)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        user = User(
            id=str(uuid4()),
            email=normalized_email,
            password_hash=hash_password(password),
            role="USER",
            language_preference="tr",
        )
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError as exc:
            await db.rollback()
            logger.info("Duplicate email during registration: %s", normalized_email)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc
        return self._token_response(user)

    async def login(self, db: AsyncSession, email: str, password: str) -> dict:
        normalized_email = email.strip().lower()
        user = await self.get_user_by_email(db, normalized_email)
        if user is None or not verify_password(password, getattr(user, "password_hash", None)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        return self._token_response(user)

    async def refresh(self, db: AsyncSession, refresh_token: str) -> dict:
        payload = decode_token(refresh_token, expected_type="refresh")
        user = await self.get_user_by_id(db, str(payload["sub"]))
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token")
        return self._token_response(user)

    async def get_user_by_id(self, db: AsyncSession, user_id: int | str) -> User | None:
        result = await db.execute(select(User).where(User.id == str(user_id)))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email.strip().lower()))
        return result.scalar_one_or_none()

    def _token_response(self, user: User) -> dict:
        role = str(getattr(user, "role", "USER") or "USER").upper()
        user_id = str(user.id)
        return {
            "access_token": create_access_token(user_id=user_id, role=role),
            "refresh_token": create_refresh_token(user_id=user_id, role=role),
            "token_type": "bearer",
            "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_expires_in_days": REFRESH_TOKEN_EXPIRE_DAYS,
            "user_id": user_id,
            "role": role,
        }
