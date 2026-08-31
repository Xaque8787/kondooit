"""Catalog API endpoints.

These endpoints expose the canonical Kondooit catalog — movies, series,
seasons, episodes, genres, and collections. They know nothing about
TMDB, TVDB, or any metadata provider. The catalog is provider-agnostic.
"""

from __future__ import annotations

from litestar import Controller, get
from litestar.exceptions import HTTPException
from litestar.params import Parameter
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from kondooit.application.catalog_service import CatalogService


class GenreResponse(BaseModel):
    id: str
    name: str
    tmdb_id: int | None = None
    tvdb_id: int | None = None


class CollectionResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    poster_url: str | None = None
    backdrop_url: str | None = None
    tmdb_id: int | None = None


class MovieResponse(BaseModel):
    id: str
    title: str
    overview: str = ""
    release_date: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    runtime_minutes: int | None = None
    vote_average: float | None = None
    genres: list[GenreResponse] = Field(default_factory=list)
    collection_id: str | None = None
    tmdb_id: int | None = None
    tvdb_id: int | None = None


class SeasonResponse(BaseModel):
    id: str
    series_id: str
    season_number: int
    name: str = ""
    overview: str = ""
    poster_path: str | None = None
    episode_count: int = 0
    air_date: str | None = None
    tmdb_id: int | None = None
    tvdb_id: int | None = None


class EpisodeResponse(BaseModel):
    id: str
    series_id: str
    season_id: str
    episode_number: int
    name: str = ""
    overview: str = ""
    still_path: str | None = None
    runtime_minutes: int | None = None
    air_date: str | None = None
    vote_average: float | None = None
    tmdb_id: int | None = None
    tvdb_id: int | None = None


class SeriesResponse(BaseModel):
    id: str
    title: str
    overview: str = ""
    first_air_date: str | None = None
    last_air_date: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    status: str = ""
    vote_average: float | None = None
    genres: list[GenreResponse] = Field(default_factory=list)
    seasons: list[SeasonResponse] = Field(default_factory=list)
    tmdb_id: int | None = None
    tvdb_id: int | None = None


def _genre_to_response(g) -> GenreResponse:
    return GenreResponse(id=str(g.id), name=g.name, tmdb_id=g.tmdb_id, tvdb_id=g.tvdb_id)


def _season_to_response(s) -> SeasonResponse:
    return SeasonResponse(
        id=str(s.id),
        series_id=str(s.series_id),
        season_number=s.season_number,
        name=s.name,
        overview=s.overview,
        poster_path=s.poster_path,
        episode_count=s.episode_count,
        air_date=s.air_date.isoformat() if s.air_date else None,
        tmdb_id=s.tmdb_id,
        tvdb_id=s.tvdb_id,
    )


def _movie_to_response(m) -> MovieResponse:
    return MovieResponse(
        id=str(m.id),
        title=m.title,
        overview=m.overview,
        release_date=m.release_date.isoformat() if m.release_date else None,
        poster_path=m.poster_path,
        backdrop_path=m.backdrop_path,
        runtime_minutes=m.runtime_minutes,
        vote_average=m.vote_average,
        genres=[_genre_to_response(g) for g in m.genres],
        collection_id=str(m.collection_id) if m.collection_id else None,
        tmdb_id=m.tmdb_id,
        tvdb_id=m.tvdb_id,
    )


def _series_to_response(s) -> SeriesResponse:
    return SeriesResponse(
        id=str(s.id),
        title=s.title,
        overview=s.overview,
        first_air_date=s.first_air_date.isoformat() if s.first_air_date else None,
        last_air_date=s.last_air_date.isoformat() if s.last_air_date else None,
        poster_path=s.poster_path,
        backdrop_path=s.backdrop_path,
        status=s.status,
        vote_average=s.vote_average,
        genres=[_genre_to_response(g) for g in s.genres],
        seasons=[_season_to_response(se) for se in s.seasons],
        tmdb_id=s.tmdb_id,
        tvdb_id=s.tvdb_id,
    )


