"""Discovery API endpoints.

Per ADR-0009, these endpoints expose provider-driven content discovery.
They query configured metadata providers in real time, aggregate results,
and return them to the client. They do NOT read from a local catalog
database — content appears because providers know about it.
"""

from __future__ import annotations

from litestar import Controller, get
from litestar.exceptions import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from kondooit.application.discovery_service import (
    DiscoverySection,
    DiscoveryService,
    DiscoveredGenre,
    DiscoveredMovie,
    DiscoveredSeries,
)


class MovieResult(BaseModel):
    title: str
    overview: str = ""
    release_date: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    vote_average: float | None = None
    provider_key: str = ""
    external_id: int = 0


class SeriesResult(BaseModel):
    title: str
    overview: str = ""
    first_air_date: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    vote_average: float | None = None
    provider_key: str = ""
    external_id: int = 0


class GenreResult(BaseModel):
    name: str
    external_id: int = 0
    content_type: str = ""
    provider_key: str = ""


class SectionResponse(BaseModel):
    title: str
    section_key: str = ""
    provider_key: str = ""
    movies: list[MovieResult] = Field(default_factory=list)
    series: list[SeriesResult] = Field(default_factory=list)


class MovieDetailResponse(BaseModel):
    external_id: int
    title: str
    overview: str = ""
    release_date: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    runtime_minutes: int | None = None
    vote_average: float | None = None
    genres: list[dict] = Field(default_factory=list)
    collection_external_id: int | None = None
    collection_name: str | None = None
    provider_key: str = ""


class SeriesDetailResponse(BaseModel):
    external_id: int
    title: str
    overview: str = ""
    first_air_date: str | None = None
    last_air_date: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    status: str = ""
    vote_average: float | None = None
    genres: list[dict] = Field(default_factory=list)
    seasons: list[dict] = Field(default_factory=list)
    provider_key: str = ""


class CapabilityResponse(BaseModel):
    key: str
    capabilities: list[str]


def _movie_to_response(m: DiscoveredMovie) -> MovieResult:
    return MovieResult(
        title=m.title,
        overview=m.overview,
        release_date=m.release_date,
        poster_path=m.poster_path,
        backdrop_path=m.backdrop_path,
        vote_average=m.vote_average,
        provider_key=m.provider_key,
        external_id=m.external_id,
    )


def _series_to_response(s: DiscoveredSeries) -> SeriesResult:
    return SeriesResult(
        title=s.title,
        overview=s.overview,
        first_air_date=s.first_air_date,
        poster_path=s.poster_path,
        backdrop_path=s.backdrop_path,
        vote_average=s.vote_average,
        provider_key=s.provider_key,
        external_id=s.external_id,
    )


def _section_to_response(s: DiscoverySection) -> SectionResponse:
    return SectionResponse(
        title=s.title,
        section_key=s.section_key,
        provider_key=s.provider_key,
        movies=[_movie_to_response(m) for m in s.movies],
        series=[_series_to_response(s2) for s2 in s.series],
    )


