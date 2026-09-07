"""In-memory playback command queue.

The web UI posts a play command here; the companion polls and picks it up.
Only one pending command per user at a time (latest wins).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from uuid import UUID


@dataclass
class PlayCommand:
    stream_url: str
    title: str
    provider_key: str
    content_type: str
    external_id: int
    duration_seconds: float
    series_external_id: int | None = None
    season_number: int | None = None
    episode_number: int | None = None
    created_at: float = 0.0


COMMAND_TTL = 30.0


class PlaybackQueue:
    """One pending play command per user. Commands expire after 30 seconds."""

    def __init__(self) -> None:
        self._commands: dict[UUID, PlayCommand] = {}

    def push(self, user_id: UUID, cmd: PlayCommand) -> None:
        cmd.created_at = time.monotonic()
        self._commands[user_id] = cmd

    def poll(self, user_id: UUID) -> PlayCommand | None:
        cmd = self._commands.pop(user_id, None)
        if cmd is None:
            return None
        if time.monotonic() - cmd.created_at > COMMAND_TTL:
            return None
        return cmd
