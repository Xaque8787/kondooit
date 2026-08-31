"""TVDB metadata provider implementation.

Calls the TVDB v4 API to retrieve TV series metadata.
Returns ProviderEvidence objects — the core maps these to canonical
content identity (ADR-0003).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from kondooit.application.provider_ports import (
    DiscoveryCapability,
    MetadataProvider,
    MetadataProviderType,
    ProviderConfig,
    ProviderEpisodeEvidence,
    ProviderGenreEvidence,
    ProviderInfo,
    ProviderMovieEvidence,
    ProviderSeasonEvidence,
    ProviderSeriesEvidence,
)

TVDB_BASE_URL = "https://api4.thetvdb.com/v4"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def _parse_genres(genre_data: list[dict[str, Any]] | list[str]) -> list[ProviderGenreEvidence]:
    if not genre_data:
        return []
    result = []
    for g in genre_data:
        if isinstance(g, dict):
            result.append(ProviderGenreEvidence(
                external_id=int(g.get("id", 0)),
                name=g.get("name", ""),
            ))
        elif isinstance(g, str):
            result.append(ProviderGenreEvidence(external_id=0, name=g))
    return result


def _extract_numeric_id(raw_id: Any) -> int | None:
    """Extract a numeric ID from TVDB's search results.

    TVDB v4 search returns IDs as strings like "series-12345" or "movie-67890".
    The numeric portion is the actual TVDB ID. For detail endpoints, the ID is
    already numeric.
    """
    if raw_id is None:
        return None
    if isinstance(raw_id, int):
        return raw_id
    s = str(raw_id)
    parts = s.split("-")
    for part in reversed(parts):
        if part.isdigit():
            return int(part)
    if s.isdigit():
        return int(s)
    return None


class TvdbProvider(MetadataProvider):
    """TVDB metadata provider — implements the MetadataProvider interface."""

    _token_cache: dict[str, str] = {}

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            key="tvdb",
            name="TheTVDB",
            description="Community-driven TV series and movie metadata database.",
            supports=[MetadataProviderType.SERIES, MetadataProviderType.MOVIE],
            requires_api_key=True,
            capabilities=sorted(self.supported_discoveries(), key=lambda c: c.value),
        )

    def supported_discoveries(self) -> set[DiscoveryCapability]:
        return {
            DiscoveryCapability.SEARCH_MOVIES,
            DiscoveryCapability.SEARCH_SERIES,
            DiscoveryCapability.GENRES_TV,
            DiscoveryCapability.MOVIE_DETAILS,
            DiscoveryCapability.SERIES_DETAILS,
            DiscoveryCapability.SEASON_DETAILS,
        }

    async def _get_auth_token(self, config: ProviderConfig) -> str | None:
        if not config.api_key:
            return None
        cached = self._token_cache.get(config.api_key)
        if cached:
            return cached
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{TVDB_BASE_URL}/login",
                    json={"apikey": config.api_key},
                    timeout=10,
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()
                token = data.get("data", {}).get("token")
                if token:
                    self._token_cache[config.api_key] = token
                return token
        except httpx.HTTPError:
            return None

    def _invalidate_token(self, config: ProviderConfig) -> None:
        self._token_cache.pop(config.api_key, None)

    async def test_connection(self, config: ProviderConfig) -> bool:
        self._invalidate_token(config)
        token = await self._get_auth_token(config)
        return token is not None

    async def _get(self, config: ProviderConfig, path: str, params: dict | None = None) -> dict:
        token = await self._get_auth_token(config)
        if not token:
            return {}
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{TVDB_BASE_URL}{path}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, params=params, timeout=15)
                if resp.status_code == 401:
                    self._invalidate_token(config)
                    token = await self._get_auth_token(config)
                    if not token:
                        return {}
                    headers = {"Authorization": f"Bearer {token}"}
                    resp = await client.get(url, headers=headers, params=params, timeout=15)
                if resp.status_code != 200:
                    return {}
                return resp.json()
        except httpx.HTTPError:
            return {}

    async def search_movies(self, config: ProviderConfig, query: str, page: int = 1) -> list[ProviderMovieEvidence]:
        data = await self._get(config, "/search", {"query": query, "type": "movie"})
        results = data.get("data", [])
        if not results:
            return []
        parsed = []
        for r in results:
            eid = _extract_numeric_id(r.get("tvdb_id") or r.get("id"))
            if eid is not None:
                parsed.append(self._parse_movie_search(r, eid))
        return parsed

    async def get_movie(self, config: ProviderConfig, external_id: int) -> ProviderMovieEvidence | None:
        data = await self._get(config, f"/movies/{external_id}/extended")
        record = data.get("data")
        if not record or "id" not in record:
            return None
        return self._parse_movie_detail(record)

    async def search_series(self, config: ProviderConfig, query: str, page: int = 1) -> list[ProviderSeriesEvidence]:
        data = await self._get(config, "/search", {"query": query, "type": "series"})
        results = data.get("data", [])
        if not results:
            return []
        parsed = []
        for r in results:
            eid = _extract_numeric_id(r.get("tvdb_id") or r.get("id"))
            if eid is not None:
                parsed.append(self._parse_series_search(r, eid))
        return parsed

    async def get_series(self, config: ProviderConfig, external_id: int) -> ProviderSeriesEvidence | None:
        data = await self._get(config, f"/series/{external_id}/extended")
        record = data.get("data")
        if not record or "id" not in record:
            return None
        return self._parse_series_detail(record)

    async def get_trending_movies(self, config: ProviderConfig, page: int = 1) -> list[ProviderMovieEvidence]:
        return []

    async def get_trending_series(self, config: ProviderConfig, page: int = 1) -> list[ProviderSeriesEvidence]:
        return []

    async def get_genres(self, config: ProviderConfig, content_type: MetadataProviderType) -> list[ProviderGenreEvidence]:
        data = await self._get(config, "/genres")
        genres = data.get("data", [])
        return [ProviderGenreEvidence(external_id=int(g["id"]), name=g.get("name", "")) for g in genres if "id" in g]

    async def get_season(
        self, config: ProviderConfig, series_external_id: int, season_number: int
    ) -> ProviderSeasonEvidence | None:
        data = await self._get(config, f"/series/{series_external_id}/episodes/default")
        all_episodes = data.get("data", {}).get("episodes", [])
        season_episodes = [e for e in all_episodes if e.get("seasonNumber") == season_number]
        if not season_episodes:
            return None
        episodes = [
            ProviderEpisodeEvidence(
                external_id=int(e["id"]),
                season_number=e.get("seasonNumber", season_number),
                episode_number=e.get("number", 0),
                name=e.get("name", ""),
                overview=e.get("overview", "") or "",
                still_path=e.get("image"),
                runtime_minutes=e.get("runtime"),
                air_date=_parse_date(e.get("aired")),
                vote_average=None,
            )
            for e in season_episodes
            if e.get("id")
        ]
        return ProviderSeasonEvidence(
            external_id=0,
            season_number=season_number,
            name=f"Season {season_number}",
            overview="",
            poster_path=None,
            episode_count=len(episodes),
            air_date=_parse_date(season_episodes[0].get("aired")) if season_episodes else None,
            episodes=episodes,
        )

    def _parse_movie_search(self, r: dict, eid: int) -> ProviderMovieEvidence:
        return ProviderMovieEvidence(
            external_id=eid,
            title=r.get("name", r.get("title", "")),
            overview=r.get("overview", "") or "",
            release_date=_parse_date(r.get("first_air_time") or r.get("firstAired") or r.get("aired")),
            poster_path=r.get("image_url") or r.get("image"),
            vote_average=float(r.get("score", 0)) if r.get("score") else None,
        )

    def _parse_movie_detail(self, r: dict) -> ProviderMovieEvidence:
        return ProviderMovieEvidence(
            external_id=int(r["id"]),
            title=r.get("name", ""),
            overview=r.get("overview", "") or "",
            release_date=_parse_date(r.get("releaseDate") or r.get("firstAired")),
            poster_path=r.get("image"),
            runtime_minutes=r.get("runtime"),
            vote_average=float(r.get("score", 0)) if r.get("score") else None,
            genres=_parse_genres(r.get("genres", [])),
        )

    def _parse_series_search(self, r: dict, eid: int) -> ProviderSeriesEvidence:
        return ProviderSeriesEvidence(
            external_id=eid,
            title=r.get("name", ""),
            overview=r.get("overview", "") or "",
            first_air_date=_parse_date(r.get("first_air_time") or r.get("firstAired") or r.get("first_air_date")),
            poster_path=r.get("image_url") or r.get("image"),
            vote_average=float(r.get("score", 0)) if r.get("score") else None,
        )

    def _parse_series_detail(self, r: dict) -> ProviderSeriesEvidence:
        seasons_data = r.get("seasons", [])
        seasons = [self._parse_season(s) for s in seasons_data if s.get("id")]
        return ProviderSeriesEvidence(
            external_id=int(r["id"]),
            title=r.get("name", ""),
            overview=r.get("overview", "") or r.get("overview", ""),
            first_air_date=_parse_date(r.get("firstAired")),
            last_air_date=_parse_date(r.get("lastAired")),
            poster_path=r.get("image"),
            status=r.get("status", {}).get("name", "") if isinstance(r.get("status"), dict) else str(r.get("status", "")),
            vote_average=float(r.get("score", 0)) if r.get("score") else None,
            genres=_parse_genres(r.get("genres", [])),
            seasons=seasons,
        )

    def _parse_season(self, s: dict) -> ProviderSeasonEvidence:
        return ProviderSeasonEvidence(
            external_id=int(s["id"]),
            season_number=s.get("number", 0),
            name=s.get("name", ""),
            overview=s.get("overview", "") or "",
            poster_path=s.get("image"),
            episode_count=s.get("episodeCount", 0) or 0,
            air_date=_parse_date(s.get("firstAired")),
        )
