"""Scraper module interface and types.

Defines the contract that scraper modules implement. Each scraper
discovers info_hashes from torrent sites/aggregators and returns
ScraperResult objects. The scraper module system is independent of
source providers (TorBox, Easynews) — scrapers find hashes, providers
resolve them.

Per ADR-0012, source resolvers (scrapers) are installable modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ScraperResult:
    """A single hash discovered by a scraper."""
    info_hash: str
    title: str
    size_bytes: int | None = None
    seeders: int | None = None
    source: str = ""


@runtime_checkable
class Scraper(Protocol):
    """Protocol that each scraper must implement."""

    async def search_movie(
        self,
        imdb_id: str,
        title: str,
        year: int,
        config: dict | None = None,
    ) -> list[ScraperResult]: ...

    async def search_episode(
        self,
        imdb_id: str,
        title: str,
        season: int,
        episode: int,
        config: dict | None = None,
    ) -> list[ScraperResult]: ...
