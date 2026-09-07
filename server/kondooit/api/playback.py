"""Playback command API.

POST /playback/play   — web UI sends a play command
GET  /playback/poll   — companion polls for pending commands
"""

from __future__ import annotations

from litestar import Controller, get, post
from pydantic import BaseModel, Field
from litestar.exceptions import NotFoundException

from kondooit.api.guards import jwt_guard, get_current_user
from kondooit.application.playback_queue import PlaybackQueue, PlayCommand


class PlayRequest(BaseModel):
    stream_url: str = Field(min_length=1)
    title: str = ""
    provider_key: str = "unknown"
    content_type: str = "movie"
    external_id: int = 0
    duration_seconds: float = 0
    series_external_id: int | None = None
    season_number: int | None = None
    episode_number: int | None = None


class PlayCommandResponse(BaseModel):
    stream_url: str
    title: str
    provider_key: str
    content_type: str
    external_id: int
    duration_seconds: float
    series_external_id: int | None = None
    season_number: int | None = None
    episode_number: int | None = None


class PlaybackController(Controller):
    path = "/playback"
    tags = ["Playback"]
    guards = [jwt_guard]

    @post(
        "/play",
        summary="Queue a play command for the companion",
        dependencies={"current_user": get_current_user},
    )
    async def queue_play(
        self,
        data: PlayRequest,
        current_user: dict,
        playback_queue: PlaybackQueue,
    ) -> dict[str, str]:
        cmd = PlayCommand(
            stream_url=data.stream_url,
            title=data.title,
            provider_key=data.provider_key,
            content_type=data.content_type,
            external_id=data.external_id,
            duration_seconds=data.duration_seconds,
            series_external_id=data.series_external_id,
            season_number=data.season_number,
            episode_number=data.episode_number,
        )
        playback_queue.push(current_user["id"], cmd)
        return {"status": "queued"}

    @get(
        "/poll",
        summary="Poll for a pending play command (companion calls this)",
        dependencies={"current_user": get_current_user},
    )
    async def poll_command(
        self,
        current_user: dict,
        playback_queue: PlaybackQueue,
    ) -> PlayCommandResponse:
        cmd = playback_queue.poll(current_user["id"])
        if cmd is None:
            raise NotFoundException("No pending playback command")
        return PlayCommandResponse(
            stream_url=cmd.stream_url,
            title=cmd.title,
            provider_key=cmd.provider_key,
            content_type=cmd.content_type,
            external_id=cmd.external_id,
            duration_seconds=cmd.duration_seconds,
            series_external_id=cmd.series_external_id,
            season_number=cmd.season_number,
            episode_number=cmd.episode_number,
        )
