"""Catalog service and API tests.

Tests that:
1. CatalogService owns canonical catalog reads and evidence ingestion.
2. CatalogService does not reference TMDB, TVDB, or httpx.
3. MetadataService no longer has import/catalog persistence methods.
4. The catalog API endpoints work for browsing and searching.
5. Evidence ingestion maps provider evidence to canonical content.
"""

from __future__ import annotations

import inspect
import uuid
from datetime import date

import pytest
import pytest_asyncio
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from kondooit.application.catalog_service import CatalogService
from kondooit.application.metadata_service import MetadataService, ProviderRegistry
from kondooit.application.provider_ports import (
    ProviderMovieEvidence,
    ProviderSeriesEvidence,
    ProviderSeasonEvidence,
    ProviderGenreEvidence,
)
from kondooit.config import Settings
from kondooit.domain.content import Movie, Series
from kondooit.infrastructure.models import Base
from kondooit.infrastructure.repositories import (
    SqlAlchemyCollectionRepository,
    SqlAlchemyEpisodeRepository,
    SqlAlchemyGenreRepository,
    SqlAlchemyMovieRepository,
    SqlAlchemySeasonRepository,
    SqlAlchemySeriesRepository,
)


# --- Architectural boundary tests ---

def test_catalog_service_does_not_reference_tmdb_or_tvdb() -> None:
    """Verify CatalogService does not import or instantiate TMDB/TVDB providers."""
    from kondooit.application.catalog_service import CatalogService
    source = inspect.getsource(CatalogService)
    assert "TmdbProvider" not in source
    assert "TvdbProvider" not in source
    assert "import httpx" not in source
    assert "sqlalchemy" not in source
    assert "litestar" not in source
    # CatalogService uses provider_key strings ("tmdb", "tvdb") for evidence
    # mapping — that's ADR-0003 identity mapping, not architectural coupling.
    # The test verifies it doesn't import or instantiate provider classes.


def test_catalog_service_does_not_import_httpx() -> None:
    """Verify CatalogService does not import httpx or any infrastructure."""
    from kondooit.application.catalog_service import CatalogService
    source = inspect.getsource(CatalogService)
    assert "import httpx" not in source
    assert "sqlalchemy" not in source
    assert "litestar" not in source


def test_metadata_service_no_longer_has_import_methods() -> None:
    """Verify MetadataService no longer has import_movie or import_series methods."""
    source = inspect.getsource(MetadataService)
    assert "import_movie" not in source, "MetadataService should not have import_movie — that's CatalogService's job"
    assert "import_series" not in source, "MetadataService should not have import_series — that's CatalogService's job"
    assert "_resolve_genres" not in source, "MetadataService should not have _resolve_genres — that's CatalogService's job"
    assert "_resolve_collection" not in source


def test_metadata_service_does_not_reference_repositories() -> None:
    """Verify MetadataService no longer takes catalog repositories as deps."""
    source = inspect.getsource(MetadataService)
    assert "MovieRepository" not in source
    assert "SeriesRepository" not in source
    assert "SeasonRepository" not in source
    assert "EpisodeRepository" not in source
    assert "GenreRepository" not in source
    assert "CollectionRepository" not in source


def test_catalog_api_does_not_reference_providers() -> None:
    """Verify the catalog API module does not import or reference provider types."""
    from kondooit.api import catalog
    source = inspect.getsource(catalog)
    assert "MetadataService" not in source
    assert "ProviderMovieEvidence" not in source
    assert "ProviderSeriesEvidence" not in source
    assert "TmdbProvider" not in source
    assert "TvdbProvider" not in source
    # The catalog API responses include tmdb_id/tvdb_id as optional fields —
    # that's exposing external evidence IDs on canonical content, not coupling.
    # The test verifies it doesn't import provider classes or services.


# --- Catalog service unit tests ---

@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def catalog_service() -> CatalogService:
    return CatalogService(
        movie_repo=SqlAlchemyMovieRepository(),
        series_repo=SqlAlchemySeriesRepository(),
        season_repo=SqlAlchemySeasonRepository(),
        episode_repo=SqlAlchemyEpisodeRepository(),
        genre_repo=SqlAlchemyGenreRepository(),
        collection_repo=SqlAlchemyCollectionRepository(),
    )


