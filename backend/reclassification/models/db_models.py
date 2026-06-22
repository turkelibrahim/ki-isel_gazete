"""Database models for the manual reclassification subsystem.

The module exposes SQLAlchemy models when SQLAlchemy is installed. In lightweight
local/test environments it also exposes dataclass fallbacks with the same field
names so the business logic remains importable without optional infrastructure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

try:  # pragma: no cover - exercised only when SQLAlchemy is installed.
    from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, JSON
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

    class Base(DeclarativeBase):
        """SQLAlchemy declarative base."""

    class ReclassificationRecord(Base):
        """Persisted admin correction."""

        __tablename__ = "reclassification_records"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        article_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
        original_labels: Mapped[list[str]] = mapped_column(JSON, default=list)
        original_model: Mapped[str] = mapped_column(String(80), default="unknown")
        original_confidence: Mapped[float] = mapped_column(Float, default=0.0)
        corrected_labels: Mapped[list[str]] = mapped_column(JSON, default=list)
        correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
        admin_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
        admin_username: Mapped[str] = mapped_column(String(120), nullable=False)
        corrected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
        feedback_status: Mapped[str] = mapped_column(String(40), default="pending")
        feedback_weight: Mapped[float] = mapped_column(Float, default=1.0)
        verified_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
        verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
        is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
        requires_verification: Mapped[bool] = mapped_column(Boolean, default=False)

    class FeedbackBatch(Base):
        """Group of processed feedback examples used for retraining."""

        __tablename__ = "feedback_batches"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        batch_number: Mapped[int] = mapped_column(Integer, nullable=False)
        records_count: Mapped[int] = mapped_column(Integer, default=0)
        created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
        used_in_retraining: Mapped[bool] = mapped_column(Boolean, default=False)
        retraining_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
        retraining_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
        accuracy_before: Mapped[float | None] = mapped_column(Float, nullable=True)
        accuracy_after: Mapped[float | None] = mapped_column(Float, nullable=True)

    class AdminUser(Base):
        """Admin account model."""

        __tablename__ = "admin_users"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
        email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
        password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
        role: Mapped[str] = mapped_column(String(40), default="reviewer")
        is_active: Mapped[bool] = mapped_column(Boolean, default=True)
        last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
        total_corrections: Mapped[int] = mapped_column(Integer, default=0)
        accuracy_rate: Mapped[float] = mapped_column(Float, default=1.0)
        failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
        locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

except Exception:  # pragma: no cover - normal in minimal execution environments.
    Base = object

    @dataclass
    class ReclassificationRecord:
        """Dataclass fallback for a persisted admin correction."""

        id: int
        article_id: str
        original_labels: list[str] = field(default_factory=list)
        original_model: str = "unknown"
        original_confidence: float = 0.0
        corrected_labels: list[str] = field(default_factory=list)
        correction_reason: str | None = None
        admin_id: int = 0
        admin_username: str = ""
        corrected_at: datetime = field(default_factory=datetime.utcnow)
        feedback_status: str = "pending"
        feedback_weight: float = 1.0
        verified_by: int | None = None
        verified_at: datetime | None = None
        is_verified: bool = False
        requires_verification: bool = False

    @dataclass
    class FeedbackBatch:
        """Dataclass fallback for feedback batches."""

        id: int
        batch_number: int
        records_count: int
        created_at: datetime = field(default_factory=datetime.utcnow)
        used_in_retraining: bool = False
        retraining_id: str | None = None
        retraining_at: datetime | None = None
        accuracy_before: float | None = None
        accuracy_after: float | None = None

    @dataclass
    class AdminUser:
        """Dataclass fallback for admin accounts."""

        id: int
        username: str
        email: str
        password_hash: str
        role: str = "reviewer"
        is_active: bool = True
        last_login: datetime | None = None
        total_corrections: int = 0
        accuracy_rate: float = 1.0
        failed_login_attempts: int = 0
        locked_until: datetime | None = None
