"""Watch progress domain entity.

Tracks per-profile playback position and watched status for movies and episodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

WATCHED_THRESHOLD = 0.90


@dataclass(frozen=True)
class WatchProgress:
    """Playback progress for a single content item (movie or episode)."""
    id: UUID | None
    user_id: UUID
    profile_id: UUID | None
    provider_key: str
    content_type: str  # 'movie' or 'episode'
    external_id: int
    series_external_id: int | None
    season_number: int | None
    episode_number: int | None
    position_seconds: float
    duration_seconds: float
    watched: bool
    updated_at: datetime | None = None

    @property
    def progress_fraction(self) -> float:
        if self.duration_seconds <= 0:
            return 0.0
        return min(self.position_seconds / self.duration_seconds, 1.0)

    def should_mark_watched(self) -> bool:
        return self.progress_fraction >= WATCHED_THRESHOLD
