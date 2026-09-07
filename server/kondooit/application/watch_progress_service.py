"""Watch progress application service."""

from __future__ import annotations

from uuid import UUID

from kondooit.application.watch_progress_ports import WatchProgressRepository
from kondooit.domain.watch_progress import WatchProgress, WATCHED_THRESHOLD


class WatchProgressService:

    def __init__(self, repo: WatchProgressRepository) -> None:
        self._repo = repo

    async def report_progress(
        self,
        session,
        user_id: UUID,
        profile_id: UUID | None,
        provider_key: str,
        content_type: str,
        external_id: int,
        position_seconds: float,
        duration_seconds: float,
        series_external_id: int | None = None,
        season_number: int | None = None,
        episode_number: int | None = None,
    ) -> WatchProgress:
        existing = await self._repo.get(
            session, user_id, profile_id, provider_key, content_type, external_id,
        )

        watched = False
        if duration_seconds > 0 and (position_seconds / duration_seconds) >= WATCHED_THRESHOLD:
            watched = True
        elif existing and existing.watched:
            watched = True

        progress = WatchProgress(
            id=existing.id if existing else None,
            user_id=user_id,
            profile_id=profile_id,
            provider_key=provider_key,
            content_type=content_type,
            external_id=external_id,
            series_external_id=series_external_id,
            season_number=season_number,
            episode_number=episode_number,
            position_seconds=position_seconds,
            duration_seconds=duration_seconds,
            watched=watched,
        )
        saved = await self._repo.upsert(session, progress)
        await session.commit()
        return saved

    async def mark_watched(
        self,
        session,
        user_id: UUID,
        profile_id: UUID | None,
        provider_key: str,
        content_type: str,
        external_id: int,
        series_external_id: int | None = None,
        season_number: int | None = None,
        episode_number: int | None = None,
    ) -> WatchProgress:
        existing = await self._repo.get(
            session, user_id, profile_id, provider_key, content_type, external_id,
        )
        progress = WatchProgress(
            id=existing.id if existing else None,
            user_id=user_id,
            profile_id=profile_id,
            provider_key=provider_key,
            content_type=content_type,
            external_id=external_id,
            series_external_id=series_external_id or (existing.series_external_id if existing else None),
            season_number=season_number or (existing.season_number if existing else None),
            episode_number=episode_number or (existing.episode_number if existing else None),
            position_seconds=existing.position_seconds if existing else 0,
            duration_seconds=existing.duration_seconds if existing else 0,
            watched=True,
        )
        saved = await self._repo.upsert(session, progress)
        await session.commit()
        return saved

    async def mark_unwatched(
        self,
        session,
        user_id: UUID,
        profile_id: UUID | None,
        provider_key: str,
        content_type: str,
        external_id: int,
    ) -> WatchProgress | None:
        existing = await self._repo.get(
            session, user_id, profile_id, provider_key, content_type, external_id,
        )
        if not existing:
            return None
        progress = WatchProgress(
            id=existing.id,
            user_id=existing.user_id,
            profile_id=existing.profile_id,
            provider_key=existing.provider_key,
            content_type=existing.content_type,
            external_id=existing.external_id,
            series_external_id=existing.series_external_id,
            season_number=existing.season_number,
            episode_number=existing.episode_number,
            position_seconds=0,
            duration_seconds=existing.duration_seconds,
            watched=False,
        )
        saved = await self._repo.upsert(session, progress)
        await session.commit()
        return saved

    async def get_progress(
        self, session, user_id: UUID, profile_id: UUID | None,
        provider_key: str, content_type: str, external_id: int,
    ) -> WatchProgress | None:
        return await self._repo.get(
            session, user_id, profile_id, provider_key, content_type, external_id,
        )

    async def get_continue_watching(
        self, session, user_id: UUID, profile_id: UUID | None, limit: int = 20,
    ) -> list[WatchProgress]:
        return await self._repo.list_continue_watching(session, user_id, profile_id, limit)

    async def get_watched(
        self, session, user_id: UUID, profile_id: UUID | None,
        content_type: str | None = None, limit: int = 100,
    ) -> list[WatchProgress]:
        return await self._repo.list_watched(session, user_id, profile_id, content_type, limit)

    async def get_series_episode_progress(
        self, session, user_id: UUID, profile_id: UUID | None,
        provider_key: str, series_external_id: int,
    ) -> list[WatchProgress]:
        return await self._repo.list_series_episodes(
            session, user_id, profile_id, provider_key, series_external_id,
        )
