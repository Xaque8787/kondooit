"""Catalog application service.

Owns canonical catalog reads and evidence ingestion. The catalog service
receives provider evidence and maps it to canonical domain entities,
persisting them through repositories. It knows nothing about TMDB, TVDB,
httpx, or any specific provider — it works with the evidence data shapes
defined in provider_ports.

This is the application-layer boundary where provider evidence becomes
canonical Kondooit content (ADR-0003).
"""

from __future__ import annotations

import uuid

from kondooit.application.ports import (
    CollectionRepository,
    EpisodeRepository,
    GenreRepository,
    MovieRepository,
    SeasonRepository,
    SeriesRepository,
)
from kondooit.application.provider_ports import (
    ProviderEpisodeEvidence,
    ProviderGenreEvidence,
    ProviderMovieEvidence,
    ProviderSeasonEvidence,
    ProviderSeriesEvidence,
)
from kondooit.domain.content import Collection, Episode, Genre, Movie, Season, Series


class CatalogService:
    """Application service for canonical catalog operations."""

    def __init__(
        self,
        movie_repo: MovieRepository,
        series_repo: SeriesRepository,
        season_repo: SeasonRepository,
        episode_repo: EpisodeRepository,
        genre_repo: GenreRepository,
        collection_repo: CollectionRepository,
    ) -> None:
        self._movie_repo = movie_repo
        self._series_repo = series_repo
        self._season_repo = season_repo
        self._episode_repo = episode_repo
        self._genre_repo = genre_repo
        self._collection_repo = collection_repo

    # --- Catalog reads ---

    async def list_movies(self, session, limit: int = 20, offset: int = 0) -> list[Movie]:
        return await self._movie_repo.list(session, limit, offset)

    async def list_series(self, session, limit: int = 20, offset: int = 0) -> list[Series]:
        return await self._series_repo.list(session, limit, offset)

    async def get_movie(self, session, movie_id) -> Movie | None:
        return await self._movie_repo.get_by_id(session, uuid.UUID(movie_id))

    async def get_series(self, session, series_id) -> Series | None:
        return await self._series_repo.get_by_id(session, uuid.UUID(series_id))

    async def search_movies(self, session, query: str, limit: int = 20) -> list[Movie]:
        return await self._movie_repo.search(session, query, limit)

    async def search_series(self, session, query: str, limit: int = 20) -> list[Series]:
        return await self._series_repo.search(session, query, limit)

    async def list_genres(self, session) -> list[Genre]:
        return await self._genre_repo.get_all(session)

    async def list_collections(self, session, limit: int = 20, offset: int = 0) -> list[Collection]:
        return await self._collection_repo.list(session, limit, offset)

    async def get_collection(self, session, collection_id) -> Collection | None:
        return await self._collection_repo.get_by_id(session, uuid.UUID(collection_id))

    async def get_seasons(self, session, series_id) -> list[Season]:
        return await self._season_repo.get_by_series(session, uuid.UUID(series_id))

    async def get_episodes(self, session, season_id) -> list[Episode]:
        return await self._episode_repo.get_by_season(session, uuid.UUID(season_id))

    # --- Evidence ingestion ---

    async def ingest_movie_evidence(
        self,
        session,
        provider_key: str,
        evidence: ProviderMovieEvidence,
    ) -> Movie | None:
        """Map provider movie evidence to a canonical movie and persist it.

        If the movie already exists by external ID, returns the existing one.
        """
        if provider_key == "tmdb":
            existing = await self._movie_repo.get_by_tmdb_id(session, evidence.external_id)
            if existing is not None:
                return existing
        elif provider_key == "tvdb":
            existing = await self._movie_repo.get_by_tvdb_id(session, evidence.external_id)
            if existing is not None:
                return existing

        canonical_genres = await self._resolve_genres(session, provider_key, evidence.genres)
        collection_id = None
        if evidence.collection_external_id and evidence.collection_name:
            collection_id = await self._resolve_collection(session, provider_key, evidence)

        movie = Movie(
            id=uuid.uuid4(),
            title=evidence.title,
            overview=evidence.overview,
            release_date=evidence.release_date,
            poster_path=evidence.poster_path,
            backdrop_path=evidence.backdrop_path,
            runtime_minutes=evidence.runtime_minutes,
            vote_average=evidence.vote_average,
            genres=canonical_genres,
            collection_id=collection_id,
            tmdb_id=evidence.external_id if provider_key == "tmdb" else None,
            tvdb_id=evidence.external_id if provider_key == "tvdb" else None,
        )
        created = await self._movie_repo.create(session, movie)
        await session.commit()
        return created

    async def ingest_series_evidence(
        self,
        session,
        provider_key: str,
        evidence: ProviderSeriesEvidence,
    ) -> Series | None:
        """Map provider series evidence to a canonical series and persist it.

        Persists the series, its seasons. If the series already exists by
        external ID, returns the existing one.
        """
        if provider_key == "tmdb":
            existing = await self._series_repo.get_by_tmdb_id(session, evidence.external_id)
            if existing is not None:
                return existing
        elif provider_key == "tvdb":
            existing = await self._series_repo.get_by_tvdb_id(session, evidence.external_id)
            if existing is not None:
                return existing

        canonical_genres = await self._resolve_genres(session, provider_key, evidence.genres)

        series = Series(
            id=uuid.uuid4(),
            title=evidence.title,
            overview=evidence.overview,
            first_air_date=evidence.first_air_date,
            last_air_date=evidence.last_air_date,
            poster_path=evidence.poster_path,
            backdrop_path=evidence.backdrop_path,
            status=evidence.status,
            vote_average=evidence.vote_average,
            genres=canonical_genres,
            seasons=[],
            tmdb_id=evidence.external_id if provider_key == "tmdb" else None,
            tvdb_id=evidence.external_id if provider_key == "tvdb" else None,
        )
        created_series = await self._series_repo.create(session, series)

        for season_evidence in evidence.seasons:
            season = Season(
                id=uuid.uuid4(),
                series_id=created_series.id,
                season_number=season_evidence.season_number,
                name=season_evidence.name,
                overview=season_evidence.overview,
                poster_path=season_evidence.poster_path,
                episode_count=season_evidence.episode_count,
                air_date=season_evidence.air_date,
                tmdb_id=season_evidence.external_id if provider_key == "tmdb" else None,
                tvdb_id=season_evidence.external_id if provider_key == "tvdb" else None,
            )
            await self._season_repo.create(session, season)

        await session.commit()
        return await self._series_repo.get_by_id(session, created_series.id)

    async def _resolve_genres(
        self,
        session,
        provider_key: str,
        genres: list[ProviderGenreEvidence],
    ) -> list[Genre]:
        """Map provider genre evidence to canonical genres. Creates if missing."""
        result: list[Genre] = []
        for g in genres:
            if provider_key == "tmdb":
                existing = await self._genre_repo.get_by_tmdb_id(session, g.external_id)
                if existing is not None:
                    result.append(existing)
                    continue
            new_genre = Genre(
                id=uuid.uuid4(),
                name=g.name,
                tmdb_id=g.external_id if provider_key == "tmdb" else None,
                tvdb_id=g.external_id if provider_key == "tvdb" else None,
            )
            created = await self._genre_repo.create(session, new_genre)
            result.append(created)
        return result

    async def _resolve_collection(
        self,
        session,
        provider_key: str,
        evidence: ProviderMovieEvidence,
    ) -> uuid.UUID | None:
        """Map provider collection evidence to a canonical collection."""
        if not evidence.collection_external_id or not evidence.collection_name:
            return None
        collection = Collection(
            id=uuid.uuid4(),
            name=evidence.collection_name,
            description=evidence.collection_overview or "",
            tmdb_id=evidence.collection_external_id if provider_key == "tmdb" else None,
        )
        created = await self._collection_repo.create(session, collection)
        return created.id
