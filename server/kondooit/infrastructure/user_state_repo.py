"""User content state infrastructure: ORM model and repository.

Per ADR-0011, this is user preference/state, NOT a content catalog.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, String, select, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from kondooit.infrastructure.models import Base
from kondooit.application.ports import UserContentStateRepository
from kondooit.application.user_state_service import UserContentState


class UserContentStateModel(Base):
    __tablename__ = "user_content_state"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    profile_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    provider_key: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_following: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _model_to_domain(m: UserContentStateModel) -> UserContentState:
    return UserContentState(
        id=m.id,
        user_id=m.user_id,
        profile_id=m.profile_id,
        provider_key=m.provider_key,
        content_type=m.content_type,
        external_id=m.external_id,
        is_favorite=m.is_favorite,
        is_following=m.is_following,
    )


class SqlAlchemyUserContentStateRepository(UserContentStateRepository):
    """SQLAlchemy implementation of UserContentStateRepository."""

    async def get(
        self, session: AsyncSession, user_id: UUID,
        provider_key: str, content_type: str, external_id: int,
        profile_id: UUID | None = None,
    ) -> UserContentState | None:
        stmt = select(UserContentStateModel).where(
            UserContentStateModel.user_id == user_id,
            UserContentStateModel.provider_key == provider_key,
            UserContentStateModel.content_type == content_type,
            UserContentStateModel.external_id == external_id,
        )
        if profile_id is not None:
            stmt = stmt.where(UserContentStateModel.profile_id == profile_id)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        return _model_to_domain(model) if model else None

    async def save(self, session: AsyncSession, state: UserContentState) -> UserContentState:
        if state.id is not None:
            model = await session.get(UserContentStateModel, state.id)
            if model:
                model.is_favorite = state.is_favorite
                model.is_following = state.is_following
                await session.flush()
                return _model_to_domain(model)

        model = UserContentStateModel(
            user_id=state.user_id,
            profile_id=state.profile_id,
            provider_key=state.provider_key,
            content_type=state.content_type,
            external_id=state.external_id,
            is_favorite=state.is_favorite,
            is_following=state.is_following,
        )
        session.add(model)
        await session.flush()
        return _model_to_domain(model)

    async def list_favorites(
        self, session: AsyncSession, user_id: UUID, content_type: str | None = None,
        profile_id: UUID | None = None,
    ) -> list[UserContentState]:
        stmt = select(UserContentStateModel).where(
            UserContentStateModel.user_id == user_id,
            UserContentStateModel.is_favorite == True,
        )
        if profile_id is not None:
            stmt = stmt.where(UserContentStateModel.profile_id == profile_id)
        if content_type:
            stmt = stmt.where(UserContentStateModel.content_type == content_type)
        stmt = stmt.order_by(UserContentStateModel.updated_at.desc())
        result = await session.execute(stmt)
        return [_model_to_domain(m) for m in result.scalars().all()]

    async def list_following(
        self, session: AsyncSession, user_id: UUID, content_type: str | None = None,
        profile_id: UUID | None = None,
    ) -> list[UserContentState]:
        stmt = select(UserContentStateModel).where(
            UserContentStateModel.user_id == user_id,
            UserContentStateModel.is_following == True,
        )
        if profile_id is not None:
            stmt = stmt.where(UserContentStateModel.profile_id == profile_id)
        if content_type:
            stmt = stmt.where(UserContentStateModel.content_type == content_type)
        stmt = stmt.order_by(UserContentStateModel.updated_at.desc())
        result = await session.execute(stmt)
        return [_model_to_domain(m) for m in result.scalars().all()]