class DiscoveryController(Controller):
    path = "/discovery"
    tags = ["Discovery"]

    @get("/landing", summary="Get aggregated discovery sections for the landing page")
    async def get_landing(
        self,
        session: AsyncSession,
        discovery_service: DiscoveryService,
    ) -> list[SectionResponse]:
        sections = await discovery_service.get_landing_page(session)
        return [_section_to_response(s) for s in sections]

    @get("/search", summary="Search across all enabled providers")
    async def search(
        self,
        session: AsyncSession,
        discovery_service: DiscoveryService,
        q: str,
    ) -> list[MovieResult | SeriesResult]:
        results = await discovery_service.search(session, q)
        return [
            _movie_to_response(r) if isinstance(r, DiscoveredMovie) else _series_to_response(r)
            for r in results
        ]

    @get("/search/movies", summary="Search movies across all enabled providers")
    async def search_movies(
        self,
        session: AsyncSession,
        discovery_service: DiscoveryService,
        q: str,
    ) -> list[MovieResult]:
        results = await discovery_service.search_movies(session, q)
        return [_movie_to_response(m) for m in results]

    @get("/search/series", summary="Search TV series across all enabled providers")
    async def search_series(
        self,
        session: AsyncSession,
        discovery_service: DiscoveryService,
        q: str,
    ) -> list[SeriesResult]:
        results = await discovery_service.search_series(session, q)
        return [_series_to_response(s) for s in results]

    @get("/genres", summary="Get genres from enabled providers")
    async def get_genres(
        self,
        session: AsyncSession,
        discovery_service: DiscoveryService,
        content_type: str | None = None,
    ) -> list[GenreResult]:
        genres = await discovery_service.get_genres(session, content_type)
        return [
            GenreResult(
                name=g.name,
                external_id=g.external_id,
                content_type=g.content_type,
                provider_key=g.provider_key,
            )
            for g in genres
        ]

    @get("/discover", summary="Discover content filtered by genre")
    async def discover(
        self,
        session: AsyncSession,
        discovery_service: DiscoveryService,
        genre_ids: str | None = None,
        content_type: str = "all",
        page: int = 1,
    ) -> list[MovieResult | SeriesResult]:
        parsed_ids = [int(gid) for gid in genre_ids.split(",") if gid.strip()] if genre_ids else []
        results = await discovery_service.discover_by_genre(
            session, genre_ids=parsed_ids, content_type=content_type, page=page
        )
        return [
            _movie_to_response(r) if isinstance(r, DiscoveredMovie) else _series_to_response(r)
            for r in results
        ]

    @get("/movie/{provider_key:str}/{external_id:int}", summary="Get movie details from a provider")
    async def get_movie_details(
        self,
        provider_key: str,
        external_id: int,
        session: AsyncSession,
        discovery_service: DiscoveryService,
    ) -> MovieDetailResponse:
        evidence = await discovery_service.get_movie_details(session, provider_key, external_id)
        if evidence is None:
            raise HTTPException(status_code=404, detail="Movie not found or provider not enabled")
        return MovieDetailResponse(
            external_id=evidence.external_id,
            title=evidence.title,
            overview=evidence.overview,
            release_date=evidence.release_date.isoformat() if evidence.release_date else None,
            poster_path=evidence.poster_path,
            backdrop_path=evidence.backdrop_path,
            runtime_minutes=evidence.runtime_minutes,
            vote_average=evidence.vote_average,
            genres=[{"id": g.external_id, "name": g.name} for g in evidence.genres],
            collection_external_id=evidence.collection_external_id,
            collection_name=evidence.collection_name,
            provider_key=provider_key,
        )

    @get("/series/{provider_key:str}/{external_id:int}", summary="Get series details from a provider")
    async def get_series_details(
        self,
        provider_key: str,
        external_id: int,
        session: AsyncSession,
        discovery_service: DiscoveryService,
    ) -> SeriesDetailResponse:
        evidence = await discovery_service.get_series_details(session, provider_key, external_id)
        if evidence is None:
            raise HTTPException(status_code=404, detail="Series not found or provider not enabled")
        return SeriesDetailResponse(
            external_id=evidence.external_id,
            title=evidence.title,
            overview=evidence.overview,
            first_air_date=evidence.first_air_date.isoformat() if evidence.first_air_date else None,
            last_air_date=evidence.last_air_date.isoformat() if evidence.last_air_date else None,
            poster_path=evidence.poster_path,
            backdrop_path=evidence.backdrop_path,
            status=evidence.status,
            vote_average=evidence.vote_average,
            genres=[{"id": g.external_id, "name": g.name} for g in evidence.genres],
            seasons=[
                {
                    "external_id": s.external_id,
                    "season_number": s.season_number,
                    "name": s.name,
                    "overview": s.overview,
                    "poster_path": s.poster_path,
                    "episode_count": s.episode_count,
                    "air_date": s.air_date.isoformat() if s.air_date else None,
                    "episodes": [
                        {
                            "external_id": e.external_id,
                            "season_number": e.season_number,
                            "episode_number": e.episode_number,
                            "name": e.name,
                            "overview": e.overview,
                            "still_path": e.still_path,
                            "runtime_minutes": e.runtime_minutes,
                            "air_date": e.air_date.isoformat() if e.air_date else None,
                            "vote_average": e.vote_average,
                        }
                        for e in s.episodes
                    ],
                }
                for s in evidence.seasons
            ],
            provider_key=provider_key,
        )

    @get("/season/{provider_key:str}/{series_id:int}/{season_number:int}", summary="Get season details with episodes")
    async def get_season_details(
        self,
        provider_key: str,
        series_id: int,
        season_number: int,
        session: AsyncSession,
        discovery_service: DiscoveryService,
    ) -> dict:
        evidence = await discovery_service.get_season_details(session, provider_key, series_id, season_number)
        if evidence is None:
            raise HTTPException(status_code=404, detail="Season not found or provider not enabled")
        return {
            "external_id": evidence.external_id,
            "season_number": evidence.season_number,
            "name": evidence.name,
            "overview": evidence.overview,
            "poster_path": evidence.poster_path,
            "episode_count": evidence.episode_count,
            "air_date": evidence.air_date.isoformat() if evidence.air_date else None,
            "episodes": [
                {
                    "external_id": e.external_id,
                    "season_number": e.season_number,
                    "episode_number": e.episode_number,
                    "name": e.name,
                    "overview": e.overview,
                    "still_path": e.still_path,
                    "runtime_minutes": e.runtime_minutes,
                    "air_date": e.air_date.isoformat() if e.air_date else None,
                    "vote_average": e.vote_average,
                }
                for e in evidence.episodes
            ],
        }

    @get("/section/{section_key:str}", summary="Get a full discovery section with pagination")
    async def get_section(
        self,
        section_key: str,
        session: AsyncSession,
        discovery_service: DiscoveryService,
        page: int = 1,
    ) -> SectionResponse:
        section = await discovery_service.get_section(session, section_key, page=page)
        if section is None:
            raise HTTPException(status_code=404, detail="Section not found or no provider supports it")
        return _section_to_response(section)

    @get("/capabilities", summary="List discovery capabilities of all registered providers")
    async def get_capabilities(
        self,
        discovery_service: DiscoveryService,
    ) -> list[CapabilityResponse]:
        caps = discovery_service.list_provider_capabilities()
        return [
            CapabilityResponse(key=k, capabilities=sorted([c.value for c in v]))
            for k, v in caps.items()
        ]