@pytest.mark.asyncio
async def test_ingest_movie_evidence_creates_canonical_movie(
    session: AsyncSession, catalog_service: CatalogService
) -> None:
    evidence = ProviderMovieEvidence(
        external_id=550,
        title="Fight Club",
        overview="A ticking-time-bomb insomniac...",
        release_date=date(1999, 10, 15),
        poster_path="https://image.tmdb.org/t/p/w500/pB8BM7pSpX",
        vote_average=8.4,
        genres=[ProviderGenreEvidence(external_id=18, name="Drama")],
    )
    movie = await catalog_service.ingest_movie_evidence(session, "tmdb", evidence)
    assert movie is not None
    assert movie.title == "Fight Club"
    assert movie.tmdb_id == 550
    assert movie.tvdb_id is None
    assert len(movie.genres) == 1
    assert movie.genres[0].name == "Drama"


@pytest.mark.asyncio
async def test_ingest_movie_evidence_idempotent(
    session: AsyncSession, catalog_service: CatalogService
) -> None:
    evidence = ProviderMovieEvidence(
        external_id=550,
        title="Fight Club",
        overview="",
        genres=[],
    )
    movie1 = await catalog_service.ingest_movie_evidence(session, "tmdb", evidence)
    assert movie1 is not None

    movie2 = await catalog_service.ingest_movie_evidence(session, "tmdb", evidence)
    assert movie2 is not None
    assert movie1.id == movie2.id


@pytest.mark.asyncio
async def test_ingest_series_evidence_creates_canonical_series(
    session: AsyncSession, catalog_service: CatalogService
) -> None:
    evidence = ProviderSeriesEvidence(
        external_id=1396,
        title="Breaking Bad",
        overview="A high school chemistry teacher...",
        first_air_date=date(2008, 1, 20),
        vote_average=9.5,
        genres=[ProviderGenreEvidence(external_id=18, name="Drama")],
        seasons=[
            ProviderSeasonEvidence(
                external_id=3572,
                season_number=1,
                name="Season 1",
                overview="",
                episode_count=7,
                air_date=date(2008, 1, 20),
            ),
        ],
    )
    series = await catalog_service.ingest_series_evidence(session, "tmdb", evidence)
    assert series is not None
    assert series.title == "Breaking Bad"
    assert series.tmdb_id == 1396
    assert len(series.seasons) == 1
    assert series.seasons[0].season_number == 1


@pytest.mark.asyncio
async def test_list_movies_returns_canonical_content(
    session: AsyncSession, catalog_service: CatalogService
) -> None:
    evidence = ProviderMovieEvidence(external_id=550, title="Fight Club", overview="")
    await catalog_service.ingest_movie_evidence(session, "tmdb", evidence)

    movies = await catalog_service.list_movies(session)
    assert len(movies) == 1
    assert movies[0].title == "Fight Club"


@pytest.mark.asyncio
async def test_search_movies_finds_by_title(
    session: AsyncSession, catalog_service: CatalogService
) -> None:
    evidence = ProviderMovieEvidence(external_id=550, title="Fight Club", overview="")
    await catalog_service.ingest_movie_evidence(session, "tmdb", evidence)

    results = await catalog_service.search_movies(session, "fight")
    assert len(results) == 1
    assert results[0].title == "Fight Club"


@pytest.mark.asyncio
async def test_list_genres_returns_canonical_genres(
    session: AsyncSession, catalog_service: CatalogService
) -> None:
    evidence = ProviderMovieEvidence(
        external_id=550,
        title="Fight Club",
        overview="",
        genres=[ProviderGenreEvidence(external_id=18, name="Drama")],
    )
    await catalog_service.ingest_movie_evidence(session, "tmdb", evidence)

    genres = await catalog_service.list_genres(session)
    assert len(genres) == 1
    assert genres[0].name == "Drama"


# --- HTTP-level catalog API tests ---

@pytest.fixture
def client() -> TestClient:
    from kondooit.app import create_app
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    with TestClient(app=create_app(settings)) as c:
        yield c


def test_catalog_movies_empty(client: TestClient) -> None:
    resp = client.get("/catalog/movies")
    assert resp.status_code == 200
    assert resp.json() == []


def test_catalog_series_empty(client: TestClient) -> None:
    resp = client.get("/catalog/series")
    assert resp.status_code == 200
    assert resp.json() == []


def test_catalog_genres_empty(client: TestClient) -> None:
    resp = client.get("/catalog/genres")
    assert resp.status_code == 200
    assert resp.json() == []


def test_catalog_movie_not_found(client: TestClient) -> None:
    resp = client.get(f"/catalog/movies/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_catalog_series_not_found(client: TestClient) -> None:
    resp = client.get(f"/catalog/series/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_catalog_collections_empty(client: TestClient) -> None:
    resp = client.get("/catalog/collections")
    assert resp.status_code == 200
    assert resp.json() == []
