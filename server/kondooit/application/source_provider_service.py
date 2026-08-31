"""Source provider application service.

Orchestrates source provider management: registration, config CRUD,
connection testing, and the full source discovery pipeline:
  1. Run scraper modules to discover info_hashes
  2. Fan out hashes to all CACHE_CHECK providers in parallel
  3. Run DIRECT_SEARCH providers in parallel
  4. Merge all results into a unified list
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

from kondooit.application.scraper_ports import Scraper, ScraperResult
from kondooit.application.source_provider_ports import (
    CacheCheckResult,
    SourceCapability,
    SourceProvider,
    SourceProviderConfig,
    SourceProviderInfo,
    SourceProviderStatus,
    SourceResult,
    SourceSearchRequest,
)

if TYPE_CHECKING:
    from kondooit.application.ports import AsyncSessionProtocol
    from kondooit.infrastructure.scraper_loader import LoadedModule, LoadedScraper

logger = logging.getLogger(__name__)

QUALITY_PATTERNS = [
    (re.compile(r"2160p|4k|uhd", re.IGNORECASE), "2160p"),
    (re.compile(r"1080p|1080i", re.IGNORECASE), "1080p"),
    (re.compile(r"720p", re.IGNORECASE), "720p"),
    (re.compile(r"480p|dvdrip|dvd", re.IGNORECASE), "480p"),
]

CODEC_PATTERNS = [
    (re.compile(r"x265|h\.?265|hevc", re.IGNORECASE), "HEVC"),
    (re.compile(r"x264|h\.?264|avc", re.IGNORECASE), "H.264"),
    (re.compile(r"av1", re.IGNORECASE), "AV1"),
]


def _detect_quality(filename: str) -> str:
    for pattern, label in QUALITY_PATTERNS:
        if pattern.search(filename):
            return label
    return ""


def _detect_codec(filename: str) -> str:
    for pattern, label in CODEC_PATTERNS:
        if pattern.search(filename):
            return label
    return ""


class SourceProviderRegistry:
    """In-memory registry of available source providers."""

    def __init__(self) -> None:
        self._providers: dict[str, SourceProvider] = {}

    def register(self, provider: SourceProvider) -> None:
        info = provider.info()
        self._providers[info.key] = provider

    def get(self, key: str) -> SourceProvider | None:
        return self._providers.get(key)

    def list_providers(self) -> list[SourceProvider]:
        return list(self._providers.values())


class ScraperModuleManager:
    """Manages loaded scraper modules with database persistence.

    Modules are installed explicitly by the admin (no auto-load).
    On startup, previously-installed modules are re-loaded from their
    stored paths. Toggle state is persisted per-scraper.
    """

    def __init__(self) -> None:
        self._modules: list[LoadedModule] = []
        self._enabled_scrapers: dict[str, LoadedScraper] = {}

    def add_module(self, module: "LoadedModule", enabled_keys: set[str] | None = None) -> None:
        """Add a loaded module. If enabled_keys provided and non-empty, use that for toggle state."""
        self._modules.append(module)
        for scraper in module.scrapers:
            if enabled_keys is not None and len(enabled_keys) > 0:
                if scraper.key in enabled_keys:
                    self._enabled_scrapers[scraper.key] = scraper
            elif scraper.default_enabled:
                self._enabled_scrapers[scraper.key] = scraper

    def remove_module(self, module_id: str) -> None:
        """Remove a module and all its scrapers from memory."""
        to_remove = [m for m in self._modules if m.manifest.module_id == module_id]
        for m in to_remove:
            for s in m.scrapers:
                self._enabled_scrapers.pop(s.key, None)
            self._modules.remove(m)

    def get_modules(self) -> list["LoadedModule"]:
        return list(self._modules)

    def get_enabled_scrapers(self) -> list["LoadedScraper"]:
        return list(self._enabled_scrapers.values())

    def set_scraper_enabled(self, key: str, enabled: bool) -> None:
        if enabled:
            for module in self._modules:
                for scraper in module.scrapers:
                    if scraper.key == key:
                        self._enabled_scrapers[key] = scraper
                        return
        else:
            self._enabled_scrapers.pop(key, None)

    def is_scraper_enabled(self, key: str) -> bool:
        return key in self._enabled_scrapers

    def get_module_by_id(self, module_id: str) -> "LoadedModule | None":
        for m in self._modules:
            if m.manifest.module_id == module_id:
                return m
        return None


class SourceProviderConfigRepository:
    """Abstract repository for source provider configuration."""

    async def get(self, session: "AsyncSessionProtocol", key: str) -> SourceProviderConfig | None:
        raise NotImplementedError

    async def get_all(self, session: "AsyncSessionProtocol") -> list[SourceProviderConfig]:
        raise NotImplementedError

    async def save(self, session: "AsyncSessionProtocol", config: SourceProviderConfig) -> SourceProviderConfig:
        raise NotImplementedError

    async def delete(self, session: "AsyncSessionProtocol", key: str) -> bool:
        raise NotImplementedError


class SourceProviderService:
    """Application service for source provider management and source discovery."""

    def __init__(
        self,
        registry: SourceProviderRegistry,
        config_repo: SourceProviderConfigRepository,
        scraper_manager: ScraperModuleManager | None = None,
        imdb_resolver: "ImdbResolver | None" = None,
    ) -> None:
        self._registry = registry
        self._config_repo = config_repo
        self._scraper_manager = scraper_manager or ScraperModuleManager()
        self._imdb_resolver = imdb_resolver

    @property
    def scraper_manager(self) -> ScraperModuleManager:
        return self._scraper_manager

    def list_providers(self) -> list[SourceProviderInfo]:
        return [p.info() for p in self._registry.list_providers()]

    async def get_config(self, session: "AsyncSessionProtocol", key: str) -> SourceProviderConfig | None:
        return await self._config_repo.get(session, key)

    async def get_all_configs(self, session: "AsyncSessionProtocol") -> list[SourceProviderConfig]:
        return await self._config_repo.get_all(session)

    async def save_config(self, session: "AsyncSessionProtocol", config: SourceProviderConfig) -> SourceProviderConfig:
        result = await self._config_repo.save(session, config)
        await session.commit()
        return result

    async def delete_config(self, session: "AsyncSessionProtocol", key: str) -> bool:
        result = await self._config_repo.delete(session, key)
        await session.commit()
        return result

    async def test_provider(self, session: "AsyncSessionProtocol", key: str) -> bool:
        provider = self._registry.get(key)
        if provider is None:
            return False
        config = await self._config_repo.get(session, key)
        if config is None:
            return False
        return await provider.test_connection(config)

    async def resolve_stream(
        self,
        session: "AsyncSessionProtocol",
        provider_key: str,
        info_hash: str,
        file_index: int | None = None,
    ) -> dict:
        """Resolve a hash to a playable stream URL via a debrid provider."""
        config = await self._config_repo.get(session, provider_key)
        if config is None or config.status != SourceProviderStatus.ENABLED:
            return {"success": False, "detail": f"Provider '{provider_key}' not configured or disabled"}
        provider = self._registry.get(provider_key)
        if provider is None or not hasattr(provider, "resolve"):
            return {"success": False, "detail": f"Provider '{provider_key}' does not support resolve"}
        return await provider.resolve(config, info_hash, file_index)

    async def add_torrent(
        self, session: "AsyncSessionProtocol", provider_key: str, info_hash: str
    ) -> dict:
        """Add an uncached torrent to the user's debrid account."""
        config = await self._config_repo.get(session, provider_key)
        if config is None or config.status != SourceProviderStatus.ENABLED:
            return {"success": False, "detail": f"Provider '{provider_key}' not configured or disabled"}
        provider = self._registry.get(provider_key)
        if provider is None or not hasattr(provider, "add_torrent"):
            return {"success": False, "detail": f"Provider '{provider_key}' does not support adding torrents"}
        return await provider.add_torrent(config, info_hash)

    async def search_sources(
        self, session: "AsyncSessionProtocol", query: SourceSearchRequest
    ) -> list[SourceResult]:
        """Full source discovery pipeline.

        1. Resolve IMDB ID if not provided (via TMDB external IDs API)
        2. Run all enabled scrapers concurrently to discover hashes
        3. Deduplicate hashes (same hash from multiple scrapers = one hash)
        4. Fan out hashes to all enabled CACHE_CHECK providers in parallel
        5. Run DIRECT_SEARCH providers in parallel with step 2-4
        6. Merge into unified result list sorted by quality then size
        """
        all_configs = await self._config_repo.get_all(session)
        enabled_configs = [
            c for c in all_configs
            if c.status == SourceProviderStatus.ENABLED
        ]
        logger.info(
            "Source search: title=%s tmdb_id=%s, enabled_source_configs=%d (keys: %s)",
            query.title, query.tmdb_id, len(enabled_configs),
            [c.key for c in enabled_configs],
        )

        resolved_query = await self._resolve_imdb_id(query, session, enabled_configs)
        logger.info("Resolved IMDB ID: %s", resolved_query.imdb_id)

        direct_task = self._run_direct_search(enabled_configs, resolved_query)

        enabled_scrapers = self._scraper_manager.get_enabled_scrapers()
        logger.info("Enabled scrapers: %d (keys: %s)", len(enabled_scrapers), [s.key for s in enabled_scrapers])

        if resolved_query.imdb_id:
            scraper_task = self._run_scrapers(resolved_query)
        else:
            logger.warning("No IMDB ID resolved — skipping scrapers")
            async def _empty_scrapers() -> list[ScraperResult]:
                return []
            scraper_task = _empty_scrapers()

        direct_results, scraper_results = await asyncio.gather(
            direct_task, scraper_task, return_exceptions=True
        )

        if isinstance(direct_results, BaseException):
            logger.error("Direct search failed: %s", direct_results)
            direct_results = []
        if isinstance(scraper_results, BaseException):
            logger.error("Scraper search failed: %s", scraper_results)
            scraper_results = []

        logger.info("Pipeline results: direct=%d, scraper_hashes=%d", len(direct_results), len(scraper_results))
        all_results: list[SourceResult] = list(direct_results)

        cached_hashes: set[str] = set()
        if scraper_results:
            cache_results = await self._run_cache_checks(
                enabled_configs, scraper_results
            )
            all_results.extend(cache_results)
            cached_hashes = {r.info_hash.lower() for r in cache_results if r.info_hash}

        for sr in scraper_results:
            if sr.info_hash.lower() in cached_hashes:
                continue
            all_results.append(SourceResult(
                provider_key=sr.source,
                filename=sr.title,
                size_bytes=sr.size_bytes or 0,
                quality=_detect_quality(sr.title),
                codec=_detect_codec(sr.title),
                info_hash=sr.info_hash,
                seeders=sr.seeders,
                source_type="uncached_torrent",
                scraper_source=sr.source,
            ))

        source_type_order = {"direct": 0, "cached_torrent": 1, "uncached_torrent": 2}
        quality_order = {"2160p": 0, "1080p": 1, "720p": 2, "480p": 3, "": 4}
        all_results.sort(
            key=lambda r: (
                source_type_order.get(r.source_type, 3),
                quality_order.get(r.quality, 4),
                -(r.seeders or 0),
                -(r.size_bytes or 0),
            )
        )

        return all_results

    async def _resolve_imdb_id(
        self,
        query: SourceSearchRequest,
        session: "AsyncSessionProtocol",
        configs: list[SourceProviderConfig],
    ) -> SourceSearchRequest:
        """Resolve IMDB ID from TMDB if not already present."""
        if query.imdb_id:
            return query

        if not query.tmdb_id or not self._imdb_resolver:
            return query

        imdb_id = await self._imdb_resolver.get_imdb_id(
            tmdb_id=query.tmdb_id,
            content_type=query.content_type,
            session=session,
        )

        if imdb_id:
            return SourceSearchRequest(
                title=query.title,
                year=query.year,
                season=query.season,
                episode=query.episode,
                imdb_id=imdb_id,
                tmdb_id=query.tmdb_id,
                content_type=query.content_type,
            )
        return query

    async def _run_direct_search(
        self, configs: list[SourceProviderConfig], query: SourceSearchRequest
    ) -> list[SourceResult]:
        """Run all enabled DIRECT_SEARCH providers concurrently."""
        tasks = []
        for config in configs:
            provider = self._registry.get(config.key)
            if provider is None:
                continue
            if SourceCapability.DIRECT_SEARCH not in provider.supported_capabilities():
                continue
            tasks.append(provider.search(config, query))

        if not tasks:
            return []

        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        results: list[SourceResult] = []
        for r in task_results:
            if isinstance(r, BaseException):
                logger.warning("Direct search provider failed: %s", r)
                continue
            results.extend(r)
        return results

    async def _run_scrapers(self, query: SourceSearchRequest) -> list[ScraperResult]:
        """Run all enabled scrapers concurrently, deduplicate by hash."""
        enabled = self._scraper_manager.get_enabled_scrapers()
        if not enabled:
            logger.warning("_run_scrapers: no enabled scrapers in manager")
            return []

        imdb_id = query.imdb_id or ""
        tasks = []

        for scraper in enabled:
            if query.content_type == "movie" and "movie" in scraper.content_types:
                logger.info("Dispatching scraper '%s' for movie imdb=%s", scraper.key, imdb_id)
                tasks.append(self._run_single_scraper_movie(
                    scraper.instance, imdb_id, query.title, query.year or 0
                ))
            elif query.content_type == "series" and "series" in scraper.content_types:
                if query.season is not None and query.episode is not None:
                    logger.info("Dispatching scraper '%s' for episode imdb=%s S%02dE%02d", scraper.key, imdb_id, query.season, query.episode)
                    tasks.append(self._run_single_scraper_episode(
                        scraper.instance, imdb_id, query.title,
                        query.season, query.episode,
                    ))

        if not tasks:
            logger.warning("_run_scrapers: no tasks dispatched (content_type=%s, scrapers=%s)", query.content_type, [(s.key, s.content_types) for s in enabled])
            return []

        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        seen_hashes: dict[str, ScraperResult] = {}

        for r in task_results:
            if isinstance(r, BaseException):
                logger.warning("Scraper failed: %s", r)
                continue
            for result in r:
                h = result.info_hash.lower()
                if h not in seen_hashes:
                    seen_hashes[h] = result

        logger.info("Scrapers returned %d unique hashes", len(seen_hashes))
        return list(seen_hashes.values())

    @staticmethod
    async def _run_single_scraper_movie(
        scraper: Scraper, imdb_id: str, title: str, year: int
    ) -> list[ScraperResult]:
        try:
            return await asyncio.wait_for(
                scraper.search_movie(imdb_id, title, year),
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            return []

    @staticmethod
    async def _run_single_scraper_episode(
        scraper: Scraper, imdb_id: str, title: str, season: int, episode: int
    ) -> list[ScraperResult]:
        try:
            return await asyncio.wait_for(
                scraper.search_episode(imdb_id, title, season, episode),
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            return []

    async def _run_cache_checks(
        self,
        configs: list[SourceProviderConfig],
        scraper_results: list[ScraperResult],
    ) -> list[SourceResult]:
        """Fan out discovered hashes to all CACHE_CHECK providers in parallel.

        Returns one SourceResult per (file x provider) — no deduplication
        across providers per the agreed architecture.
        """
        hashes = [r.info_hash for r in scraper_results]
        hash_to_scraper: dict[str, ScraperResult] = {
            r.info_hash.lower(): r for r in scraper_results
        }

        tasks: list[tuple[str, asyncio.Task]] = []
        for config in configs:
            provider = self._registry.get(config.key)
            if provider is None:
                continue
            if SourceCapability.CACHE_CHECK not in provider.supported_capabilities():
                continue
            task = asyncio.ensure_future(provider.cache_check(config, hashes))
            tasks.append((config.key, task))

        if not tasks:
            return []

        results: list[SourceResult] = []
        task_results = await asyncio.gather(
            *[t for _, t in tasks], return_exceptions=True
        )

        total_cached = 0
        for (provider_key, _), cache_results in zip(tasks, task_results):
            if isinstance(cache_results, BaseException):
                logger.warning("Cache check failed for %s: %s", provider_key, cache_results)
                continue
            total_cached += len(cache_results)
            for cr in cache_results:
                scraper_info = hash_to_scraper.get(cr.info_hash.lower())
                seeders = scraper_info.seeders if scraper_info else None
                scraper_source = scraper_info.source if scraper_info else None

                results.append(SourceResult(
                    provider_key=provider_key,
                    filename=cr.filename,
                    size_bytes=cr.size_bytes,
                    quality=_detect_quality(cr.filename),
                    codec=_detect_codec(cr.filename),
                    info_hash=cr.info_hash,
                    seeders=seeders,
                    source_type="cached_torrent",
                    scraper_source=scraper_source,
                ))

        if total_cached == 0 and len(hashes) >= 10:
            logger.warning(
                "0 cached out of %d hashes across %d providers — "
                "possible API response format change or auth issue",
                len(hashes), len(tasks),
            )

        return results


class ImdbResolver:
    """Resolves TMDB IDs to IMDB IDs using the metadata provider."""

    def __init__(self, tmdb_provider: "Any", config_repo: "Any") -> None:
        self._tmdb_provider = tmdb_provider
        self._config_repo = config_repo

    async def get_imdb_id(
        self, tmdb_id: int, content_type: str, session: "AsyncSessionProtocol"
    ) -> str | None:
        config = await self._config_repo.get(session, "tmdb")
        if config is None:
            return None
        if content_type == "movie":
            return await self._tmdb_provider.get_movie_imdb_id(config, tmdb_id)
        else:
            return await self._tmdb_provider.get_series_imdb_id(config, tmdb_id)
