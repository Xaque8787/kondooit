"""Shared Stremio addon stream parser.

All Stremio-protocol scrapers (Torrentio, MediaFusion, Comet, etc.)
return the same JSON shape: {"streams": [{infoHash, title, ...}, ...]}.
This module extracts hashes, sizes, and seeders from that format so
individual scrapers only need to build a URL and call fetch().
"""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

HASH_PATTERN = re.compile(r"[a-fA-F0-9]{40}")
SIZE_PATTERN = re.compile(r"([\d.]+)\s*(GB|MB|TB)", re.IGNORECASE)
SEEDERS_PATTERN = re.compile(r"👤\s*(\d+)")

STREMIO_HEADERS = {
    "User-Agent": "Stremio/1.0",
    "Accept": "application/json",
}

_SIZE_MULTIPLIERS = {"TB": 1099511627776, "GB": 1073741824, "MB": 1048576}


def parse_size_bytes(text: str) -> int | None:
    match = SIZE_PATTERN.search(text)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).upper()
    return int(value * _SIZE_MULTIPLIERS.get(unit, 1))


def parse_seeders(text: str) -> int | None:
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
    source: str = ""


def parse_stremio_streams(streams: list[dict], source_label: str) -> list[ScraperResult]:
    """Parse a Stremio streams array into ScraperResults."""
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
        size_bytes = parse_size_bytes(raw_title)
        seeders = parse_seeders(raw_title)
        display_title = raw_title.split("\n")[0].strip() if raw_title else info_hash

        results.append(ScraperResult(
            info_hash=info_hash.lower(),
            title=display_title,
            size_bytes=size_bytes,
            seeders=seeders,
            source=source_label,
        ))

    return results


async def fetch_stremio_streams(
    url: str,
    source_label: str,
    timeout: float = 15.0,
) -> list[ScraperResult]:
    """Fetch and parse a Stremio addon stream endpoint."""
    try:
        async with httpx.AsyncClient(timeout=timeout, headers=STREMIO_HEADERS) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code != 200:
                logger.warning("%s returned %d for %s", source_label, resp.status_code, url)
                return []
            data = resp.json()
    except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
        logger.warning("%s request failed: %s", source_label, e)
        return []

    streams = data.get("streams", [])
    results = parse_stremio_streams(streams, source_label)
    logger.info("%s: %d streams, %d valid hashes", source_label, len(streams), len(results))
    return results


def encode_stremio_config(config_dict: dict) -> str:
    """Encode a config dict as a base64 string for Stremio addon URLs."""
    return base64.b64encode(json.dumps(config_dict, separators=(",", ":")).encode()).decode()
