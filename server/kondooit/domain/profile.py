"""Profile domain entity.

A profile represents an individual household member within an account.
Each account (User) can have multiple profiles, each with their own
display name, preferences, and content state (favorites, watch history).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Profile:
    id: UUID | None
    user_id: UUID
    display_name: str
    avatar_color: str = "#3B82F6"
    is_admin: bool = False
    max_resolution: int = 2160
    allow_direct_play: bool = True
    allow_remux: bool = True
    allow_transcode: bool = False
    auto_play: bool = False
    client_video_codecs: str = ""
    client_audio_codecs: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
