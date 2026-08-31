"""Torrentio scraper — queries the public Torrentio Stremio addon API.

Torrentio aggregates results from 15+ torrent indexers and returns
pre-indexed info_hashes. One GET request returns dozens of hashes.

API: GET https://torrentio.strem.fun/{config}/stream/{type}/{imdb_id}.json
"""

from __future__ import annotations

from kondooit_scraper_shared__stremio import (
    ScraperResult,
    fetch_stremio_streams,
)

TORRENTIO_BASE = "https://torrentio.strem.fun"
DEFAULT_CONFIG = "sort=seeders|qualityfilter=other"


class ScraperImpl:
    """Torrentio public API scraper."""

    async def search_movie(
        self,
        imdb_id: str,
        title: str,
        year: int,
        config: dict | None = None,
    ) -> list[ScraperResult]:
        cfg = _build_config(config)
        url = f"{TORRENTIO_BASE}/{cfg}/stream/movie/{imdb_id}.json"
        return await fetch_stremio_streams(url, "torrentio")

    async def search_episode(
        self,
        imdb_id: str,
        title: str,
        season: int,
        episode: int,
        config: dict | None = None,
    ) -> list[ScraperResult]:
        cfg = _build_config(config)
        url = f"{TORRENTIO_BASE}/{cfg}/stream/series/{imdb_id}:{season}:{episode}.json"
        return await fetch_stremio_streams(url, "torrentio")


def _build_config(config: dict | None) -> str:
    if not config:
        return DEFAULT_CONFIG
    sort = config.get("sort", "seeders")
    quality_filter = config.get("quality_filter", "other")
    return f"sort={sort}|qualityfilter={quality_filter}"
