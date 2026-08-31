"""MediaFusion scraper — queries the public MediaFusion Stremio addon API.

MediaFusion is another major Stremio addon that aggregates torrent
sources. Uses the same Stremio stream protocol as Torrentio.

API: GET https://mediafusion.elfhosted.com/{config}/stream/{type}/{imdb_id}.json
"""

from __future__ import annotations

from kondooit_scraper_shared__stremio import (
    ScraperResult,
    encode_stremio_config,
    fetch_stremio_streams,
)

MEDIAFUSION_BASE = "https://mediafusion.elfhosted.com"
DEFAULT_CONFIG = {"stream_type": "torrent"}


class ScraperImpl:
    """MediaFusion public API scraper."""

    async def search_movie(
        self,
        imdb_id: str,
        title: str,
        year: int,
        config: dict | None = None,
    ) -> list[ScraperResult]:
        cfg = _build_config(config)
        url = f"{MEDIAFUSION_BASE}/{cfg}/stream/movie/{imdb_id}.json"
        return await fetch_stremio_streams(url, "mediafusion", timeout=20.0)

    async def search_episode(
        self,
        imdb_id: str,
        title: str,
        season: int,
        episode: int,
        config: dict | None = None,
    ) -> list[ScraperResult]:
        cfg = _build_config(config)
        url = f"{MEDIAFUSION_BASE}/{cfg}/stream/series/{imdb_id}:{season}:{episode}.json"
        return await fetch_stremio_streams(url, "mediafusion", timeout=20.0)


def _build_config(config: dict | None) -> str:
    merged = dict(DEFAULT_CONFIG)
    if config:
        merged.update(config)
    return encode_stremio_config(merged)
