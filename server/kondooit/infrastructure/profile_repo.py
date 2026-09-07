"""Profile infrastructure: ORM model and repository."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String, select, func, delete as sa_delete
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from kondooit.infrastructure.models import Base
from kondooit.application.profile_ports import ProfileRepository
from kondooit.domain.profile import Profile


class ProfileModel(Base):
    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_color: Mapped[str] = mapped_column(String, nullable=False, default="#3B82F6")
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    preferred_quality: Mapped[str] = mapped_column(String, nullable=False, default="1080p")
    allow_server_processing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _model_to_domain(m: ProfileModel) -> Profile:
    return Profile(
        id=m.id,
        user_id=m.user_id,
        display_name=m.display_name,
        avatar_color=m.avatar_color,
        is_admin=m.is_admin,
        preferred_quality=m.preferred_quality,
        allow_server_processing=m.allow_server_processing,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class SqlAlchemyProfileRepository(ProfileRepository):

    async def get_by_id(self, session: AsyncSession, profile_id: UUID) -> Profile | None:
        model = await session.get(ProfileModel, profile_id)
        return _model_to_domain(model) if model else None

    async def list_by_user(self, session: AsyncSession, user_id: UUID) -> list[Profile]:
        stmt = (
            select(ProfileModel)
            .where(ProfileModel.user_id == user_id)
            .order_by(ProfileModel.is_admin.desc(), ProfileModel.created_at.asc())
        )
        result = await session.execute(stmt)
        return [_model_to_domain(m) for m in result.scalars().all()]

    async def create(self, session: AsyncSession, profile: Profile) -> Profile:
        model = ProfileModel(
            user_id=profile.user_id,
            display_name=profile.display_name,
            avatar_color=profile.avatar_color,
            is_admin=profile.is_admin,
            preferred_quality=profile.preferred_quality,
            allow_server_processing=profile.allow_server_processing,
        )
        session.add(model)
        await session.flush()
        return _model_to_domain(model)

    async def update(self, session: AsyncSession, profile: Profile) -> Profile:
        model = await session.get(ProfileModel, profile.id)
        if model is None:
            raise ValueError(f"Profile {profile.id} not found")
        model.display_name = profile.display_name
        model.avatar_color = profile.avatar_color
        model.preferred_quality = profile.preferred_quality
        model.allow_server_processing = profile.allow_server_processing
        await session.flush()
        return _model_to_domain(model)

    async def delete(self, session: AsyncSession, profile_id: UUID) -> bool:
        stmt = sa_delete(ProfileModel).where(ProfileModel.id == profile_id)
        result = await session.execute(stmt)
        return result.rowcount > 0
