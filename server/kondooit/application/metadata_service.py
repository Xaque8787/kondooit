"""Provider registry and metadata application service.

The registry maps provider keys to MetadataProvider instances. The
MetadataService orchestrates provider calls and manages provider configs.
It returns provider evidence — it does NOT own canonical catalog content.

Canonical catalog ownership lives in CatalogService, which receives
evidence and maps it to canonical domain entities (ADR-0003).
"""

from __future__ import annotations

from kondooit.application.provider_ports import (
    MetadataProvider,
    ProviderConfig,
    ProviderInfo,
    ProviderMovieEvidence,
    ProviderSeriesEvidence,
    ProviderStatus,
)
from kondooit.application.ports import ProviderConfigRepository


class ProviderRegistry:
    """Registry of available metadata providers, keyed by provider key."""

    def __init__(self) -> None:
        self._providers: dict[str, MetadataProvider] = {}

    def register(self, provider: MetadataProvider) -> None:
        key = provider.info().key
        self._providers[key] = provider

    def get(self, key: str) -> MetadataProvider | None:
        return self._providers.get(key)

    def list_providers(self) -> list[ProviderInfo]:
        return [p.info() for p in self._providers.values()]


class MetadataService:
    """Application service for metadata provider operations.

    This service talks to providers and returns evidence. It does not
    persist canonical content — that is CatalogService's responsibility.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        config_repo: ProviderConfigRepository,
    ) -> None:
        self._registry = registry
        self._config_repo = config_repo

    def list_providers(self) -> list[ProviderInfo]:
        """Return info for all registered providers."""
        return self._registry.list_providers()

    async def get_provider_configs(self, session) -> list[ProviderConfig]:
        """Return all stored provider configs."""
        return await self._config_repo.get_all(session)

    async def get_provider_config(self, session, key: str) -> ProviderConfig | None:
        """Return a single provider config."""
        return await self._config_repo.get(session, key)

    async def save_provider_config(
        self, session, key: str, api_key: str, status: ProviderStatus, priority: int = 100
    ) -> ProviderConfig:
        """Save or update a provider's configuration."""
        config = ProviderConfig(key=key, api_key=api_key, status=status, priority=priority)
        saved = await self._config_repo.save(session, config)
        await session.commit()
        return saved

    async def delete_provider_config(self, session, key: str) -> bool:
        """Delete a provider's configuration."""
        deleted = await self._config_repo.delete(session, key)
        await session.commit()
        return deleted

    async def test_provider(self, session, key: str) -> bool:
        """Test a provider's connection with its stored config."""
        config = await self._config_repo.get(session, key)
        if config is None:
            return False
        provider = self._registry.get(key)
        if provider is None:
            return False
        return await provider.test_connection(config)

    async def search_movies(
        self, session, key: str, query: str, page: int = 1
    ) -> list[ProviderMovieEvidence]:
        """Search for movies via a provider. Returns raw evidence."""
        config = await self._get_enabled_config(session, key)
        if config is None:
            return []
        provider = self._registry.get(key)
        if provider is None:
            return []
        return await provider.search_movies(config, query, page)

    async def search_series(
        self, session, key: str, query: str, page: int = 1
    ) -> list[ProviderSeriesEvidence]:
        """Search for TV series via a provider. Returns raw evidence."""
        config = await self._get_enabled_config(session, key)
        if config is None:
            return []
        provider = self._registry.get(key)
        if provider is None:
            return []
        return await provider.search_series(config, query, page)

    async def get_trending_movies(
        self, session, key: str, page: int = 1
    ) -> list[ProviderMovieEvidence]:
        """Get trending movies from a provider. Returns raw evidence."""
        config = await self._get_enabled_config(session, key)
        if config is None:
            return []
        provider = self._registry.get(key)
        if provider is None:
            return []
        return await provider.get_trending_movies(config, page)

    async def get_trending_series(
        self, session, key: str, page: int = 1
    ) -> list[ProviderSeriesEvidence]:
        """Get trending TV series from a provider. Returns raw evidence."""
        config = await self._get_enabled_config(session, key)
        if config is None:
            return []
        provider = self._registry.get(key)
        if provider is None:
            return []
        return await provider.get_trending_series(config, page)

    async def get_movie_evidence(
        self, session, key: str, external_id: int
    ) -> ProviderMovieEvidence | None:
        """Fetch movie evidence from a provider (does not persist)."""
        config = await self._get_enabled_config(session, key)
        if config is None:
            return None
        provider = self._registry.get(key)
        if provider is None:
            return None
        return await provider.get_movie(config, external_id)

    async def get_series_evidence(
        self, session, key: str, external_id: int
    ) -> ProviderSeriesEvidence | None:
        """Fetch series evidence from a provider (does not persist)."""
        config = await self._get_enabled_config(session, key)
        if config is None:
            return None
        provider = self._registry.get(key)
        if provider is None:
            return None
        return await provider.get_series(config, external_id)

    async def _get_enabled_config(self, session, key: str) -> ProviderConfig | None:
        config = await self._config_repo.get(session, key)
        if config is None or config.status != ProviderStatus.ENABLED:
            return None
        return config
