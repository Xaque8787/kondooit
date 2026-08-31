"""Metadata provider API endpoints."""

from __future__ import annotations

from litestar import Controller, get, post, put, delete
from litestar.exceptions import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from kondooit.application.catalog_service import CatalogService
from kondooit.application.metadata_service import MetadataService
from kondooit.application.provider_ports import ProviderStatus


class ProviderInfoResponse(BaseModel):
    key: str
    name: str
    description: str
    supports: list[str]
    requires_api_key: bool


class ProviderConfigResponse(BaseModel):
    key: str
    api_key: str
    status: str
    priority: int = 100


class ProviderConfigRequest(BaseModel):
    api_key: str = Field(default="", max_length=1024)
    status: str = Field(default="disabled", pattern="^(enabled|disabled)$")
    priority: int = Field(default=100, ge=1, le=999)


class TestConnectionResponse(BaseModel):
    key: str
    connected: bool


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=255)
    page: int = Field(default=1, ge=1)


class MovieEvidenceResponse(BaseModel):
    external_id: int
    title: str
    overview: str = ""
    release_date: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    runtime_minutes: int | None = None
    vote_average: float | None = None


class SeriesEvidenceResponse(BaseModel):
    external_id: int
    title: str
    overview: str = ""
    first_air_date: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    vote_average: float | None = None


class ImportRequest(BaseModel):
    external_id: int


