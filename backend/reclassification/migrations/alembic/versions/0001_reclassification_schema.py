"""create reclassification tables

Revision ID: 0001_reclassification_schema
Revises:
Create Date: 2026-06-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_reclassification_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create admin reclassification tables."""
    op.create_table(
        "reclassification_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("original_labels", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("original_model", sa.String(length=80), nullable=False, server_default="unknown"),
        sa.Column("original_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("corrected_labels", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("admin_id", sa.Integer(), nullable=False, index=True),
        sa.Column("admin_username", sa.String(length=120), nullable=False),
        sa.Column("corrected_at", sa.DateTime(), nullable=False),
        sa.Column("feedback_status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("feedback_weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("verified_by", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_table(
        "feedback_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_number", sa.Integer(), nullable=False),
        sa.Column("records_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("used_in_retraining", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("retraining_id", sa.String(length=128), nullable=True),
        sa.Column("retraining_at", sa.DateTime(), nullable=True),
        sa.Column("accuracy_before", sa.Float(), nullable=True),
        sa.Column("accuracy_after", sa.Float(), nullable=True),
    )
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=120), nullable=False, unique=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False, server_default="reviewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("total_corrections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accuracy_rate", sa.Float(), nullable=False, server_default="1"),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Drop admin reclassification tables."""
    op.drop_table("admin_users")
    op.drop_table("feedback_batches")
    op.drop_table("reclassification_records")
