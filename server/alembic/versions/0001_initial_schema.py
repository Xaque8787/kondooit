"""Initial schema — complete current state of all tables.

Revision ID: 0001
Revises:
Create Date: 2026-08-17
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="admin"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Genres
    op.create_table(
        "genres",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("tmdb_id", sa.Integer, nullable=True, unique=True),
        sa.Column("tvdb_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Collections
    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("poster_url", sa.String(1024), nullable=True),
        sa.Column("backdrop_url", sa.String(1024), nullable=True),
        sa.Column("tmdb_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Movies
    op.create_table(
        "movies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("overview", sa.Text, nullable=False, server_default=""),
        sa.Column("release_date", sa.Date, nullable=True),
        sa.Column("poster_path", sa.String(1024), nullable=True),
        sa.Column("backdrop_path", sa.String(1024), nullable=True),
        sa.Column("runtime_minutes", sa.Integer, nullable=True),
        sa.Column("vote_average", sa.Float, nullable=True),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("collections.id"), nullable=True),
        sa.Column("tmdb_id", sa.Integer, nullable=True, unique=True),
        sa.Column("tvdb_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Series
    op.create_table(
        "series",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("overview", sa.Text, nullable=False, server_default=""),
        sa.Column("first_air_date", sa.Date, nullable=True),
        sa.Column("last_air_date", sa.Date, nullable=True),
        sa.Column("poster_path", sa.String(1024), nullable=True),
        sa.Column("backdrop_path", sa.String(1024), nullable=True),
        sa.Column("status", sa.String(100), nullable=False, server_default=""),
        sa.Column("vote_average", sa.Float, nullable=True),
        sa.Column("tmdb_id", sa.Integer, nullable=True, unique=True),
        sa.Column("tvdb_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Seasons
    op.create_table(
        "seasons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("series_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("series.id"), nullable=False),
        sa.Column("season_number", sa.Integer, nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("overview", sa.Text, nullable=False, server_default=""),
        sa.Column("poster_path", sa.String(1024), nullable=True),
        sa.Column("episode_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("air_date", sa.Date, nullable=True),
        sa.Column("tmdb_id", sa.Integer, nullable=True),
        sa.Column("tvdb_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Episodes
    op.create_table(
        "episodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("series_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("series.id"), nullable=False),
        sa.Column("season_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seasons.id"), nullable=False),
        sa.Column("episode_number", sa.Integer, nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("overview", sa.Text, nullable=False, server_default=""),
        sa.Column("still_path", sa.String(1024), nullable=True),
        sa.Column("runtime_minutes", sa.Integer, nullable=True),
        sa.Column("air_date", sa.Date, nullable=True),
        sa.Column("vote_average", sa.Float, nullable=True),
        sa.Column("tmdb_id", sa.Integer, nullable=True),
        sa.Column("tvdb_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Association tables
    op.create_table(
        "movie_genres",
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("movies.id"), primary_key=True),
        sa.Column("genre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("genres.id"), primary_key=True),
    )

    op.create_table(
        "series_genres",
        sa.Column("series_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("series.id"), primary_key=True),
        sa.Column("genre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("genres.id"), primary_key=True),
    )

    # Provider settings (metadata + source providers)
    op.create_table(
        "provider_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("api_key", sa.String(1024), nullable=False, server_default=""),
        sa.Column("status", sa.String(50), nullable=False, server_default="disabled"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("credentials", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # User content state (favorites/following)
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

    # Scraper modules (installed source resolver modules)
    op.create_table(
        "scraper_modules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("module_id", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_path", sa.String(1024), nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Scraper settings (per-scraper toggle within a module)
    op.create_table(
        "scraper_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("module_id", sa.String(255), nullable=False),
        sa.Column("scraper_key", sa.String(255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_scraper_settings_module_key",
        "scraper_settings",
        ["module_id", "scraper_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_scraper_settings_module_key", "scraper_settings")
    op.drop_table("scraper_settings")
    op.drop_table("scraper_modules")
    op.drop_index("ix_user_content_state_following", table_name="user_content_state")
    op.drop_index("ix_user_content_state_favorites", table_name="user_content_state")
    op.drop_constraint("uq_user_content_state_ref", "user_content_state")
    op.drop_table("user_content_state")
    op.drop_table("provider_settings")
    op.drop_table("series_genres")
    op.drop_table("movie_genres")
    op.drop_table("episodes")
    op.drop_table("seasons")
    op.drop_table("series")
    op.drop_table("movies")
    op.drop_table("collections")
    op.drop_table("genres")
    op.drop_table("users")