class ProviderController(Controller):
    path = "/providers"
    tags = ["Metadata Providers"]

    @get("/", summary="List all available metadata providers")
    async def list_providers(self, metadata_service: MetadataService) -> list[ProviderInfoResponse]:
        providers = metadata_service.list_providers()
        return [
            ProviderInfoResponse(
                key=p.key,
                name=p.name,
                description=p.description,
                supports=[s.value for s in p.supports],
                requires_api_key=p.requires_api_key,
            )
            for p in providers
        ]

    @get("/{key:str}", summary="Get a provider's configuration")
    async def get_provider_config(
        self,
        key: str,
        session: AsyncSession,
        metadata_service: MetadataService,
    ) -> ProviderConfigResponse:
        config = await metadata_service.get_provider_config(session, key)
        if config is None:
            return ProviderConfigResponse(key=key, api_key="", status="disabled", priority=100)
        return ProviderConfigResponse(key=config.key, api_key=config.api_key, status=config.status.value, priority=config.priority)

    @put("/{key:str}", summary="Configure a provider (API key, enable/disable)")
    async def save_provider_config(
        self,
        key: str,
        data: ProviderConfigRequest,
        session: AsyncSession,
        metadata_service: MetadataService,
    ) -> ProviderConfigResponse:
        status = ProviderStatus(data.status)
        config = await metadata_service.save_provider_config(session, key, data.api_key, status, data.priority)
        return ProviderConfigResponse(key=config.key, api_key=config.api_key, status=config.status.value, priority=config.priority)

    @delete("/{key:str}", summary="Delete a provider's configuration", status_code=200)
    async def delete_provider_config(
        self,
        key: str,
        session: AsyncSession,
        metadata_service: MetadataService,
    ) -> dict:
        deleted = await metadata_service.delete_provider_config(session, key)
        return {"deleted": deleted}

    @post("/{key:str}/test", summary="Test a provider's connection")
    async def test_provider(
        self,
        key: str,
        session: AsyncSession,
        metadata_service: MetadataService,
    ) -> TestConnectionResponse:
        connected = await metadata_service.test_provider(session, key)
        return TestConnectionResponse(key=key, connected=connected)

    @post("/{key:str}/search/movies", summary="Search for movies via a provider")
    async def search_movies(
        self,
        key: str,
        data: SearchRequest,
        session: AsyncSession,
        metadata_service: MetadataService,
    ) -> list[MovieEvidenceResponse]:
        results = await metadata_service.search_movies(session, key, data.query, data.page)
        return [
            MovieEvidenceResponse(
                external_id=r.external_id,
                title=r.title,
                overview=r.overview,
                release_date=r.release_date.isoformat() if r.release_date else None,
                poster_path=r.poster_path,
                backdrop_path=r.backdrop_path,
                runtime_minutes=r.runtime_minutes,
                vote_average=r.vote_average,
            )
            for r in results
        ]

    @post("/{key:str}/search/series", summary="Search for TV series via a provider")
    async def search_series(
        self,
        key: str,
        data: SearchRequest,
        session: AsyncSession,
        metadata_service: MetadataService,
    ) -> list[SeriesEvidenceResponse]:
        results = await metadata_service.search_series(session, key, data.query, data.page)
        return [
            SeriesEvidenceResponse(
                external_id=r.external_id,
                title=r.title,
                overview=r.overview,
                first_air_date=r.first_air_date.isoformat() if r.first_air_date else None,
                poster_path=r.poster_path,
                backdrop_path=r.backdrop_path,
                vote_average=r.vote_average,
            )
            for r in results
        ]

    @post("/{key:str}/trending/movies", summary="Get trending movies from a provider")
    async def trending_movies(
        self,
        key: str,
        session: AsyncSession,
        metadata_service: MetadataService,
    ) -> list[MovieEvidenceResponse]:
        results = await metadata_service.get_trending_movies(session, key)
        return [
            MovieEvidenceResponse(
                external_id=r.external_id,
                title=r.title,
                overview=r.overview,
                release_date=r.release_date.isoformat() if r.release_date else None,
                poster_path=r.poster_path,
                backdrop_path=r.backdrop_path,
                runtime_minutes=r.runtime_minutes,
                vote_average=r.vote_average,
            )
            for r in results
        ]

    @post("/{key:str}/trending/series", summary="Get trending TV series from a provider")
    async def trending_series(
        self,
        key: str,
        session: AsyncSession,
        metadata_service: MetadataService,
    ) -> list[SeriesEvidenceResponse]:
        results = await metadata_service.get_trending_series(session, key)
        return [
            SeriesEvidenceResponse(
                external_id=r.external_id,
                title=r.title,
                overview=r.overview,
                first_air_date=r.first_air_date.isoformat() if r.first_air_date else None,
                poster_path=r.poster_path,
                backdrop_path=r.backdrop_path,
                vote_average=r.vote_average,
            )
            for r in results
        ]

    @post("/{key:str}/import/movie", summary="Import a movie from a provider into the catalog")
    async def import_movie(
        self,
        key: str,
        data: ImportRequest,
        session: AsyncSession,
        metadata_service: MetadataService,
        catalog_service: CatalogService,
    ) -> dict:
        evidence = await metadata_service.get_movie_evidence(session, key, data.external_id)
        if evidence is None:
            raise HTTPException(status_code=404, detail="Movie not found or provider not enabled")
        movie = await catalog_service.ingest_movie_evidence(session, key, evidence)
        if movie is None:
            raise HTTPException(status_code=500, detail="Failed to ingest movie")
        return {"id": str(movie.id), "title": movie.title, "tmdb_id": movie.tmdb_id, "tvdb_id": movie.tvdb_id}

    @post("/{key:str}/import/series", summary="Import a TV series from a provider into the catalog")
    async def import_series(
        self,
        key: str,
        data: ImportRequest,
        session: AsyncSession,
        metadata_service: MetadataService,
        catalog_service: CatalogService,
    ) -> dict:
        evidence = await metadata_service.get_series_evidence(session, key, data.external_id)
        if evidence is None:
            raise HTTPException(status_code=404, detail="Series not found or provider not enabled")
        series = await catalog_service.ingest_series_evidence(session, key, evidence)
        if series is None:
            raise HTTPException(status_code=500, detail="Failed to ingest series")
        return {"id": str(series.id), "title": series.title, "tmdb_id": series.tmdb_id, "tvdb_id": series.tvdb_id}
