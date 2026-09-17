"""Easynews source provider implementation.

Easynews is a Usenet provider with a direct search API. It discovers
AND serves content in one step — search results include direct download
URLs. No cache check or resolution step is needed.

Capabilities: DIRECT_SEARCH
Authentication: HTTP Basic Auth (username + password)
API: https://members.easynews.com/2.0/search/solr-search/advanced

URL construction verified against Umbrella (Kodi addon) source code:
  stream_url = downURL + quote('/{dlFarm}/{dlPort}/{hash}{ext}/{title}{ext}')
where downURL, dlFarm, dlPort are top-level response fields (not per-item).
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

from kondooit.application.source_provider_ports import (
    CredentialField,
    SourceCapability,
    SourceProvider,
    SourceProviderConfig,
    SourceProviderInfo,
    SourceResult,
    SourceSearchRequest,
)

EASYNEWS_SEARCH_URL = "https://members.easynews.com/2.0/search/solr-search/advanced"
VIDEO_EXTENSIONS = {"mkv", "mp4", "avi", "ts", "m2ts", "wmv", "webm", "m4v", "3gp", "mov", "divx", "xvid", "mpg", "mpeg", "flv"}

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
    (re.compile(r"xvid", re.IGNORECASE), "XviD"),
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


def _build_search_query(query: SourceSearchRequest) -> str:
    """Build the search string for Easynews from structured metadata."""
    parts = [query.title]
    if query.year:
        parts.append(str(query.year))
    if query.season is not None and query.episode is not None:
        parts.append(f"S{query.season:02d}E{query.episode:02d}")
    elif query.season is not None:
        parts.append(f"S{query.season:02d}")
    return " ".join(parts)


_SE_PATTERN = re.compile(
    r"[.\s_-]S(\d{1,2})\s?E(\d{1,3})"   # S01E03, S1E3, S01.E03
    r"|[.\s_-](\d{1,2})x(\d{1,3})",       # 1x03, 01x03
    re.IGNORECASE,
)

_SEASON_ONLY_PATTERN = re.compile(
    r"[.\s_-]S(\d{1,2})[.\s_-]"           # S01. or S01- without E
    r"|[.\s_-]Season\s*(\d{1,2})[.\s_-]",
    re.IGNORECASE,
)


def _extract_season_episode(filename: str) -> tuple[int | None, int | None]:
    """Extract season and episode numbers from a filename."""
    m = _SE_PATTERN.search(filename)
    if m:
        if m.group(1) is not None:
            return int(m.group(1)), int(m.group(2))
        return int(m.group(3)), int(m.group(4))
    sm = _SEASON_ONLY_PATTERN.search(filename)
    if sm:
        s = sm.group(1) or sm.group(2)
        return int(s), None
    return None, None


def _matches_episode_query(filename: str, query: SourceSearchRequest) -> bool:
    """Check if a filename matches the requested season/episode."""
    if query.season is None:
        return True
    file_s, file_e = _extract_season_episode(filename)
    if file_s is None:
        return False
    if file_s != query.season:
        return False
    if query.episode is not None:
        if file_e is None:
            return False
        if file_e != query.episode:
            return False
    return True


def build_easynews_download_url(
    down_url: str, dl_farm: str, dl_port: str,
    post_hash: str, ext: str, filename: str,
) -> str:
    """Build the upstream Easynews download URL from search response fields.

    Pattern (from Umbrella source):
      {downURL}/{dlFarm}/{dlPort}/{post_hash}{ext}/{filename}{ext}
    """
    ext_dot = f".{ext.lstrip('.')}" if ext else ""
    safe_name = quote(filename, safe="")
    return f"{down_url}/{dl_farm}/{dl_port}/{post_hash}{ext_dot}/{safe_name}{ext_dot}"


def _content_type_for_ext(ext: str) -> str:
    mapping = {
        "mkv": "video/x-matroska",
        "avi": "video/x-msvideo",
        "ts": "video/mp2t",
        "m2ts": "video/mp2t",
        "webm": "video/webm",
    }
    return mapping.get(ext, "video/mp4")


class EasynewsProvider(SourceProvider):

    def info(self) -> SourceProviderInfo:
        return SourceProviderInfo(
            key="easynews",
            name="Easynews",
            description="Usenet provider with direct search and download. Search results are immediately playable — no cache check needed.",
            capabilities=[SourceCapability.DIRECT_SEARCH],
            credential_fields=[
                CredentialField(
                    name="username",
                    label="Username",
                    field_type="text",
                    required=True,
                    placeholder="Your Easynews username",
                ),
                CredentialField(
                    name="password",
                    label="Password",
                    field_type="password",
                    required=True,
                    placeholder="Your Easynews password",
                ),
            ],
        )

    def supported_capabilities(self) -> set[SourceCapability]:
        return {SourceCapability.DIRECT_SEARCH}

    async def test_connection(self, config: SourceProviderConfig) -> bool:
        username = config.credentials.get("username", "")
        password = config.credentials.get("password", "")
        if not username or not password:
            return False
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    self._build_search_url("test"),
                    auth=(username, password),
                )
                return resp.status_code == 200
        except (httpx.HTTPError, httpx.TimeoutException):
            return False

    async def search(self, config: SourceProviderConfig, query: SourceSearchRequest) -> list[SourceResult]:
        username = config.credentials.get("username", "")
        password = config.credentials.get("password", "")
        if not username or not password:
            return []

        search_text = _build_search_query(query)
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    self._build_search_url(search_text),
                    auth=(username, password),
                )
                if resp.status_code != 200:
                    logger.warning("Easynews search returned status %d", resp.status_code)
                    return []
                data = resp.json()
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
            logger.error("Easynews search failed: %s", e)
            return []

        results = self._parse_results(data)

        if query.season is not None:
            filtered = [r for r in results if _matches_episode_query(r.filename, query)]
            logger.info(
                "Easynews search for %r: %d raw items -> %d parsed -> %d after S/E filter",
                search_text, len(data.get("data", [])), len(results), len(filtered),
            )
            return filtered
        logger.info("Easynews search for %r returned %d results (raw items: %d)",
                     search_text, len(results), len(data.get("data", [])))
        return results

    @staticmethod
    def _build_search_url(query: str) -> str:
        fex = ",".join(VIDEO_EXTENSIONS)
        q = quote(query, safe="")
        return (
            f"{EASYNEWS_SEARCH_URL}"
            f"?st=adv&sb=1&gps={q}"
            f"&fex={fex}&fty[]=VIDEO"
            f"&spamf=1&u=1&gx=1&pno=1&pby=100"
            f"&s1=relevance&s1d=-&s2=dsize&s2d=-&s3=dtime&s3d=-&sS=3"
        )

    @staticmethod
    def _parse_results(data: dict) -> list[SourceResult]:
        results: list[SourceResult] = []
        items = data.get("data", [])
        if not isinstance(items, list):
            return results

        down_url = data.get("downURL", "")
        dl_farm = data.get("dlFarm", "")
        dl_port = str(data.get("dlPort", ""))

        if not down_url or not dl_farm or not dl_port:
            logger.warning(
                "Easynews response missing top-level URL fields: downURL=%r dlFarm=%r dlPort=%r",
                down_url, dl_farm, dl_port,
            )
            return results

        for item in items:
            if not isinstance(item, dict):
                continue
            filename = item.get("10", item.get("fn", ""))
            if not filename:
                continue

            ext_field = item.get("11", item.get("extension", ""))
            ext = ext_field.lstrip(".").lower() if ext_field else ""
            if not ext:
                ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in VIDEO_EXTENSIONS:
                continue

            post_hash = item.get("0", item.get("hash", ""))
            if not post_hash:
                continue

            full_filename = f"{filename}.{ext}" if not filename.lower().endswith(f".{ext}") else filename

            raw_size = item.get("rawSize", item.get("size", 0))
            size_bytes = int(raw_size) if raw_size else 0

            duration_seconds = None
            duration_str = item.get("14", "")
            if duration_str:
                try:
                    parts = str(duration_str).replace("h", ":").replace("m", ":").replace("s", "").split(":")
                    parts = [p.strip() for p in parts if p.strip()]
                    if len(parts) == 3:
                        duration_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    elif len(parts) == 2:
                        duration_seconds = int(parts[0]) * 60 + int(parts[1])
                except (ValueError, IndexError):
                    pass
            if duration_str and (re.match(r"^\d+s", duration_str) or re.match(r"^[0-5]m", duration_str)):
                continue

            upstream_url = build_easynews_download_url(
                down_url=down_url, dl_farm=dl_farm, dl_port=dl_port,
                post_hash=post_hash, ext=ext, filename=filename,
            )

            results.append(SourceResult(
                provider_key="easynews",
                filename=full_filename,
                size_bytes=size_bytes,
                quality=_detect_quality(full_filename),
                codec=_detect_codec(full_filename),
                duration_seconds=duration_seconds,
                _upstream_url=upstream_url,
                _content_type=_content_type_for_ext(ext),
            ))

        return results
