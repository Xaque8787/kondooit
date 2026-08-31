"""TMDB (The Movie Database) metadata provider implementation.

Calls the TMDB v3 API to retrieve movie and TV series metadata.
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

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"


def _build_image_url(path: str | None, size: str = "original") -> str | None:
    if not path:
        return None
    return f"{TMDB_IMAGE_BASE_URL}/{size}{path}"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_genres(genre_data: list[dict[str, Any]]) -> list[ProviderGenreEvidence]:
    return [
        ProviderGenreEvidence(external_id=g["id"], name=g["name"])
        for g in genre_data
        if "id" in g and "name" in g
    ]


class TmdbProvider(MetadataProvider):
    """TMDB metadata provider — implements the MetadataProvider interface."""

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            key="tmdb",
            name="The Movie Database (TMDB)",
            description="Community-driven movie and TV metadata database.",
            supports=[MetadataProviderType.MOVIE, MetadataProviderType.SERIES],
            requires_api_key=True,
            capabilities=sorted(self.supported_discoveries(), key=lambda c: c.value),
        )

    def supported_discoveries(self) -> set[DiscoveryCapability]:
        return {
            DiscoveryCapability.SEARCH_MOVIES,
            DiscoveryCapability.SEARCH_SERIES,
            DiscoveryCapability.TRENDING_MOVIES,
            DiscoveryCapability.TRENDING_SERIES,
            DiscoveryCapability.NOW_PLAYING_MOVIES,
            DiscoveryCapability.UPCOMING_MOVIES,
            DiscoveryCapability.POPULAR_MOVIES,
            DiscoveryCapability.POPULAR_SERIES,
            DiscoveryCapability.DISCOVER_MOVIES,
            DiscoveryCapability.DISCOVER_SERIES,
            DiscoveryCapability.GENRES_MOVIE,
            DiscoveryCapability.GENRES_TV,
            DiscoveryCapability.MOVIE_DETAILS,
            DiscoveryCapability.SERIES_DETAILS,
            DiscoveryCapability.SEASON_DETAILS,
        }

    def _headers(self, config: ProviderConfig) -> dict[str, str]:
        return {"Authorization": f"Bearer {config.api_key}"}

    async def test_connection(self, config: ProviderConfig) -> bool:
        if not config.api_key:
            return False
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{TMDB_BASE_URL}/authentication",
                    headers=self._headers(config),
                    timeout=10,
                )
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def search_movies(self, config: ProviderConfig, query: str, page: int = 1) -> list[ProviderMovieEvidence]:
        params = {"query": query, "page": page}
        data = await self._get(config, "/search/movie", params)
        results = data.get("results", [])
        return [self._parse_movie_search(r) for r in results if r.get("id")]

    async def get_movie(self, config: ProviderConfig, external_id: int) -> ProviderMovieEvidence | None:
        data = await self._get(config, f"/movie/{external_id}", {"append_to_response": "genres"})
        if not data or "id" not in data:
            return None
        return self._parse_movie_detail(data)

    async def search_series(self, config: ProviderConfig, query: str, page: int = 1) -> list[ProviderSeriesEvidence]:
        params = {"query": query, "page": page}
        data = await self._get(config, "/search/tv", params)
        results = data.get("results", [])
        return [self._parse_series_search(r) for r in results if r.get("id")]

    async def get_series(self, config: ProviderConfig, external_id: int) -> ProviderSeriesEvidence | None:
        data = await self._get(config, f"/tv/{external_id}", {"append_to_response": "genres,seasons"})
        if not data or "id" not in data:
            return None
        return self._parse_series_detail(data)

    async def get_trending_movies(self, config: ProviderConfig, page: int = 1) -> list[ProviderMovieEvidence]:
        data = await self._get(config, "/trending/movie/week", {"page": page})
        results = data.get("results", [])
        return [self._parse_movie_search(r) for r in results if r.get("id")]

    async def get_trending_series(self, config: ProviderConfig, page: int = 1) -> list[ProviderSeriesEvidence]:
        data = await self._get(config, "/trending/tv/week", {"page": page})
        results = data.get("results", [])
        return [self._parse_series_search(r) for r in results if r.get("id")]

    async def get_now_playing_movies(self, config: ProviderConfig, page: int = 1) -> list[ProviderMovieEvidence]:
        data = await self._get(config, "/movie/now_playing", {"page": page})
        results = data.get("results", [])
        return [self._parse_movie_search(r) for r in results if r.get("id")]

    async def get_upcoming_movies(self, config: ProviderConfig, page: int = 1) -> list[ProviderMovieEvidence]:
        data = await self._get(config, "/movie/upcoming", {"page": page})
        results = data.get("results", [])
        return [self._parse_movie_search(r) for r in results if r.get("id")]

    async def get_popular_movies(self, config: ProviderConfig, page: int = 1) -> list[ProviderMovieEvidence]:
        data = await self._get(config, "/movie/popular", {"page": page})
        results = data.get("results", [])
        return [self._parse_movie_search(r) for r in results if r.get("id")]

    async def get_popular_series(self, config: ProviderConfig, page: int = 1) -> list[ProviderSeriesEvidence]:
        data = await self._get(config, "/tv/popular", {"page": page})
        results = data.get("results", [])
        return [self._parse_series_search(r) for r in results if r.get("id")]

    async def get_genres(self, config: ProviderConfig, content_type: MetadataProviderType) -> list[ProviderGenreEvidence]:
        endpoint = "/genre/movie/list" if content_type == MetadataProviderType.MOVIE else "/genre/tv/list"
        data = await self._get(config, endpoint)
        genres = data.get("genres", [])
        return [
            ProviderGenreEvidence(external_id=g["id"], name=g["name"], content_type=content_type)
            for g in genres if "id" in g
        ]

    async def discover_movies(
        self, config: ProviderConfig, genre_ids: list[int] | None = None, page: int = 1
    ) -> list[ProviderMovieEvidence]:
        params: dict = {"page": page, "sort_by": "popularity.desc"}
        if genre_ids:
            params["with_genres"] = ",".join(str(gid) for gid in genre_ids)
        data = await self._get(config, "/discover/movie", params)
        results = data.get("results", [])
        return [self._parse_movie_search(r) for r in results if r.get("id")]

    async def discover_series(
        self, config: ProviderConfig, genre_ids: list[int] | None = None, page: int = 1
    ) -> list[ProviderSeriesEvidence]:
        params: dict = {"page": page, "sort_by": "popularity.desc"}
        if genre_ids:
            params["with_genres"] = ",".join(str(gid) for gid in genre_ids)
        data = await self._get(config, "/discover/tv", params)
        results = data.get("results", [])
        return [self._parse_series_search(r) for r in results if r.get("id")]

    async def get_season(
        self, config: ProviderConfig, series_external_id: int, season_number: int
    ) -> ProviderSeasonEvidence | None:
        data = await self._get(config, f"/tv/{series_external_id}/season/{season_number}")
        if not data or "id" not in data:
            return None
        episodes_data = data.get("episodes", [])
        episodes = [self._parse_episode(e) for e in episodes_data if e.get("id")]
        return ProviderSeasonEvidence(
            external_id=data["id"],
            season_number=data.get("season_number", season_number),
            name=data.get("name", ""),
            overview=data.get("overview", ""),
            poster_path=_build_image_url(data.get("poster_path"), "w500"),
            episode_count=len(episodes),
            air_date=_parse_date(data.get("air_date")),
            episodes=episodes,
        )

    async def get_movie_imdb_id(self, config: ProviderConfig, tmdb_id: int) -> str | None:
        data = await self._get(config, f"/movie/{tmdb_id}/external_ids")
        return data.get("imdb_id") or None

    async def get_series_imdb_id(self, config: ProviderConfig, tmdb_id: int) -> str | None:
        data = await self._get(config, f"/tv/{tmdb_id}/external_ids")
        return data.get("imdb_id") or None

    async def _get(self, config: ProviderConfig, path: str, params: dict | None = None) -> dict:
        if not config.api_key:
            return {}
        url = f"{TMDB_BASE_URL}{path}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url,
                    headers=self._headers(config),
                    params=params,
                    timeout=15,
                )
                if resp.status_code != 200:
                    return {}
                return resp.json()
        except httpx.HTTPError:
            return {}

    def _parse_movie_search(self, r: dict) -> ProviderMovieEvidence:
        return ProviderMovieEvidence(
            external_id=r["id"],
            title=r.get("title", r.get("name", "")),
            overview=r.get("overview", ""),
            release_date=_parse_date(r.get("release_date")),
            poster_path=_build_image_url(r.get("poster_path"), "w500"),
            backdrop_path=_build_image_url(r.get("backdrop_path")),
            vote_average=r.get("vote_average"),
        )

    def _parse_movie_detail(self, r: dict) -> ProviderMovieEvidence:
        belongs = r.get("belongs_to_collection")
        return ProviderMovieEvidence(
            external_id=r["id"],
            title=r.get("title", ""),
            overview=r.get("overview", ""),
            release_date=_parse_date(r.get("release_date")),
            poster_path=_build_image_url(r.get("poster_path"), "w500"),
            backdrop_path=_build_image_url(r.get("backdrop_path")),
            runtime_minutes=r.get("runtime"),
            vote_average=r.get("vote_average"),
            genres=_parse_genres(r.get("genres", [])),
            collection_external_id=belongs.get("id") if belongs else None,
            collection_name=belongs.get("name") if belongs else None,
            collection_overview=belongs.get("overview") if belongs else None,
        )

    def _parse_series_search(self, r: dict) -> ProviderSeriesEvidence:
        return ProviderSeriesEvidence(
            external_id=r["id"],
            title=r.get("name", r.get("title", "")),
            overview=r.get("overview", ""),
            first_air_date=_parse_date(r.get("first_air_date")),
            poster_path=_build_image_url(r.get("poster_path"), "w500"),
            backdrop_path=_build_image_url(r.get("backdrop_path")),
            vote_average=r.get("vote_average"),
        )

    def _parse_series_detail(self, r: dict) -> ProviderSeriesEvidence:
        seasons_data = r.get("seasons", [])
        seasons = [self._parse_season(s) for s in seasons_data if s.get("id")]
        return ProviderSeriesEvidence(
            external_id=r["id"],
            title=r.get("name", ""),
            overview=r.get("overview", ""),
            first_air_date=_parse_date(r.get("first_air_date")),
            last_air_date=_parse_date(r.get("last_air_date")),
            poster_path=_build_image_url(r.get("poster_path"), "w500"),
            backdrop_path=_build_image_url(r.get("backdrop_path")),
            status=r.get("status", ""),
            vote_average=r.get("vote_average"),
            genres=_parse_genres(r.get("genres", [])),
            seasons=seasons,
        )

    def _parse_season(self, s: dict) -> ProviderSeasonEvidence:
        return ProviderSeasonEvidence(
            external_id=s["id"],
            season_number=s.get("season_number", 0),
            name=s.get("name", ""),
            overview=s.get("overview", ""),
            poster_path=_build_image_url(s.get("poster_path"), "w500"),
            episode_count=s.get("episode_count", 0),
            air_date=_parse_date(s.get("air_date")),
        )

    def _parse_episode(self, e: dict) -> ProviderEpisodeEvidence:
        return ProviderEpisodeEvidence(
            external_id=e["id"],
            season_number=e.get("season_number", 0),
            episode_number=e.get("episode_number", 0),
            name=e.get("name", ""),
            overview=e.get("overview", ""),
            still_path=_build_image_url(e.get("still_path"), "w500"),
            runtime_minutes=e.get("runtime"),
            air_date=_parse_date(e.get("air_date")),
            vote_average=e.get("vote_average"),
        )
