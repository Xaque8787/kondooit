"""Watch progress infrastructure: ORM model and repository."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, Integer, String, select, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from kondooit.infrastructure.models import Base
from kondooit.application.watch_progress_ports import WatchProgressRepository
from kondooit.domain.watch_progress import WatchProgress


class WatchProgressModel(Base):
    __tablename__ = "watch_progress"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    profile_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    provider_key: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    series_external_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    season_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    watched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _to_domain(m: WatchProgressModel) -> WatchProgress:
    return WatchProgress(
        id=m.id,
        user_id=m.user_id,
        profile_id=m.profile_id,
        provider_key=m.provider_key,
        content_type=m.content_type,
        external_id=m.external_id,
        series_external_id=m.series_external_id,
        season_number=m.season_number,
        episode_number=m.episode_number,
        position_seconds=m.position_seconds,
        duration_seconds=m.duration_seconds,
        watched=m.watched,
        updated_at=m.updated_at,
    )


def _profile_filter(stmt, profile_id: UUID | None):
    if profile_id is not None:
        return stmt.where(WatchProgressModel.profile_id == profile_id)
    return stmt.where(WatchProgressModel.profile_id.is_(None))


class SqlAlchemyWatchProgressRepository(WatchProgressRepository):

    async def upsert(self, session: AsyncSession, progress: WatchProgress) -> WatchProgress:
        if progress.id is not None:
            model = await session.get(WatchProgressModel, progress.id)
            if model:
                model.position_seconds = progress.position_seconds
                model.duration_seconds = progress.duration_seconds
                model.watched = progress.watched
                model.series_external_id = progress.series_external_id
                model.season_number = progress.season_number
                model.episode_number = progress.episode_number
                model.updated_at = func.now()
                await session.flush()
                await session.refresh(model)
                return _to_domain(model)

        model = WatchProgressModel(
            user_id=progress.user_id,
            profile_id=progress.profile_id,
            provider_key=progress.provider_key,
            content_type=progress.content_type,
            external_id=progress.external_id,
            series_external_id=progress.series_external_id,
            season_number=progress.season_number,
            episode_number=progress.episode_number,
            position_seconds=progress.position_seconds,
            duration_seconds=progress.duration_seconds,
            watched=progress.watched,
        )
        session.add(model)
        await session.flush()
        return _to_domain(model)

    async def get(
        self, session: AsyncSession, user_id: UUID, profile_id: UUID | None,
        provider_key: str, content_type: str, external_id: int,
    ) -> WatchProgress | None:
        stmt = select(WatchProgressModel).where(
            WatchProgressModel.user_id == user_id,
            WatchProgressModel.provider_key == provider_key,
            WatchProgressModel.content_type == content_type,
            WatchProgressModel.external_id == external_id,
        )
        stmt = _profile_filter(stmt, profile_id)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def list_continue_watching(
        self, session: AsyncSession, user_id: UUID, profile_id: UUID | None, limit: int = 20,
    ) -> list[WatchProgress]:
        stmt = select(WatchProgressModel).where(
            WatchProgressModel.user_id == user_id,
            WatchProgressModel.watched == False,
            WatchProgressModel.position_seconds > 0,
        )
        stmt = _profile_filter(stmt, profile_id)
        stmt = stmt.order_by(WatchProgressModel.updated_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return [_to_domain(m) for m in result.scalars().all()]

    async def list_watched(
        self, session: AsyncSession, user_id: UUID, profile_id: UUID | None,
        content_type: str | None = None, limit: int = 100,
    ) -> list[WatchProgress]:
        stmt = select(WatchProgressModel).where(
            WatchProgressModel.user_id == user_id,
            WatchProgressModel.watched == True,
        )
        stmt = _profile_filter(stmt, profile_id)
        if content_type:
            stmt = stmt.where(WatchProgressModel.content_type == content_type)
        stmt = stmt.order_by(WatchProgressModel.updated_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return [_to_domain(m) for m in result.scalars().all()]

    async def list_series_episodes(
        self, session: AsyncSession, user_id: UUID, profile_id: UUID | None,
        provider_key: str, series_external_id: int,
    ) -> list[WatchProgress]:
        stmt = select(WatchProgressModel).where(
            WatchProgressModel.user_id == user_id,
            WatchProgressModel.provider_key == provider_key,
            WatchProgressModel.content_type == "episode",
            WatchProgressModel.series_external_id == series_external_id,
        )
        stmt = _profile_filter(stmt, profile_id)
        stmt = stmt.order_by(WatchProgressModel.season_number, WatchProgressModel.episode_number)
        result = await session.execute(stmt)
        return [_to_domain(m) for m in result.scalars().all()]

    async def delete(
        self, session: AsyncSession, user_id: UUID, profile_id: UUID | None,
        provider_key: str, content_type: str, external_id: int,
    ) -> bool:
        stmt = select(WatchProgressModel).where(
            WatchProgressModel.user_id == user_id,
            WatchProgressModel.provider_key == provider_key,
            WatchProgressModel.content_type == content_type,
            WatchProgressModel.external_id == external_id,
        )
        stmt = _profile_filter(stmt, profile_id)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            await session.delete(model)
            await session.flush()
            return True
        return False
