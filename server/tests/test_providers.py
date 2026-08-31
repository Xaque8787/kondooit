"""Metadata provider architecture tests.

Tests that:
1. TMDB and TVDB both implement the MetadataProvider interface.
2. The provider abstraction is metadata-only (no source/playback methods).
3. Provider evidence objects are pure dataclasses, not ORM models.
4. The MetadataService depends on ports, not on TMDB/TVDB directly.
5. Provider config persistence works through the repository pattern.
"""

from __future__ import annotations

import inspect
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from kondooit.application.metadata_service import MetadataService, ProviderRegistry
from kondooit.application.provider_ports import (
    MetadataProvider,
    MetadataProviderType,
    ProviderConfig,
    ProviderEpisodeEvidence,
    ProviderGenreEvidence,
    ProviderInfo,
    ProviderMovieEvidence,
    ProviderSeasonEvidence,
    ProviderSeriesEvidence,
    ProviderStatus,
)
from kondooit.infrastructure.models import Base
from kondooit.infrastructure.providers.tmdb import TmdbProvider
from kondooit.infrastructure.providers.tvdb import TvdbProvider
from kondooit.infrastructure.repositories import SqlAlchemyProviderConfigRepository


# --- Provider interface conformance ---

def test_tmdb_implements_metadata_provider() -> None:
    provider = TmdbProvider()
    assert isinstance(provider, MetadataProvider)


def test_tvdb_implements_metadata_provider() -> None:
    provider = TvdbProvider()
    assert isinstance(provider, MetadataProvider)


def test_tmdb_provider_info() -> None:
    provider = TmdbProvider()
    info = provider.info()
    assert info.key == "tmdb"
    assert info.requires_api_key is True
    assert MetadataProviderType.MOVIE in info.supports
    assert MetadataProviderType.SERIES in info.supports


def test_tvdb_provider_info() -> None:
    provider = TvdbProvider()
    info = provider.info()
    assert info.key == "tvdb"
    assert info.requires_api_key is True
    assert MetadataProviderType.SERIES in info.supports


# --- Provider abstraction is metadata-only ---

def test_metadata_provider_interface_has_only_metadata_methods() -> None:
    """Verify the MetadataProvider interface exposes only metadata-related methods.

    The architectural invariant is that MetadataProvider is scoped to metadata
    concerns only — not source discovery, acquisition, playback, or streaming.
    This test protects the capability boundary, not a specific method count.

    Note: 'now_playing' is a metadata discovery concept (movies in theaters),
    not a playback concept. The forbidden substrings are chosen to catch
    playback/streaming/acquisition methods, not discovery methods that
    happen to contain overlapping substrings.
    """
    method_names = [
        name for name in dir(MetadataProvider)
        if not name.startswith("_") and callable(getattr(MetadataProvider, name, None))
    ]
    forbidden_substrings = (
        "source", "acquire", "download", "stream",
        "transcode", "playback", "debrid", "usenet", "iptv",
        "indexer", "torrent", "epg", "channel",
    )
    for method_name in method_names:
        for forbidden in forbidden_substrings:
            assert forbidden not in method_name.lower(), (
                f"MetadataProvider has method '{method_name}' which contains '{forbidden}' — "
                f"the interface should be metadata-only"
            )


# --- Evidence objects are pure dataclasses ---

def test_provider_evidence_objects_are_dataclasses() -> None:
    from dataclasses import is_dataclass
    assert is_dataclass(ProviderMovieEvidence)
    assert is_dataclass(ProviderSeriesEvidence)
    assert is_dataclass(ProviderSeasonEvidence)
    assert is_dataclass(ProviderEpisodeEvidence)
    assert is_dataclass(ProviderGenreEvidence)
    assert is_dataclass(ProviderInfo)
    assert is_dataclass(ProviderConfig)


def test_provider_evidence_objects_are_not_orm_models() -> None:
    """Verify evidence objects do not inherit from SQLAlchemy DeclarativeBase."""
    from kondooit.infrastructure.models import Base as OrmBase
    evidence_classes = [
        ProviderMovieEvidence, ProviderSeriesEvidence, ProviderSeasonEvidence,
        ProviderEpisodeEvidence, ProviderGenreEvidence, ProviderInfo, ProviderConfig,
    ]
    for cls in evidence_classes:
        for base in cls.__mro__:
            assert base is not OrmBase, (
                f"{cls.__name__} inherits from SQLAlchemy DeclarativeBase — "
                f"evidence objects must not be ORM models"
            )


