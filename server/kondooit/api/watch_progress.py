"""Watch progress API endpoints.

Manages playback position tracking, watched/unwatched status,
and "continue watching" queries. Per-profile when X-Profile-Id header is set.
"""

from __future__ import annotations

from uuid import UUID

from litestar import Controller, get, post, delete, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from kondooit.application.watch_progress_service import WatchProgressService
from kondooit.api.guards import jwt_guard, get_current_user


class ProgressReportRequest(BaseModel):
    provider_key: str = Field(min_length=1)
    content_type: str = Field(pattern="^(movie|episode)$")
    external_id: int
    position_seconds: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    series_external_id: int | None = None
    season_number: int | None = None
    episode_number: int | None = None


class MarkWatchedRequest(BaseModel):
    provider_key: str = Field(min_length=1)
    content_type: str = Field(pattern="^(movie|episode)$")
    external_id: int
    series_external_id: int | None = None
    season_number: int | None = None
    episode_number: int | None = None


class WatchProgressResponse(BaseModel):
    provider_key: str
    content_type: str
    external_id: int
    series_external_id: int | None = None
    season_number: int | None = None
    episode_number: int | None = None
    position_seconds: float
    duration_seconds: float
    progress_percent: float
    watched: bool
    updated_at: str | None = None


def _to_response(p) -> WatchProgressResponse:
    pct = 0.0
    if p.duration_seconds > 0:
        pct = round(min(p.position_seconds / p.duration_seconds, 1.0) * 100, 1)
    return WatchProgressResponse(
        provider_key=p.provider_key,
        content_type=p.content_type,
        external_id=p.external_id,
        series_external_id=p.series_external_id,
        season_number=p.season_number,
        episode_number=p.episode_number,
        position_seconds=p.position_seconds,
        duration_seconds=p.duration_seconds,
        progress_percent=pct,
        watched=p.watched,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
    )


def _get_profile_id(request: Request) -> UUID | None:
    raw = request.headers.get("X-Profile-Id")
    if raw:
        try:
            return UUID(raw)
        except ValueError:
            pass
    return None


