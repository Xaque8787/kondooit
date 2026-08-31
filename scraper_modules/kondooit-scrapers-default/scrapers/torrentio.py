"""Torrentio scraper — queries the public Torrentio Stremio addon API.

Torrentio aggregates results from 15+ torrent indexers and returns
pre-indexed info_hashes. This is the highest-value, lowest-effort
scraper: one GET request returns dozens of hashes.

API: GET https://torrentio.strem.fun/{config}/stream/{type}/{imdb_id}.json
The config path segment is required (base64-encoded JSON filter).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

TORRENTIO_BASE = "https://torrentio.strem.fun"
TORRENTIO_DEFAULT_CONFIG = "sort=seeders|qualityfilter=other"
HASH_PATTERN = re.compile(r"[a-fA-F0-9]{40}")
SIZE_PATTERN = re.compile(r"([\d.]+)\s*(GB|MB|TB)", re.IGNORECASE)
SEEDERS_PATTERN = re.compile(r"👤\s*(\d+)")

HEADERS = {
    "User-Agent": "Stremio/1.0",
    "Accept": "application/json",
}


def _parse_size_bytes(text: str) -> int | None:
    match = SIZE_PATTERN.search(text)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).upper()
    multipliers = {"TB": 1099511627776, "GB": 1073741824, "MB": 1048576}
    return int(value * multipliers.get(unit, 1))


def _parse_seeders(text: str) -> int | None:
    match = SEEDERS_PATTERN.search(text)
    if match:
        return int(match.group(1))
    return None


@dataclass(frozen=True)
class ScraperResult:
    info_hash: str
    title: str
    size_bytes: int | None = None
    seeders: int | None = None
    source: str = "torrentio"


class ScraperImpl:
    """Torrentio public API scraper."""

    async def search_movie(
        self,
        imdb_id: str,
        title: str,
        year: int,
        config: dict | None = None,
    ) -> list[ScraperResult]:
        url = f"{TORRENTIO_BASE}/{TORRENTIO_DEFAULT_CONFIG}/stream/movie/{imdb_id}.json"
        return await self._fetch(url)

    async def search_episode(
        self,
        imdb_id: str,
        title: str,
        season: int,
        episode: int,
        config: dict | None = None,
    ) -> list[ScraperResult]:
        url = f"{TORRENTIO_BASE}/{TORRENTIO_DEFAULT_CONFIG}/stream/series/{imdb_id}:{season}:{episode}.json"
        return await self._fetch(url)

    async def _fetch(self, url: str) -> list[ScraperResult]:
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code != 200:
                    logger.warning("Torrentio returned %d for %s", resp.status_code, url)
                    return []
                data = resp.json()
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
            logger.warning("Torrentio request failed: %s", e)
            return []

        streams = data.get("streams", [])
        results: list[ScraperResult] = []

        for stream in streams:
            info_hash = stream.get("infoHash", "")
            if not info_hash or not HASH_PATTERN.match(info_hash):
                bfield = stream.get("behaviorHints", {})
                bh = bfield.get("bingeGroup", "") if isinstance(bfield, dict) else ""
                hash_match = HASH_PATTERN.search(bh)
                if hash_match:
                    info_hash = hash_match.group(0)
                else:
                    continue

            raw_title = stream.get("title", "") or stream.get("name", "")
            size_bytes = _parse_size_bytes(raw_title)
            seeders = _parse_seeders(raw_title)
            display_title = raw_title.split("\n")[0].strip() if raw_title else info_hash

            results.append(ScraperResult(
                info_hash=info_hash.lower(),
                title=display_title,
                size_bytes=size_bytes,
                seeders=seeders,
                source="torrentio",
            ))

        logger.info("Torrentio: %d streams, %d valid hashes", len(streams), len(results))
        return results
