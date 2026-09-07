"""Watch progress tracking per profile.

Revision ID: 0006_watch_progress
Revises: 0005_scraper_modules
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_watch_progress"
down_revision = "0005_scraper_modules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watch_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_key", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("external_id", sa.Integer(), nullable=False),
        sa.Column("series_external_id", sa.Integer(), nullable=True),
        sa.Column("season_number", sa.Integer(), nullable=True),
        sa.Column("episode_number", sa.Integer(), nullable=True),
        sa.Column("position_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("watched", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("content_type IN ('movie', 'episode')", name="ck_watch_progress_content_type"),
    )
    op.create_index(
        "uq_watch_progress_user_profile_content",
        "watch_progress",
        ["user_id", sa.text("COALESCE(profile_id, '00000000-0000-0000-0000-000000000000')"), "provider_key", "content_type", "external_id"],
        unique=True,
    )
    op.create_index(
        "idx_watch_progress_continue",
        "watch_progress",
        ["user_id", "profile_id", sa.text("updated_at DESC")],
        postgresql_where=sa.text("watched = false AND position_seconds > 0"),
    )
    op.create_index(
        "idx_watch_progress_watched",
        "watch_progress",
        ["user_id", "profile_id", "watched"],
        postgresql_where=sa.text("watched = true"),
    )


def downgrade() -> None:
    op.drop_table("watch_progress")
