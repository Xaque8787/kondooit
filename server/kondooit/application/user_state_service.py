"""User content state application service.

Per ADR-0011, user state is preference/state, NOT a content catalog.
Favorites and Following are thin references connecting users to provider-sourced content.
Metadata is always retrieved from the provider; this service stores only the relationship.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from kondooit.application.ports import UserContentStateRepository


@dataclass(frozen=True)
class ContentReference:
    """A reference to provider-sourced content. Not a canonical identity."""
    provider_key: str
    content_type: str
    external_id: int


@dataclass(frozen=True)
class UserContentState:
    """User's preference state for a piece of content."""
    id: UUID | None
    user_id: UUID
    provider_key: str
    content_type: str
    external_id: int
    is_favorite: bool = False
    is_following: bool = False
    profile_id: UUID | None = None


class UserContentStateService:
    """Application service for managing user content state (favorites/following)."""

    def __init__(self, state_repo: UserContentStateRepository) -> None:
        self._repo = state_repo

    async def toggle_favorite(
        self, session, user_id: UUID, ref: ContentReference,
        profile_id: UUID | None = None,
    ) -> UserContentState:
        """Toggle the favorite state for a content reference."""
        state = await self._repo.get(
            session, user_id, ref.provider_key, ref.content_type, ref.external_id,
            profile_id=profile_id,
        )
        if state is None:
            state = UserContentState(
                id=None, user_id=user_id,
                provider_key=ref.provider_key,
                content_type=ref.content_type,
                external_id=ref.external_id,
                is_favorite=True, is_following=False,
                profile_id=profile_id,
            )
        else:
            state = UserContentState(
                id=state.id, user_id=state.user_id,
                provider_key=state.provider_key,
                content_type=state.content_type,
                external_id=state.external_id,
                is_favorite=not state.is_favorite,
                is_following=state.is_following,
                profile_id=state.profile_id,
            )
        saved = await self._repo.save(session, state)
        await session.commit()
        return saved

    async def toggle_following(
        self, session, user_id: UUID, ref: ContentReference,
        profile_id: UUID | None = None,
    ) -> UserContentState:
        """Toggle the following state for a content reference."""
        state = await self._repo.get(
            session, user_id, ref.provider_key, ref.content_type, ref.external_id,
            profile_id=profile_id,
        )
        if state is None:
            state = UserContentState(
                id=None, user_id=user_id,
                provider_key=ref.provider_key,
                content_type=ref.content_type,
                external_id=ref.external_id,
                is_favorite=False, is_following=True,
                profile_id=profile_id,
            )
        else:
            state = UserContentState(
                id=state.id, user_id=state.user_id,
                provider_key=state.provider_key,
                content_type=state.content_type,
                external_id=state.external_id,
                is_favorite=state.is_favorite,
                is_following=not state.is_following,
                profile_id=state.profile_id,
            )
        saved = await self._repo.save(session, state)
        await session.commit()
        return saved

    async def get_state(
        self, session, user_id: UUID, ref: ContentReference,
        profile_id: UUID | None = None,
    ) -> UserContentState | None:
        """Get the current state for a content reference."""
        return await self._repo.get(
            session, user_id, ref.provider_key, ref.content_type, ref.external_id,
            profile_id=profile_id,
        )

    async def list_favorites(
        self, session, user_id: UUID, content_type: str | None = None,
        profile_id: UUID | None = None,
    ) -> list[UserContentState]:
        """List user's favorites, optionally filtered by content type."""
        return await self._repo.list_favorites(session, user_id, content_type, profile_id=profile_id)

    async def list_following(
        self, session, user_id: UUID, content_type: str | None = None,
        profile_id: UUID | None = None,
    ) -> list[UserContentState]:
        """List user's followed content, optionally filtered by content type."""
        return await self._repo.list_following(session, user_id, content_type, profile_id=profile_id)
