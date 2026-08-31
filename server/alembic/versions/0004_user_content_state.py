"""Add user_content_state table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_content_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_key", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("external_id", sa.Integer(), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_following", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_user_content_state_ref",
        "user_content_state",
        ["user_id", "provider_key", "content_type", "external_id"],
    )
    op.create_index(
        "ix_user_content_state_favorites",
        "user_content_state",
        ["user_id", "is_favorite"],
    )
    op.create_index(
        "ix_user_content_state_following",
        "user_content_state",
        ["user_id", "is_following"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_content_state_following", table_name="user_content_state")
    op.drop_index("ix_user_content_state_favorites", table_name="user_content_state")
    op.drop_constraint("uq_user_content_state_ref", "user_content_state")
    op.drop_table("user_content_state")