# --- MetadataService depends on ports, not infrastructure ---

def test_metadata_service_does_not_reference_tmdb_or_tvdb() -> None:
    """Verify the MetadataService source code does not reference TMDB or TVDB directly."""
    source = inspect.getsource(MetadataService)
    assert "TmdbProvider" not in source, "MetadataService must not reference TmdbProvider directly"
    assert "TvdbProvider" not in source, "MetadataService must not reference TvdbProvider directly"
    assert "import httpx" not in source, "MetadataService must not import httpx directly"


def test_provider_registry_does_not_reference_infrastructure() -> None:
    """Verify the ProviderRegistry does not import infrastructure providers."""
    source = inspect.getsource(ProviderRegistry)
    assert "TmdbProvider" not in source
    assert "TvdbProvider" not in source
    assert "httpx" not in source


# --- Provider config persistence ---

@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_provider_config_save_and_get(session: AsyncSession) -> None:
    repo = SqlAlchemyProviderConfigRepository()
    config = ProviderConfig(key="tmdb", api_key="test-api-key", status=ProviderStatus.ENABLED)
    saved = await repo.save(session, config)
    await session.commit()

    assert saved.key == "tmdb"
    assert saved.api_key == "test-api-key"
    assert saved.status == ProviderStatus.ENABLED

    found = await repo.get(session, "tmdb")
    assert found is not None
    assert found.api_key == "test-api-key"
    assert found.status == ProviderStatus.ENABLED


@pytest.mark.asyncio
async def test_provider_config_update_existing(session: AsyncSession) -> None:
    repo = SqlAlchemyProviderConfigRepository()
    config = ProviderConfig(key="tvdb", api_key="old-key", status=ProviderStatus.DISABLED)
    await repo.save(session, config)
    await session.commit()

    updated = ProviderConfig(key="tvdb", api_key="new-key", status=ProviderStatus.ENABLED)
    result = await repo.save(session, updated)
    await session.commit()

    assert result.api_key == "new-key"
    assert result.status == ProviderStatus.ENABLED


@pytest.mark.asyncio
async def test_provider_config_get_all(session: AsyncSession) -> None:
    repo = SqlAlchemyProviderConfigRepository()
    await repo.save(session, ProviderConfig(key="tmdb", api_key="key1", status=ProviderStatus.ENABLED))
    await repo.save(session, ProviderConfig(key="tvdb", api_key="key2", status=ProviderStatus.DISABLED))
    await session.commit()

    configs = await repo.get_all(session)
    assert len(configs) == 2
    keys = {c.key for c in configs}
    assert keys == {"tmdb", "tvdb"}


@pytest.mark.asyncio
async def test_provider_config_delete(session: AsyncSession) -> None:
    repo = SqlAlchemyProviderConfigRepository()
    await repo.save(session, ProviderConfig(key="tmdb", api_key="key1", status=ProviderStatus.ENABLED))
    await session.commit()

    deleted = await repo.delete(session, "tmdb")
    await session.commit()
    assert deleted is True

    found = await repo.get(session, "tmdb")
    assert found is None


# --- Registry ---

def test_provider_registry_register_and_list() -> None:
    registry = ProviderRegistry()
    registry.register(TmdbProvider())
    registry.register(TvdbProvider())

    providers = registry.list_providers()
    assert len(providers) == 2
    keys = {p.key for p in providers}
    assert keys == {"tmdb", "tvdb"}


def test_provider_registry_get_by_key() -> None:
    registry = ProviderRegistry()
    registry.register(TmdbProvider())
    registry.register(TvdbProvider())

    tmdb = registry.get("tmdb")
    assert tmdb is not None
    assert tmdb.info().key == "tmdb"

    tvdb = registry.get("tvdb")
    assert tvdb is not None
    assert tvdb.info().key == "tvdb"

    assert registry.get("nonexistent") is None
