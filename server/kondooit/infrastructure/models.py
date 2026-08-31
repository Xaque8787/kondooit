"""SQLAlchemy ORM models.

These are infrastructure representations of database tables. They are NOT
the Kondooit domain model. The repository layer maps between these ORM
models and the pure domain entities defined in kondooit.domain.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="admin")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class GenreModel(Base):
    __tablename__ = "genres"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    tvdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CollectionModel(Base):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    poster_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    backdrop_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MovieModel(Base):
    __tablename__ = "movies"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    overview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vote_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    collection_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("collections.id"), nullable=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    tvdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    genres: Mapped[list[GenreModel]] = relationship(secondary="movie_genres")


class SeriesModel(Base):
    __tablename__ = "series"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    overview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    first_air_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_air_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    vote_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    tvdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    genres: Mapped[list[GenreModel]] = relationship(secondary="series_genres")
    seasons: Mapped[list["SeasonModel"]] = relationship(back_populates="series", cascade="all, delete-orphan")


class SeasonModel(Base):
    __tablename__ = "seasons"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    series_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("series.id"), nullable=False)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    overview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    poster_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    episode_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    air_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tvdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    series: Mapped[SeriesModel] = relationship(back_populates="seasons")
    episodes: Mapped[list["EpisodeModel"]] = relationship(back_populates="season", cascade="all, delete-orphan")


class EpisodeModel(Base):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    series_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("series.id"), nullable=False)
    season_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("seasons.id"), nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    overview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    still_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    air_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    vote_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tvdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    season: Mapped[SeasonModel] = relationship(back_populates="episodes")


# Association tables for many-to-many genre relationships
from sqlalchemy import Table, Column

movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", UUID(as_uuid=True), ForeignKey("movies.id"), primary_key=True),
    Column("genre_id", UUID(as_uuid=True), ForeignKey("genres.id"), primary_key=True),
)

series_genres = Table(
    "series_genres",
    Base.metadata,
    Column("series_id", UUID(as_uuid=True), ForeignKey("series.id"), primary_key=True),
    Column("genre_id", UUID(as_uuid=True), ForeignKey("genres.id"), primary_key=True),
)


class ProviderSettingModel(Base):
    __tablename__ = "provider_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    api_key: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="disabled")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    credentials: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ScraperModuleModel(Base):
    __tablename__ = "scraper_modules"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    module_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "local"
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ScraperSettingModel(Base):
    __tablename__ = "scraper_settings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    module_id: Mapped[str] = mapped_column(String(255), nullable=False)
    scraper_key: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("module_id", "scraper_key", name="uq_scraper_settings_module_key"),
    )