class CatalogController(Controller):
    path = "/catalog"
    tags = ["Catalog"]

    @get("/movies", summary="Browse movies in the catalog")
    async def list_movies(
        self,
        session: AsyncSession,
        catalog_service: CatalogService,
        limit: int = Parameter(default=20, ge=1, le=100),
        offset: int = Parameter(default=0, ge=0),
    ) -> list[MovieResponse]:
        movies = await catalog_service.list_movies(session, limit, offset)
        return [_movie_to_response(m) for m in movies]

    @get("/movies/search", summary="Search movies in the catalog")
    async def search_movies(
        self,
        session: AsyncSession,
        catalog_service: CatalogService,
        q: str = Parameter(min_length=1, max_length=255),
    ) -> list[MovieResponse]:
        movies = await catalog_service.search_movies(session, q)
        return [_movie_to_response(m) for m in movies]

    @get("/movies/{movie_id:str}", summary="Get movie details")
    async def get_movie(
        self,
        movie_id: str,
        session: AsyncSession,
        catalog_service: CatalogService,
    ) -> MovieResponse:
        movie = await catalog_service.get_movie(session, movie_id)
        if movie is None:
            raise HTTPException(status_code=404, detail="Movie not found")
        return _movie_to_response(movie)

    @get("/series", summary="Browse TV series in the catalog")
    async def list_series(
        self,
        session: AsyncSession,
        catalog_service: CatalogService,
        limit: int = Parameter(default=20, ge=1, le=100),
        offset: int = Parameter(default=0, ge=0),
    ) -> list[SeriesResponse]:
        series_list = await catalog_service.list_series(session, limit, offset)
        return [_series_to_response(s) for s in series_list]

    @get("/series/search", summary="Search TV series in the catalog")
    async def search_series(
        self,
        session: AsyncSession,
        catalog_service: CatalogService,
        q: str = Parameter(min_length=1, max_length=255),
    ) -> list[SeriesResponse]:
        series_list = await catalog_service.search_series(session, q)
        return [_series_to_response(s) for s in series_list]

    @get("/series/{series_id:str}", summary="Get TV series details")
    async def get_series(
        self,
        series_id: str,
        session: AsyncSession,
        catalog_service: CatalogService,
    ) -> SeriesResponse:
        series = await catalog_service.get_series(session, series_id)
        if series is None:
            raise HTTPException(status_code=404, detail="Series not found")
        return _series_to_response(series)

    @get("/series/{series_id:str}/seasons", summary="List seasons for a series")
    async def list_seasons(
        self,
        series_id: str,
        session: AsyncSession,
        catalog_service: CatalogService,
    ) -> list[SeasonResponse]:
        seasons = await catalog_service.get_seasons(session, series_id)
        return [_season_to_response(s) for s in seasons]

    @get("/seasons/{season_id:str}/episodes", summary="List episodes for a season")
    async def list_episodes(
        self,
        season_id: str,
        session: AsyncSession,
        catalog_service: CatalogService,
    ) -> list[EpisodeResponse]:
        episodes = await catalog_service.get_episodes(session, season_id)
        return [
            EpisodeResponse(
                id=str(e.id),
                series_id=str(e.series_id),
                season_id=str(e.season_id),
                episode_number=e.episode_number,
                name=e.name,
                overview=e.overview,
                still_path=e.still_path,
                runtime_minutes=e.runtime_minutes,
                air_date=e.air_date.isoformat() if e.air_date else None,
                vote_average=e.vote_average,
                tmdb_id=e.tmdb_id,
                tvdb_id=e.tvdb_id,
            )
            for e in episodes
        ]

    @get("/genres", summary="List all genres in the catalog")
    async def list_genres(
        self,
        session: AsyncSession,
        catalog_service: CatalogService,
    ) -> list[GenreResponse]:
        genres = await catalog_service.list_genres(session)
        return [_genre_to_response(g) for g in genres]

    @get("/collections", summary="List all collections in the catalog")
    async def list_collections(
        self,
        session: AsyncSession,
        catalog_service: CatalogService,
        limit: int = Parameter(default=20, ge=1, le=100),
        offset: int = Parameter(default=0, ge=0),
    ) -> list[CollectionResponse]:
        collections = await catalog_service.list_collections(session, limit, offset)
        return [
            CollectionResponse(
                id=str(c.id),
                name=c.name,
                description=c.description,
                poster_url=c.poster_url,
                backdrop_url=c.backdrop_url,
                tmdb_id=c.tmdb_id,
            )
            for c in collections
        ]

    @get("/collections/{collection_id:str}", summary="Get collection details")
    async def get_collection(
        self,
        collection_id: str,
        session: AsyncSession,
        catalog_service: CatalogService,
    ) -> CollectionResponse:
        collection = await catalog_service.get_collection(session, collection_id)
        if collection is None:
            raise HTTPException(status_code=404, detail="Collection not found")
        return CollectionResponse(
            id=str(collection.id),
            name=collection.name,
            description=collection.description,
            poster_url=collection.poster_url,
            backdrop_url=collection.backdrop_url,
            tmdb_id=collection.tmdb_id,
        )
