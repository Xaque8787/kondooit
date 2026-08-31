"""TorBox source provider implementation.

TorBox is a debrid service that caches torrents on remote servers and
provides direct download links. It requires hashes from a source
resolver (hash aggregator) to find new content, then checks which
hashes are cached, then resolves cached hashes to playable URLs.

Capabilities: CLOUD_SEARCH, CACHE_CHECK, RESOLVE
Authentication: Bearer token (API key)
"""

from __future__ import annotations

import logging

import httpx

from kondooit.application.source_provider_ports import (
    CacheCheckResult,
    CredentialField,
    SourceCapability,
    SourceProvider,
    SourceProviderConfig,
    SourceProviderInfo,
)

logger = logging.getLogger(__name__)

TORBOX_API_BASE = "https://api.torbox.app/v1/api"

VIDEO_EXTS = {"mkv", "mp4", "avi", "ts", "m2ts", "wmv", "webm", "m4v", "mov"}


class TorboxProvider(SourceProvider):

    def info(self) -> SourceProviderInfo:
        return SourceProviderInfo(
            key="torbox",
            name="TorBox",
            description="Debrid service with cloud storage, torrent caching, and direct download links. Requires hashes from a source resolver for full cache-check functionality.",
            capabilities=[
                SourceCapability.CLOUD_SEARCH,
                SourceCapability.CACHE_CHECK,
                SourceCapability.RESOLVE,
            ],
            credential_fields=[
                CredentialField(
                    name="api_key",
                    label="API Key",
                    field_type="password",
                    required=True,
                    placeholder="Your TorBox API key",
                ),
            ],
        )

    def supported_capabilities(self) -> set[SourceCapability]:
        return {
            SourceCapability.CLOUD_SEARCH,
            SourceCapability.CACHE_CHECK,
            SourceCapability.RESOLVE,
        }

    async def test_connection(self, config: SourceProviderConfig) -> bool:
        api_key = config.credentials.get("api_key", "")
        if not api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{TORBOX_API_BASE}/user/me",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code != 200:
                    return False
                data = resp.json()
                return data.get("success", False)
        except (httpx.HTTPError, httpx.TimeoutException):
            return False

    async def cache_check(
        self, config: SourceProviderConfig, info_hashes: list[str]
    ) -> list[CacheCheckResult]:
        """Check which hashes are cached on TorBox (global network cache).

        TorBox API: GET /torrents/checkcached?hash={hash1,hash2,...}&format=list&list_files=true
        Response with format=list&list_files=true:
          {"success": true, "data": {"<hash>": [{"name": "file.mkv", "size": 1234}, ...], ...}}
        Hashes not in the response data are NOT cached.
        """
        api_key = config.credentials.get("api_key", "")
        if not api_key or not info_hashes:
            return []

        results: list[CacheCheckResult] = []
        batch_size = 100

        for i in range(0, len(info_hashes), batch_size):
            batch = info_hashes[i:i + batch_size]
            batch_results = await self._check_batch(api_key, batch)
            results.extend(batch_results)

        return results

    async def _check_batch(self, api_key: str, hashes: list[str]) -> list[CacheCheckResult]:
        hash_str = ",".join(hashes)
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    f"{TORBOX_API_BASE}/torrents/checkcached",
                    params={"hash": hash_str, "format": "list", "list_files": "true"},
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code != 200:
                    logger.warning("TorBox checkcached returned %d", resp.status_code)
                    return []
                data = resp.json()
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
            logger.warning("TorBox checkcached failed: %s", e)
            return []

        if not data.get("success", False):
            logger.warning("TorBox checkcached success=false: %s", data.get("detail", ""))
            return []

        results: list[CacheCheckResult] = []
        cache_data = data.get("data")

        if not cache_data:
            return []

        if isinstance(cache_data, dict):
            for info_hash, file_entries in cache_data.items():
                if not file_entries:
                    continue
                self._parse_hash_entries(info_hash.lower(), file_entries, results)
        elif isinstance(cache_data, list):
            for item in cache_data:
                if isinstance(item, dict) and "hash" in item:
                    info_hash = item["hash"]
                    files = item.get("files", [])
                    self._parse_hash_entries(info_hash.lower(), files, results)

        logger.info("TorBox cache check: %d/%d hashes cached (%d files)", 
                    len(set(r.info_hash for r in results)), len(hashes), len(results))
        return results

    @staticmethod
    def _parse_hash_entries(
        info_hash: str, entries: list | dict, results: list[CacheCheckResult]
    ) -> None:
        """Parse file entries for a cached hash.
        
        With format=list&list_files=true, entries is typically a list of file dicts:
          [{"name": "Movie.mkv", "size": 12345}, ...]
        
        It can also be a list of lists (multiple cached variants):
          [[{"name": "Movie.mkv", "size": 12345}], [...]]
        """
        if isinstance(entries, dict):
            # Single file entry
            TorboxProvider._add_file_result(info_hash, entries, 0, results)
            return

        if not isinstance(entries, list) or not entries:
            return

        # Check if it's a list of file dicts or a list of variants (list of lists)
        first = entries[0]

        if isinstance(first, dict):
            # Direct list of file objects: [{"name": ..., "size": ...}, ...]
            for idx, f in enumerate(entries):
                if isinstance(f, dict):
                    TorboxProvider._add_file_result(info_hash, f, idx, results)
        elif isinstance(first, list):
            # List of variants: [[file1, file2], [file1, file2]]
            # Take the first variant (they're usually the same content)
            for idx, f in enumerate(first):
                if isinstance(f, dict):
                    TorboxProvider._add_file_result(info_hash, f, idx, results)

    @staticmethod
    def _add_file_result(
        info_hash: str, file_dict: dict, idx: int, results: list[CacheCheckResult]
    ) -> None:
        name = file_dict.get("name", "") or file_dict.get("short_name", "")
        size = file_dict.get("size", 0)
        if not name:
            return
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in VIDEO_EXTS:
            return
        results.append(CacheCheckResult(
            info_hash=info_hash,
            filename=name,
            size_bytes=int(size) if size else 0,
            file_index=idx,
        ))

    async def add_torrent(self, config: SourceProviderConfig, magnet_or_hash: str) -> dict:
        """Add a torrent to the user's TorBox account by magnet link or info_hash.

        TorBox API: POST /torrents/createtorrent
        """
        api_key = config.credentials.get("api_key", "")
        if not api_key:
            return {"success": False, "detail": "No API key configured"}

        # If it looks like a bare hash, convert to magnet
        if len(magnet_or_hash) == 40 and all(c in "0123456789abcdef" for c in magnet_or_hash.lower()):
            magnet_or_hash = f"magnet:?xt=urn:btih:{magnet_or_hash}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{TORBOX_API_BASE}/torrents/createtorrent",
                    headers={"Authorization": f"Bearer {api_key}"},
                    data={"magnet": magnet_or_hash, "seed": "1", "allow_zip": "false"},
                )
                data = resp.json()
                if resp.status_code in (200, 201):
                    return {"success": True, "detail": data.get("detail", "Torrent added"), "data": data.get("data")}
                return {"success": False, "detail": data.get("detail", f"HTTP {resp.status_code}")}
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
            return {"success": False, "detail": str(e)}
