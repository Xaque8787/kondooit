"""Profile application service.

Manages CRUD for household profiles under an account. The admin's
default profile is created automatically during bootstrap.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from kondooit.application.profile_ports import ProfileRepository
from kondooit.domain.profile import Profile

MAX_PROFILES_PER_USER = 8


class ProfileService:

    def __init__(self, profile_repo: ProfileRepository) -> None:
        self._repo = profile_repo

    async def list_profiles(self, session, user_id: UUID) -> list[Profile]:
        return await self._repo.list_by_user(session, user_id)

    async def get_profile(self, session, profile_id: UUID) -> Profile | None:
        return await self._repo.get_by_id(session, profile_id)

    async def create_profile(
        self,
        session,
        user_id: UUID,
        display_name: str,
        avatar_color: str = "#3B82F6",
        preferred_quality: str = "1080p",
        allow_server_processing: bool = True,
    ) -> Profile:
        existing = await self._repo.list_by_user(session, user_id)
        if len(existing) >= MAX_PROFILES_PER_USER:
            raise ValueError(f"Maximum of {MAX_PROFILES_PER_USER} profiles per account")

        profile = Profile(
            id=None,
            user_id=user_id,
            display_name=display_name.strip(),
            avatar_color=avatar_color,
            is_admin=False,
            preferred_quality=preferred_quality,
            allow_server_processing=allow_server_processing,
        )
        saved = await self._repo.create(session, profile)
        await session.commit()
        return saved

    async def update_profile(
        self,
        session,
        profile_id: UUID,
        user_id: UUID,
        display_name: str | None = None,
        avatar_color: str | None = None,
        preferred_quality: str | None = None,
        allow_server_processing: bool | None = None,
    ) -> Profile | None:
        profile = await self._repo.get_by_id(session, profile_id)
        if profile is None or profile.user_id != user_id:
            return None

        updates = {}
        if display_name is not None:
            updates["display_name"] = display_name.strip()
        if avatar_color is not None:
            updates["avatar_color"] = avatar_color
        if preferred_quality is not None:
            updates["preferred_quality"] = preferred_quality
        if allow_server_processing is not None:
            updates["allow_server_processing"] = allow_server_processing

        if not updates:
            return profile

        updated = replace(profile, **updates)
        saved = await self._repo.update(session, updated)
        await session.commit()
        return saved

    async def delete_profile(self, session, profile_id: UUID, user_id: UUID) -> bool:
        profile = await self._repo.get_by_id(session, profile_id)
        if profile is None or profile.user_id != user_id:
            return False
        if profile.is_admin:
            return False
        deleted = await self._repo.delete(session, profile_id)
        if deleted:
            await session.commit()
        return deleted

    async def ensure_admin_profile(self, session, user_id: UUID, username: str) -> Profile:
        """Ensure the admin user has a default profile. Idempotent."""
        existing = await self._repo.list_by_user(session, user_id)
        for p in existing:
            if p.is_admin:
                return p

        profile = Profile(
            id=None,
            user_id=user_id,
            display_name=username,
            avatar_color="#3B82F6",
            is_admin=True,
            preferred_quality="1080p",
            allow_server_processing=True,
        )
        saved = await self._repo.create(session, profile)
        await session.commit()
        return saved
