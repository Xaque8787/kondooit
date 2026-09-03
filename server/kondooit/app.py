"""Litestar application factory.

Creates and configures the Litestar app. The app factory is the composition
root where infrastructure implementations are wired to application-layer
ports.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from litestar import Litestar
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kondooit.api.auth import AuthController
from kondooit.api.catalog import CatalogController
from kondooit.api.discovery import DiscoveryController
from kondooit.api.health import health
from kondooit.api.providers import ProviderController
from kondooit.api.source_providers import SourceProviderController
from kondooit.api.streams import StreamController
from kondooit.api.user_state import UserStateController
from kondooit.application.auth_service import AuthService
from kondooit.application.catalog_service import CatalogService
from kondooit.application.discovery_service import DiscoveryService
from kondooit.application.metadata_service import MetadataService, ProviderRegistry
from kondooit.application.source_provider_service import (
    ImdbResolver,
    ScraperModuleManager,
    SourceProviderRegistry,
    SourceProviderService,
)
from kondooit.application.stream_store import StreamHandleStore
from kondooit.application.user_state_service import UserContentStateService
from kondooit.config import Settings, get_settings
from kondooit.infrastructure.database import create_engine, create_session_factory
from kondooit.infrastructure.providers.easynews import EasynewsProvider
from kondooit.infrastructure.providers.tmdb import TmdbProvider
from kondooit.infrastructure.providers.torbox import TorboxProvider
from kondooit.infrastructure.providers.tvdb import TvdbProvider
from kondooit.infrastructure.repositories import (
    SqlAlchemyCollectionRepository,
    SqlAlchemyEpisodeRepository,
    SqlAlchemyGenreRepository,
    SqlAlchemyMovieRepository,
    SqlAlchemyProviderConfigRepository,
    SqlAlchemySeasonRepository,
    SqlAlchemySeriesRepository,
    SqlAlchemyUserRepository,
)
from kondooit.infrastructure.scraper_loader import load_module
from kondooit.infrastructure.scraper_module_repo import ScraperModuleRepository
from kondooit.infrastructure.source_provider_repo import SqlAlchemySourceProviderConfigRepository
from kondooit.infrastructure.user_state_repo import SqlAlchemyUserContentStateRepository
from kondooit.infrastructure.security import BcryptPasswordHasher, JwtTokenService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> Litestar:
    """Create and configure the Litestar application."""
    settings = settings or get_settings()

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    # Auth
    user_repo = SqlAlchemyUserRepository()
    password_hasher = BcryptPasswordHasher()
    token_service = JwtTokenService(settings)
    auth_service = AuthService(user_repo, password_hasher, token_service)

    # Provider registry
    registry = ProviderRegistry()
    tmdb_provider = TmdbProvider()
    registry.register(tmdb_provider)
    registry.register(TvdbProvider())

    # Metadata service (provider orchestration only — no catalog persistence)
    config_repo = SqlAlchemyProviderConfigRepository()
    metadata_service = MetadataService(registry, config_repo)

    # Discovery service (provider-driven content discovery, per ADR-0009)
    discovery_service = DiscoveryService(registry, config_repo)

    # Catalog service (canonical catalog ownership)
    movie_repo = SqlAlchemyMovieRepository()
    series_repo = SqlAlchemySeriesRepository()
    season_repo = SqlAlchemySeasonRepository()
    episode_repo = SqlAlchemyEpisodeRepository()
    genre_repo = SqlAlchemyGenreRepository()
    collection_repo = SqlAlchemyCollectionRepository()
    catalog_service = CatalogService(
        movie_repo=movie_repo,
        series_repo=series_repo,
        season_repo=season_repo,
        episode_repo=episode_repo,
        genre_repo=genre_repo,
        collection_repo=collection_repo,
    )

    # Source provider registry
    source_registry = SourceProviderRegistry()
    source_registry.register(EasynewsProvider())
    source_registry.register(TorboxProvider())

    source_config_repo = SqlAlchemySourceProviderConfigRepository()

    # Scraper module manager — loaded from DB during lifespan startup
    scraper_manager = ScraperModuleManager()
    scraper_module_repo = ScraperModuleRepository()

    # IMDB resolver (uses TMDB external IDs endpoint)
    imdb_resolver = ImdbResolver(tmdb_provider, config_repo)

    stream_store = StreamHandleStore()

    source_provider_service = SourceProviderService(
        source_registry, source_config_repo,
        scraper_manager=scraper_manager,
        imdb_resolver=imdb_resolver,
    )

    # User content state service (favorites/following per ADR-0011)
    user_state_repo = SqlAlchemyUserContentStateRepository()
    user_state_service = UserContentStateService(user_state_repo)

    @asynccontextmanager
    async def lifespan(app: Litestar) -> AsyncIterator[None]:
        app.state.session_factory = session_factory
        app.state.auth_service = auth_service
        from kondooit.infrastructure.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Re-load previously-installed scraper modules from DB
        async with session_factory() as session:
            installed = await scraper_module_repo.list_modules(session)
            logger.info("Startup: found %d installed scraper modules in DB", len(installed))
            for mod_record in installed:
                loaded = load_module(mod_record.source_path)
                if loaded:
                    settings = await scraper_module_repo.list_settings(session, mod_record.module_id)
                    enabled_keys = {s.scraper_key for s in settings if s.enabled}
                    saved_configs = {s.scraper_key: s.config for s in settings if s.config}
                    scraper_manager.add_module(loaded, enabled_keys=enabled_keys, saved_configs=saved_configs)
                    logger.info(
                        "Loaded installed module '%s' from %s (%d scrapers, enabled_keys=%s)",
                        mod_record.name, mod_record.source_path,
                        len(loaded.scrapers), enabled_keys,
                    )
                else:
                    logger.warning("Failed to load installed module '%s' from %s", mod_record.module_id, mod_record.source_path)
            logger.info(
                "Startup complete: %d modules, %d enabled scrapers",
                len(scraper_manager.get_modules()),
                len(scraper_manager.get_enabled_scrapers()),
            )

        try:
            yield
        finally:
            await engine.dispose()

    async def provide_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def provide_auth_service() -> AsyncIterator[AuthService]:
        yield auth_service

    async def provide_metadata_service() -> AsyncIterator[MetadataService]:
        yield metadata_service

    async def provide_discovery_service() -> AsyncIterator[DiscoveryService]:
        yield discovery_service

    async def provide_catalog_service() -> AsyncIterator[CatalogService]:
        yield catalog_service

    async def provide_user_state_service() -> AsyncIterator[UserContentStateService]:
        yield user_state_service

    async def provide_source_provider_service() -> AsyncIterator[SourceProviderService]:
        yield source_provider_service

    async def provide_scraper_module_repo() -> AsyncIterator[ScraperModuleRepository]:
        yield scraper_module_repo

    async def provide_stream_store() -> AsyncIterator[StreamHandleStore]:
        yield stream_store

    return Litestar(
        route_handlers=[health, AuthController, ProviderController, SourceProviderController, StreamController, CatalogController, DiscoveryController, UserStateController],
        lifespan=[lifespan],
        dependencies={
            "session": provide_session,
            "auth_service": provide_auth_service,
            "metadata_service": provide_metadata_service,
            "discovery_service": provide_discovery_service,
            "catalog_service": provide_catalog_service,
            "user_state_service": provide_user_state_service,
            "source_provider_service": provide_source_provider_service,
            "scraper_module_repo": provide_scraper_module_repo,
            "stream_store": provide_stream_store,
        },
        debug=settings.debug,
    )


app = create_app()
