"""Application-layer port for watch progress persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from kondooit.domain.watch_progress import WatchProgress


class WatchProgressRepository(ABC):

    @abstractmethod
    async def upsert(self, session, progress: WatchProgress) -> WatchProgress: ...

    @abstractmethod
    async def get(
        self, session, user_id: UUID, profile_id: UUID | None,
        provider_key: str, content_type: str, external_id: int,
    ) -> WatchProgress | None: ...

    @abstractmethod
    async def list_continue_watching(
        self, session, user_id: UUID, profile_id: UUID | None, limit: int = 20,
    ) -> list[WatchProgress]: ...

    @abstractmethod
    async def list_watched(
        self, session, user_id: UUID, profile_id: UUID | None,
        content_type: str | None = None, limit: int = 100,
    ) -> list[WatchProgress]: ...

    @abstractmethod
    async def list_series_episodes(
        self, session, user_id: UUID, profile_id: UUID | None,
        provider_key: str, series_external_id: int,
    ) -> list[WatchProgress]: ...

    @abstractmethod
    async def delete(
        self, session, user_id: UUID, profile_id: UUID | None,
        provider_key: str, content_type: str, external_id: int,
    ) -> bool: ...
