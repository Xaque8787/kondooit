"""Discovery application service.

Per ADR-0009, the primary browsing experience is provider-driven.
Per ADR-0010, providers declare which discovery capabilities they support.
Per ADR-0011, providers are selected by priority with three-way condition
handling: unsupported capability, zero results, and request failure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from kondooit.application.provider_ports import (
    DiscoveryCapability,
    MetadataProvider,
    MetadataProviderType,
    ProviderConfig,
    ProviderGenreEvidence,
    ProviderMovieEvidence,
    ProviderSeriesEvidence,
    ProviderStatus,
)
from kondooit.application.metadata_service import ProviderRegistry
from kondooit.application.ports import ProviderConfigRepository

logger = logging.getLogger(__name__)


class ProviderCallOutcome(Enum):
    SUCCESS = "success"
    EMPTY = "empty"
    FAILURE = "failure"


@dataclass(frozen=True)
class DiscoveredMovie:
    """A movie discovered from a provider."""
    title: str
    overview: str = ""
    release_date: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    vote_average: float | None = None
    provider_key: str = ""
    external_id: int = 0


@dataclass(frozen=True)
class DiscoveredSeries:
    """A TV series discovered from a provider."""
    title: str
    overview: str = ""
    first_air_date: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    vote_average: float | None = None
    provider_key: str = ""
    external_id: int = 0


@dataclass(frozen=True)
class DiscoveredGenre:
    """A genre discovered from a metadata provider."""
    name: str
    external_id: int = 0
    content_type: str = ""
    provider_key: str = ""


@dataclass(frozen=True)
class DiscoverySection:
    """A named section of discovered content."""
    title: str
    section_key: str = ""
    provider_key: str = ""
    movies: list[DiscoveredMovie] = field(default_factory=list)
    series: list[DiscoveredSeries] = field(default_factory=list)


class DiscoveryService:
    """Application service for provider-driven content discovery.

    Per ADR-0011:
    - Discovery uses a primary provider with per-section capability fallback.
    - Search uses priority-ordered sequential fallback.
    - Results come from a single provider per section/query — never merged.
    - Three conditions are distinguished: unsupported, empty, failure.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        config_repo: ProviderConfigRepository,
    ) -> None:
        self._registry = registry
        self._config_repo = config_repo

    async def get_landing_page(self, session, limit: int = 10) -> list[DiscoverySection]:
        """Return discovery sections for the landing page.

        Uses the primary provider (highest-priority enabled) for all sections
        it supports. Falls back to lower-priority providers only for capabilities
        the primary provider does not support or where its request fails.
        """
        providers = await self._get_enabled_providers(session)
        if not providers:
            return []

        section_defs = [
            (DiscoveryCapability.TRENDING_MOVIES, "Trending Movies", "trending_movies"),
            (DiscoveryCapability.NOW_PLAYING_MOVIES, "Now Playing", "now_playing_movies"),
            (DiscoveryCapability.UPCOMING_MOVIES, "Upcoming Movies", "upcoming_movies"),
            (DiscoveryCapability.POPULAR_MOVIES, "Popular Movies", "popular_movies"),
            (DiscoveryCapability.TRENDING_SERIES, "Trending TV Shows", "trending_series"),
            (DiscoveryCapability.POPULAR_SERIES, "Popular TV Shows", "popular_series"),
        ]

        sections: list[DiscoverySection] = []

        for capability, title, section_key in section_defs:
            section = await self._resolve_discovery_section(
                providers, capability, title, section_key, limit
            )
            if section is not None:
                sections.append(section)

        return sections

    async def search(self, session, query: str) -> list[DiscoveredMovie | DiscoveredSeries]:
        """Search across providers with priority-ordered fallback."""
        providers = await self._get_enabled_providers(session)
        if not providers:
            return []

        movies = await self._search_movies_with_fallback(providers, query)
        series = await self._search_series_with_fallback(providers, query)
        return movies + series

    async def search_movies(self, session, query: str) -> list[DiscoveredMovie]:
        """Search for movies with priority-ordered fallback."""
        providers = await self._get_enabled_providers(session)
        if not providers:
            return []
        return await self._search_movies_with_fallback(providers, query)

    async def search_series(self, session, query: str) -> list[DiscoveredSeries]:
        """Search for TV series with priority-ordered fallback."""
        providers = await self._get_enabled_providers(session)
        if not providers:
            return []
        return await self._search_series_with_fallback(providers, query)

    async def get_movie_details(
        self, session, provider_key: str, external_id: int
    ) -> ProviderMovieEvidence | None:
        """Fetch full movie details from a specific provider."""
        config = await self._get_enabled_config(session, provider_key)
        if config is None:
            return None
        provider = self._registry.get(provider_key)
        if provider is None:
            return None
        caps = provider.supported_discoveries()
        if DiscoveryCapability.MOVIE_DETAILS not in caps:
            return None
        try:
            return await provider.get_movie(config, external_id)
        except Exception as exc:
            logger.error("Provider %s failed get_movie(%d): %s", provider_key, external_id, exc)
            return None

    async def get_series_details(
        self, session, provider_key: str, external_id: int
    ) -> ProviderSeriesEvidence | None:
        """Fetch full series details from a specific provider."""
        config = await self._get_enabled_config(session, provider_key)
        if config is None:
            return None
        provider = self._registry.get(provider_key)
        if provider is None:
            return None
        caps = provider.supported_discoveries()
        if DiscoveryCapability.SERIES_DETAILS not in caps:
            return None
        try:
            return await provider.get_series(config, external_id)
        except Exception as exc:
            logger.error("Provider %s failed get_series(%d): %s", provider_key, external_id, exc)
            return None

    async def get_season_details(
        self, session, provider_key: str, series_external_id: int, season_number: int
    ) -> "ProviderSeasonEvidence | None":
        """Fetch season details with episodes from a specific provider."""
        from kondooit.application.provider_ports import ProviderSeasonEvidence  # noqa: F811
        config = await self._get_enabled_config(session, provider_key)
        if config is None:
            return None
        provider = self._registry.get(provider_key)
        if provider is None:
            return None
        caps = provider.supported_discoveries()
        if DiscoveryCapability.SEASON_DETAILS not in caps:
            return None
        try:
            return await provider.get_season(config, series_external_id, season_number)
        except Exception as exc:
            logger.error("Provider %s failed get_season(%d, %d): %s", provider_key, series_external_id, season_number, exc)
            return None

    async def get_genres(self, session, content_type: str | None = None) -> list[DiscoveredGenre]:
        """Get genres from the primary provider that supports genre capability.

        If content_type is 'movie' or 'series', fetches only that type.
        If None or 'all', fetches both movie and TV genres.
        """
        providers = await self._get_enabled_providers(session)
        if not providers:
            return []

        results: list[DiscoveredGenre] = []

        fetch_movie = content_type in (None, "all", "movie")
        fetch_series = content_type in (None, "all", "series")

        if fetch_movie:
            for provider, config in providers:
                caps = provider.supported_discoveries()
                if DiscoveryCapability.GENRES_MOVIE in caps:
                    try:
                        genres = await provider.get_genres(config, MetadataProviderType.MOVIE)
                        results.extend(
                            DiscoveredGenre(
                                name=g.name,
                                external_id=g.external_id,
                                content_type="movie",
                                provider_key=provider.info().key,
                            )
                            for g in genres
                        )
                        break
                    except Exception as exc:
                        logger.error("Provider %s failed get_genres(movie): %s", config.key, exc)
                        continue

        if fetch_series:
            for provider, config in providers:
                caps = provider.supported_discoveries()
                if DiscoveryCapability.GENRES_TV in caps:
                    try:
                        genres = await provider.get_genres(config, MetadataProviderType.SERIES)
                        results.extend(
                            DiscoveredGenre(
                                name=g.name,
                                external_id=g.external_id,
                                content_type="series",
                                provider_key=provider.info().key,
                            )
                            for g in genres
                        )
                        break
                    except Exception as exc:
                        logger.error("Provider %s failed get_genres(tv): %s", config.key, exc)
                        continue

        return results

    async def discover_by_genre(
        self, session, genre_ids: list[int], content_type: str = "all", page: int = 1
    ) -> list[DiscoveredMovie | DiscoveredSeries]:
        """Discover content filtered by genre IDs using provider discover APIs.

        Uses priority-ordered fallback per ADR-0011.
        content_type: 'movie', 'series', or 'all'.
        """
        providers = await self._get_enabled_providers(session)
        if not providers:
            return []

        results: list[DiscoveredMovie | DiscoveredSeries] = []

        if content_type in ("all", "movie"):
            for provider, config in providers:
                caps = provider.supported_discoveries()
                if DiscoveryCapability.DISCOVER_MOVIES not in caps:
                    continue
                try:
                    evidence = await provider.discover_movies(config, genre_ids=genre_ids, page=page)
                    if evidence:
                        results.extend(self._evidence_to_discovered_movies(evidence, provider.info().key))
                        break
                except Exception as exc:
                    logger.error("Provider %s discover_movies failed: %s", config.key, exc)
                    continue

        if content_type in ("all", "series"):
            for provider, config in providers:
                caps = provider.supported_discoveries()
                if DiscoveryCapability.DISCOVER_SERIES not in caps:
                    continue
                try:
                    evidence = await provider.discover_series(config, genre_ids=genre_ids, page=page)
                    if evidence:
                        results.extend(self._evidence_to_discovered_series(evidence, provider.info().key))
                        break
                except Exception as exc:
                    logger.error("Provider %s discover_series failed: %s", config.key, exc)
                    continue

        return results

    async def get_section(
        self, session, section_key: str, page: int = 1, limit: int = 20
    ) -> DiscoverySection | None:
        """Get a full section by key with pagination."""
        providers = await self._get_enabled_providers(session)
        if not providers:
            return None

        cap_map = {
            "trending_movies": DiscoveryCapability.TRENDING_MOVIES,
            "now_playing_movies": DiscoveryCapability.NOW_PLAYING_MOVIES,
            "upcoming_movies": DiscoveryCapability.UPCOMING_MOVIES,
            "popular_movies": DiscoveryCapability.POPULAR_MOVIES,
            "trending_series": DiscoveryCapability.TRENDING_SERIES,
            "popular_series": DiscoveryCapability.POPULAR_SERIES,
        }
        title_map = {
            "trending_movies": "Trending Movies",
            "now_playing_movies": "Now Playing",
            "upcoming_movies": "Upcoming Movies",
            "popular_movies": "Popular Movies",
            "trending_series": "Trending TV Shows",
            "popular_series": "Popular TV Shows",
        }

        capability = cap_map.get(section_key)
        title = title_map.get(section_key, section_key)
        if capability is None:
            return None

        return await self._resolve_discovery_section(
            providers, capability, title, section_key, limit, page
        )

    def list_provider_capabilities(self) -> dict[str, set[DiscoveryCapability]]:
        """Return capabilities for all registered providers."""
        result = {}
        for info in self._registry.list_providers():
            provider = self._registry.get(info.key)
            if provider:
                result[info.key] = provider.supported_discoveries()
        return result

    # --- Private methods ---

    async def _resolve_discovery_section(
        self,
        providers: list[tuple[MetadataProvider, ProviderConfig]],
        capability: DiscoveryCapability,
        title: str,
        section_key: str,
        limit: int,
        page: int = 1,
    ) -> DiscoverySection | None:
        """Resolve a discovery section using priority-based provider selection.

        Per ADR-0011:
        - Condition A (unsupported): skip, try next provider
        - Condition B (zero results): section is absent (primary has authority)
        - Condition C (request failure): section is absent, try next provider
        """
        is_movie_cap = capability in {
            DiscoveryCapability.TRENDING_MOVIES,
            DiscoveryCapability.NOW_PLAYING_MOVIES,
            DiscoveryCapability.UPCOMING_MOVIES,
            DiscoveryCapability.POPULAR_MOVIES,
        }

        for provider, config in providers:
            caps = provider.supported_discoveries()
            if capability not in caps:
                continue

            if is_movie_cap:
                outcome, movies = await self._call_movie_method(provider, config, capability, page)
                if outcome == ProviderCallOutcome.SUCCESS:
                    return DiscoverySection(
                        title=title,
                        section_key=section_key,
                        provider_key=config.key,
                        movies=movies[:limit],
                    )
                elif outcome == ProviderCallOutcome.EMPTY:
                    return None
                else:
                    continue
            else:
                outcome, series = await self._call_series_method(provider, config, capability, page)
                if outcome == ProviderCallOutcome.SUCCESS:
                    return DiscoverySection(
                        title=title,
                        section_key=section_key,
                        provider_key=config.key,
                        series=series[:limit],
                    )
                elif outcome == ProviderCallOutcome.EMPTY:
                    return None
                else:
                    continue

        return None

    async def _search_movies_with_fallback(
        self, providers: list[tuple[MetadataProvider, ProviderConfig]], query: str
    ) -> list[DiscoveredMovie]:
        """Search movies using priority-ordered sequential fallback."""
        for provider, config in providers:
            caps = provider.supported_discoveries()
            if DiscoveryCapability.SEARCH_MOVIES not in caps:
                continue
            try:
                evidence_list = await provider.search_movies(config, query)
                movies = self._evidence_to_discovered_movies(evidence_list, provider.info().key)
                if movies:
                    return movies
            except Exception as exc:
                logger.error("Provider %s search_movies failed: %s", config.key, exc)
                continue
        return []

    async def _search_series_with_fallback(
        self, providers: list[tuple[MetadataProvider, ProviderConfig]], query: str
    ) -> list[DiscoveredSeries]:
        """Search series using priority-ordered sequential fallback."""
        for provider, config in providers:
            caps = provider.supported_discoveries()
            if DiscoveryCapability.SEARCH_SERIES not in caps:
                continue
            try:
                evidence_list = await provider.search_series(config, query)
                series = self._evidence_to_discovered_series(evidence_list, provider.info().key)
                if series:
                    return series
            except Exception as exc:
                logger.error("Provider %s search_series failed: %s", config.key, exc)
                continue
        return []

    async def _call_movie_method(
        self, provider: MetadataProvider, config: ProviderConfig,
        capability: DiscoveryCapability, page: int = 1,
    ) -> tuple[ProviderCallOutcome, list[DiscoveredMovie]]:
        """Call a movie discovery method, returning outcome + results."""
        method_map = {
            DiscoveryCapability.TRENDING_MOVIES: "get_trending_movies",
            DiscoveryCapability.NOW_PLAYING_MOVIES: "get_now_playing_movies",
            DiscoveryCapability.UPCOMING_MOVIES: "get_upcoming_movies",
            DiscoveryCapability.POPULAR_MOVIES: "get_popular_movies",
        }
        method_name = method_map.get(capability)
        if not method_name:
            return ProviderCallOutcome.EMPTY, []

        try:
            method = getattr(provider, method_name)
            evidence_list = await method(config, page=page)
            movies = self._evidence_to_discovered_movies(evidence_list, provider.info().key)
            if movies:
                return ProviderCallOutcome.SUCCESS, movies
            return ProviderCallOutcome.EMPTY, []
        except Exception as exc:
            logger.error("Provider %s %s failed: %s", config.key, method_name, exc)
            return ProviderCallOutcome.FAILURE, []

    async def _call_series_method(
        self, provider: MetadataProvider, config: ProviderConfig,
        capability: DiscoveryCapability, page: int = 1,
    ) -> tuple[ProviderCallOutcome, list[DiscoveredSeries]]:
        """Call a series discovery method, returning outcome + results."""
        method_map = {
            DiscoveryCapability.TRENDING_SERIES: "get_trending_series",
            DiscoveryCapability.POPULAR_SERIES: "get_popular_series",
        }
        method_name = method_map.get(capability)
        if not method_name:
            return ProviderCallOutcome.EMPTY, []

        try:
            method = getattr(provider, method_name)
            evidence_list = await method(config, page=page)
            series = self._evidence_to_discovered_series(evidence_list, provider.info().key)
            if series:
                return ProviderCallOutcome.SUCCESS, series
            return ProviderCallOutcome.EMPTY, []
        except Exception as exc:
            logger.error("Provider %s %s failed: %s", config.key, method_name, exc)
            return ProviderCallOutcome.FAILURE, []

    def _evidence_to_discovered_movies(
        self, evidence_list: list[ProviderMovieEvidence], provider_key: str
    ) -> list[DiscoveredMovie]:
        return [
            DiscoveredMovie(
                title=e.title,
                overview=e.overview,
                release_date=e.release_date.isoformat() if e.release_date else None,
                poster_path=e.poster_path,
                backdrop_path=e.backdrop_path,
                vote_average=e.vote_average,
                provider_key=provider_key,
                external_id=e.external_id,
            )
            for e in evidence_list
        ]

    def _evidence_to_discovered_series(
        self, evidence_list: list[ProviderSeriesEvidence], provider_key: str
    ) -> list[DiscoveredSeries]:
        return [
            DiscoveredSeries(
                title=e.title,
                overview=e.overview,
                first_air_date=e.first_air_date.isoformat() if e.first_air_date else None,
                poster_path=e.poster_path,
                backdrop_path=e.backdrop_path,
                vote_average=e.vote_average,
                provider_key=provider_key,
                external_id=e.external_id,
            )
            for e in evidence_list
        ]

    async def _get_enabled_providers(self, session) -> list[tuple[MetadataProvider, ProviderConfig]]:
        """Get enabled providers ordered by priority (ascending)."""
        configs = await self._config_repo.get_all(session)
        result = []
        for config in configs:
            if config.status != ProviderStatus.ENABLED:
                continue
            provider = self._registry.get(config.key)
            if provider is not None:
                result.append((provider, config))
        return result

    async def _get_enabled_config(self, session, key: str) -> ProviderConfig | None:
        config = await self._config_repo.get(session, key)
        if config is None or config.status != ProviderStatus.ENABLED:
            return None
        return config
