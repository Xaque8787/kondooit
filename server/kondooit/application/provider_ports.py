"""Metadata provider port definitions.

This is the application-layer interface for metadata providers. It is
intentionally scoped to METADATA ONLY — it does not generalize to source
discovery, acquisition, playback, or any other provider capability.

TMDB and TVDB are concrete implementations of this interface. The domain
and application layers know only this interface; they never reference
TMDB or TVDB directly.

Per ADR-0003, providers supply evidence about content (IDs, metadata).
The core establishes canonical content identity. Providers do not own
identity.

Per ADR-0010, providers declare which discovery capabilities they
support. The aggregation layer only calls capabilities a provider
declares. This avoids forcing providers to implement fake equivalents
of functionality they do not have.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class MetadataProviderType(str, Enum):
    """The kind of metadata a provider supplies."""
    MOVIE = "movie"
    SERIES = "series"


class ProviderStatus(str, Enum):
    """Whether a provider is enabled or disabled."""
    ENABLED = "enabled"
    DISABLED = "disabled"


class DiscoveryCapability(str, Enum):
    """Discovery operations a metadata provider may support.

    Per ADR-0010, providers declare which of these they support. The
    aggregation layer only calls capabilities a provider declares.
    """
    SEARCH_MOVIES = "search_movies"
    SEARCH_SERIES = "search_series"
    TRENDING_MOVIES = "trending_movies"
    TRENDING_SERIES = "trending_series"
    NOW_PLAYING_MOVIES = "now_playing_movies"
    UPCOMING_MOVIES = "upcoming_movies"
    POPULAR_MOVIES = "popular_movies"
    POPULAR_SERIES = "popular_series"
    DISCOVER_MOVIES = "discover_movies"
    DISCOVER_SERIES = "discover_series"
    GENRES_MOVIE = "genres_movie"
    GENRES_TV = "genres_tv"
    MOVIE_DETAILS = "movie_details"
    SERIES_DETAILS = "series_details"
    SEASON_DETAILS = "season_details"


@dataclass(frozen=True)
class ProviderInfo:
    """Static information about a metadata provider."""
    key: str
    name: str
    description: str
    supports: list[MetadataProviderType]
    requires_api_key: bool
    capabilities: list[DiscoveryCapability] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderGenreEvidence:
    """Genre evidence from a metadata provider."""
    external_id: int
    name: str
    content_type: MetadataProviderType | None = None


@dataclass(frozen=True)
class ProviderMovieEvidence:
    """Movie metadata evidence from a provider.

    Per ADR-0003, this is evidence — not canonical identity. The core
    maps this to canonical content.
    """
    external_id: int
    title: str
    overview: str = ""
    release_date: date | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    runtime_minutes: int | None = None
    vote_average: float | None = None
    genres: list[ProviderGenreEvidence] = field(default_factory=list)
    collection_external_id: int | None = None
    collection_name: str | None = None
    collection_overview: str = None


@dataclass(frozen=True)
class ProviderEpisodeEvidence:
    """Episode metadata evidence from a provider."""
    external_id: int
    season_number: int
    episode_number: int
    name: str = ""
    overview: str = ""
    still_path: str | None = None
    runtime_minutes: int | None = None
    air_date: date | None = None
    vote_average: float | None = None


@dataclass(frozen=True)
class ProviderSeasonEvidence:
    """Season metadata evidence from a provider."""
    external_id: int
    season_number: int
    name: str = ""
    overview: str = ""
    poster_path: str | None = None
    episode_count: int = 0
    air_date: date | None = None
    episodes: list[ProviderEpisodeEvidence] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderSeriesEvidence:
    """Series metadata evidence from a provider."""
    external_id: int
    title: str
    overview: str = ""
    first_air_date: date | None = None
    last_air_date: date | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    status: str = ""
    vote_average: float | None = None
    genres: list[ProviderGenreEvidence] = field(default_factory=list)
    seasons: list[ProviderSeasonEvidence] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for a metadata provider instance."""
    key: str
    api_key: str = ""
    status: ProviderStatus = ProviderStatus.DISABLED
    priority: int = 100


class MetadataProvider(ABC):
    """Abstract interface for metadata providers.

    This interface is scoped to metadata retrieval only. It does not
    handle source discovery, acquisition, playback, or any other provider
    capability. Those will be defined as separate interfaces when their
    milestones arrive.

    Per ADR-0010, providers declare which discovery capabilities they
    support via supported_discoveries(). The aggregation layer checks
    this before calling any discovery method.
    """

    @abstractmethod
    def info(self) -> ProviderInfo:
        """Return static information about this provider."""
        ...

    @abstractmethod
    def supported_discoveries(self) -> set[DiscoveryCapability]:
        """Return the set of discovery capabilities this provider supports."""
        ...

    @abstractmethod
    async def test_connection(self, config: ProviderConfig) -> bool:
        """Test whether the provider is reachable with the given config."""
        ...

    @abstractmethod
    async def search_movies(self, config: ProviderConfig, query: str, page: int = 1) -> list[ProviderMovieEvidence]:
        """Search for movies by title."""
        ...

    @abstractmethod
    async def get_movie(self, config: ProviderConfig, external_id: int) -> ProviderMovieEvidence | None:
        """Retrieve full movie metadata by external ID."""
        ...

    @abstractmethod
    async def search_series(self, config: ProviderConfig, query: str, page: int = 1) -> list[ProviderSeriesEvidence]:
        """Search for TV series by title."""
        ...

    @abstractmethod
    async def get_series(self, config: ProviderConfig, external_id: int) -> ProviderSeriesEvidence | None:
        """Retrieve full series metadata by external ID."""
        ...

    @abstractmethod
    async def get_trending_movies(self, config: ProviderConfig, page: int = 1) -> list[ProviderMovieEvidence]:
        """Retrieve trending/popular movies."""
        ...

    @abstractmethod
    async def get_trending_series(self, config: ProviderConfig, page: int = 1) -> list[ProviderSeriesEvidence]:
        """Retrieve trending/popular TV series."""
        ...

    async def get_now_playing_movies(self, config: ProviderConfig, page: int = 1) -> list[ProviderMovieEvidence]:
        """Retrieve movies currently in theaters. Override if supported."""
        return []

    async def get_upcoming_movies(self, config: ProviderConfig, page: int = 1) -> list[ProviderMovieEvidence]:
        """Retrieve upcoming movie releases. Override if supported."""
        return []

    async def get_popular_movies(self, config: ProviderConfig, page: int = 1) -> list[ProviderMovieEvidence]:
        """Retrieve popular movies. Override if supported."""
        return []

    async def get_popular_series(self, config: ProviderConfig, page: int = 1) -> list[ProviderSeriesEvidence]:
        """Retrieve popular TV series. Override if supported."""
        return []

    @abstractmethod
    async def get_genres(self, config: ProviderConfig, content_type: MetadataProviderType) -> list[ProviderGenreEvidence]:
        """Retrieve the genre list for movies or series."""
        ...

    async def discover_movies(
        self, config: ProviderConfig, genre_ids: list[int] | None = None, page: int = 1
    ) -> list[ProviderMovieEvidence]:
        """Discover movies with optional genre filtering. Override if supported."""
        return []

    async def discover_series(
        self, config: ProviderConfig, genre_ids: list[int] | None = None, page: int = 1
    ) -> list[ProviderSeriesEvidence]:
        """Discover series with optional genre filtering. Override if supported."""
        return []

    async def get_season(
        self, config: ProviderConfig, series_external_id: int, season_number: int
    ) -> ProviderSeasonEvidence | None:
        """Retrieve season details including episodes. Override if supported."""
        return None
