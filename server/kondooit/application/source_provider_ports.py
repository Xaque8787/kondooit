"""Source provider port definitions.

This is the application-layer interface for source providers. Source
providers are paid services with official APIs (TorBox, Easynews, IPTV).
They are bundled with the core — same pattern as metadata providers.

Per ADR-0012 (revised), the module system applies only to source
resolvers (hash aggregators), not to these bundled providers.

Per ADR-0010, providers declare which capabilities they support via
supported_capabilities(). The orchestration layer only calls methods
corresponding to declared capabilities.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class SourceProviderStatus(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class SourceCapability(str, Enum):
    """Operations a source provider may support.

    Per ADR-0010, providers declare which of these they support.
    The orchestration layer only calls capabilities a provider declares.
    """
    DIRECT_SEARCH = "direct_search"
    CLOUD_SEARCH = "cloud_search"
    CACHE_CHECK = "cache_check"
    RESOLVE = "resolve"
    CHANNEL_LIST = "channel_list"


@dataclass(frozen=True)
class SourceProviderInfo:
    """Static information about a source provider."""
    key: str
    name: str
    description: str
    capabilities: list[SourceCapability]
    credential_fields: list[CredentialField]


@dataclass(frozen=True)
class CredentialField:
    """Describes a credential field a source provider requires."""
    name: str
    label: str
    field_type: str = "text"  # text, password, url
    required: bool = True
    placeholder: str = ""


@dataclass(frozen=True)
class SourceProviderConfig:
    """Configuration for a source provider instance."""
    key: str
    credentials: dict[str, str] = field(default_factory=dict)
    status: SourceProviderStatus = SourceProviderStatus.DISABLED
    priority: int = 100


@dataclass(frozen=True)
class SourceSearchRequest:
    """What to search for. Constructed from metadata context."""
    title: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    imdb_id: str | None = None
    tmdb_id: int | None = None
    content_type: str = "movie"  # "movie" or "series"


@dataclass(frozen=True)
class SourceResult:
    """A unified source result from any provider type.

    Used for both DIRECT_SEARCH results (Easynews) and CACHE_CHECK results
    (TorBox). The UI displays these uniformly with provider badges.
    """
    provider_key: str
    filename: str
    size_bytes: int
    quality: str = ""
    codec: str = ""
    duration_seconds: int | None = None
    # Torrent-specific fields (populated by CACHE_CHECK results)
    info_hash: str | None = None
    seeders: int | None = None
    source_type: str = "direct"  # "direct", "cached_torrent", "in_library", "scraper_direct", "uncached_torrent"
    scraper_source: str | None = None  # which scraper discovered this hash
    stream_url: str | None = None
    stream_id: str | None = None
    is_season_pack: bool = False
    file_count: int = 0
    playback_compatibility: str = "unknown"  # "direct_play", "remux", "transcode", "incompatible", "unknown"
    compatibility_reason: str = ""
    # Internal: upstream details for handle creation (not serialized to API)
    _upstream_url: str | None = None
    _upstream_auth: tuple[str, str] | None = None
    _content_type: str | None = None


class SourceProvider(ABC):
    """Abstract interface for source providers."""

    @abstractmethod
    def info(self) -> SourceProviderInfo:
        """Return static information about this provider."""
        ...

    @abstractmethod
    def supported_capabilities(self) -> set[SourceCapability]:
        """Return the set of source capabilities this provider supports."""
        ...

    @abstractmethod
    async def test_connection(self, config: SourceProviderConfig) -> bool:
        """Test whether the provider is reachable with the given credentials."""
        ...

    async def search(self, config: SourceProviderConfig, query: SourceSearchRequest) -> list[SourceResult]:
        """Search for sources matching the query (DIRECT_SEARCH providers)."""
        return []

    async def cache_check(
        self, config: SourceProviderConfig, info_hashes: list[str]
    ) -> list[CacheCheckResult]:
        """Check which hashes are cached on this service (CACHE_CHECK providers)."""
        return []


@dataclass(frozen=True)
class CacheCheckResult:
    """A single file available from a cached torrent on a debrid service."""
    info_hash: str
    filename: str
    size_bytes: int
    file_index: int | None = None


@dataclass(frozen=True)
class CacheCheckGroup:
    """All cached files for a single info_hash, grouped."""
    info_hash: str
    files: list[CacheCheckResult]
