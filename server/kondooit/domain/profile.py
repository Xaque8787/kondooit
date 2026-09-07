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
    preferred_quality: str = "1080p"
    allow_server_processing: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
