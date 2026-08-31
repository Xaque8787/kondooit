"""Canonical content domain entities.

These are pure Python domain objects. They know nothing about SQLAlchemy,
PostgreSQL, or any other infrastructure concern. Infrastructure-layer
ORM models map to and from these entities at repository boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from uuid import UUID


class ContentType(str, Enum):
    """Top-level content type for catalog navigation."""
    MOVIE = "movie"
    SERIES = "series"


@dataclass(frozen=True)
class Genre:
    """A genre category applied to content."""
    id: UUID
    name: str
    tmdb_id: int | None = None
    tvdb_id: int | None = None


@dataclass(frozen=True)
class Collection:
    """A curated collection of content items (e.g. 'Marvel Cinematic Universe')."""
    id: UUID
    name: str
    description: str = ""
    poster_url: str | None = None
    backdrop_url: str | None = None
    tmdb_id: int | None = None


@dataclass(frozen=True)
class Movie:
    """Canonical movie entity owned by Kondooit."""
    id: UUID
    title: str
    overview: str = ""
    release_date: date | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    runtime_minutes: int | None = None
    vote_average: float | None = None
    genres: list[Genre] = field(default_factory=list)
    collection_id: UUID | None = None
    # External identifiers — evidence, not canonical identity
    tmdb_id: int | None = None
    tvdb_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Season:
    """Canonical season entity."""
    id: UUID
    series_id: UUID
    season_number: int
    name: str = ""
    overview: str = ""
    poster_path: str | None = None
    episode_count: int = 0
    air_date: date | None = None
    tmdb_id: int | None = None
    tvdb_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Episode:
    """Canonical episode entity."""
    id: UUID
    series_id: UUID
    season_id: UUID
    episode_number: int
    name: str = ""
    overview: str = ""
    still_path: str | None = None
    runtime_minutes: int | None = None
    air_date: date | None = None
    vote_average: float | None = None
    tmdb_id: int | None = None
    tvdb_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Series:
    """Canonical series entity owned by Kondooit."""
    id: UUID
    title: str
    overview: str = ""
    first_air_date: date | None = None
    last_air_date: date | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    status: str = ""
    vote_average: float | None = None
    genres: list[Genre] = field(default_factory=list)
    seasons: list[Season] = field(default_factory=list)
    # External identifiers — evidence, not canonical identity
    tmdb_id: int | None = None
    tvdb_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
