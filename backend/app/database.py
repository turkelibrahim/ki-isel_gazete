"""Database wiring for the FastAPI crawler backend."""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/smart_newspaper",
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


def get_engine() -> AsyncEngine:
    """Create and cache the async SQLAlchemy engine lazily."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create and cache the async session factory lazily."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _session_factory


def AsyncSessionLocal(**kwargs: Any) -> AsyncSession:
    """Return a new async database session.

    Kept as a function named like a sessionmaker so existing FastAPI code can
    use ``async with AsyncSessionLocal() as session``.
    """
    return get_session_factory()(**kwargs)