class WatchProgressController(Controller):
    path = "/watch-progress"
    tags = ["Watch Progress"]
    guards = [jwt_guard]

    @post(
        "/report",
        summary="Report playback progress",
        dependencies={"current_user": get_current_user},
    )
    async def report_progress(
        self,
        request: Request,
        data: ProgressReportRequest,
        session: AsyncSession,
        watch_progress_service: WatchProgressService,
        current_user: dict,
    ) -> WatchProgressResponse:
        profile_id = _get_profile_id(request)
        progress = await watch_progress_service.report_progress(
            session,
            user_id=current_user["id"],
            profile_id=profile_id,
            provider_key=data.provider_key,
            content_type=data.content_type,
            external_id=data.external_id,
            position_seconds=data.position_seconds,
            duration_seconds=data.duration_seconds,
            series_external_id=data.series_external_id,
            season_number=data.season_number,
            episode_number=data.episode_number,
        )
        return _to_response(progress)

    @post(
        "/beacon",
        summary="Report progress via sendBeacon (fire-and-forget)",
        dependencies={"current_user": get_current_user},
    )
    async def beacon_progress(
        self,
        request: Request,
        data: ProgressReportRequest,
        session: AsyncSession,
        watch_progress_service: WatchProgressService,
        current_user: dict,
    ) -> WatchProgressResponse:
        profile_id = _get_profile_id(request)
        progress = await watch_progress_service.report_progress(
            session,
            user_id=current_user["id"],
            profile_id=profile_id,
            provider_key=data.provider_key,
            content_type=data.content_type,
            external_id=data.external_id,
            position_seconds=data.position_seconds,
            duration_seconds=data.duration_seconds,
            series_external_id=data.series_external_id,
            season_number=data.season_number,
            episode_number=data.episode_number,
        )
        return _to_response(progress)

    @post(
        "/mark-watched",
        summary="Manually mark content as watched",
        dependencies={"current_user": get_current_user},
    )
    async def mark_watched(
        self,
        request: Request,
        data: MarkWatchedRequest,
        session: AsyncSession,
        watch_progress_service: WatchProgressService,
        current_user: dict,
    ) -> WatchProgressResponse:
        profile_id = _get_profile_id(request)
        progress = await watch_progress_service.mark_watched(
            session,
            user_id=current_user["id"],
            profile_id=profile_id,
            provider_key=data.provider_key,
            content_type=data.content_type,
            external_id=data.external_id,
            series_external_id=data.series_external_id,
            season_number=data.season_number,
            episode_number=data.episode_number,
        )
        return _to_response(progress)

    @post(
        "/mark-unwatched",
        summary="Manually mark content as unwatched",
        dependencies={"current_user": get_current_user},
    )
    async def mark_unwatched(
        self,
        request: Request,
        data: MarkWatchedRequest,
        session: AsyncSession,
        watch_progress_service: WatchProgressService,
        current_user: dict,
    ) -> WatchProgressResponse | None:
        profile_id = _get_profile_id(request)
        progress = await watch_progress_service.mark_unwatched(
            session,
            user_id=current_user["id"],
            profile_id=profile_id,
            provider_key=data.provider_key,
            content_type=data.content_type,
            external_id=data.external_id,
        )
        if not progress:
            return WatchProgressResponse(
                provider_key=data.provider_key,
                content_type=data.content_type,
                external_id=data.external_id,
                position_seconds=0,
                duration_seconds=0,
                progress_percent=0,
                watched=False,
            )
        return _to_response(progress)

    @get(
        "/get/{provider_key:str}/{content_type:str}/{external_id:int}",
        summary="Get watch progress for a specific content item",
        dependencies={"current_user": get_current_user},
    )
    async def get_progress(
        self,
        request: Request,
        provider_key: str,
        content_type: str,
        external_id: int,
        session: AsyncSession,
        watch_progress_service: WatchProgressService,
        current_user: dict,
    ) -> WatchProgressResponse:
        profile_id = _get_profile_id(request)
        progress = await watch_progress_service.get_progress(
            session, current_user["id"], profile_id,
            provider_key, content_type, external_id,
        )
        if not progress:
            return WatchProgressResponse(
                provider_key=provider_key,
                content_type=content_type,
                external_id=external_id,
                position_seconds=0,
                duration_seconds=0,
                progress_percent=0,
                watched=False,
            )
        return _to_response(progress)

    @get(
        "/continue-watching",
        summary="Get items to continue watching",
        dependencies={"current_user": get_current_user},
    )
    async def continue_watching(
        self,
        request: Request,
        session: AsyncSession,
        watch_progress_service: WatchProgressService,
        current_user: dict,
        limit: int = 20,
    ) -> list[WatchProgressResponse]:
        profile_id = _get_profile_id(request)
        items = await watch_progress_service.get_continue_watching(
            session, current_user["id"], profile_id, limit,
        )
        return [_to_response(p) for p in items]

    @get(
        "/watched",
        summary="Get watched items",
        dependencies={"current_user": get_current_user},
    )
    async def list_watched(
        self,
        request: Request,
        session: AsyncSession,
        watch_progress_service: WatchProgressService,
        current_user: dict,
        content_type: str | None = None,
        limit: int = 100,
    ) -> list[WatchProgressResponse]:
        profile_id = _get_profile_id(request)
        items = await watch_progress_service.get_watched(
            session, current_user["id"], profile_id, content_type, limit,
        )
        return [_to_response(p) for p in items]

    @get(
        "/series/{provider_key:str}/{series_external_id:int}",
        summary="Get watch progress for all episodes in a series",
        dependencies={"current_user": get_current_user},
    )
    async def series_progress(
        self,
        request: Request,
        provider_key: str,
        series_external_id: int,
        session: AsyncSession,
        watch_progress_service: WatchProgressService,
        current_user: dict,
    ) -> list[WatchProgressResponse]:
        profile_id = _get_profile_id(request)
        items = await watch_progress_service.get_series_episode_progress(
            session, current_user["id"], profile_id, provider_key, series_external_id,
        )
        return [_to_response(p) for p in items]
