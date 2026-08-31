"""User content state API endpoints.

Per ADR-0011, these endpoints manage user preference/state (favorites/following).
This is NOT a content catalog — it stores thin references to provider-sourced content.
"""

from __future__ import annotations

from litestar import Controller, get, post
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from kondooit.application.user_state_service import ContentReference, UserContentStateService
from kondooit.api.guards import jwt_guard, get_current_user


class ContentRefRequest(BaseModel):
    provider_key: str = Field(min_length=1)
    content_type: str = Field(pattern="^(movie|series)$")
    external_id: int


class UserStateResponse(BaseModel):
    provider_key: str
    content_type: str
    external_id: int
    is_favorite: bool
    is_following: bool


class UserStateController(Controller):
    path = "/user-state"
    tags = ["User State"]
    guards = [jwt_guard]

    @post(
        "/favorite",
        summary="Toggle favorite state for content",
        dependencies={"current_user": get_current_user},
    )
    async def toggle_favorite(
        self,
        data: ContentRefRequest,
        session: AsyncSession,
        user_state_service: UserContentStateService,
        current_user: dict,
    ) -> UserStateResponse:
        ref = ContentReference(
            provider_key=data.provider_key,
            content_type=data.content_type,
            external_id=data.external_id,
        )
        state = await user_state_service.toggle_favorite(session, current_user["id"], ref)
        return UserStateResponse(
            provider_key=state.provider_key,
            content_type=state.content_type,
            external_id=state.external_id,
            is_favorite=state.is_favorite,
            is_following=state.is_following,
        )

    @post(
        "/following",
        summary="Toggle following state for content",
        dependencies={"current_user": get_current_user},
    )
    async def toggle_following(
        self,
        data: ContentRefRequest,
        session: AsyncSession,
        user_state_service: UserContentStateService,
        current_user: dict,
    ) -> UserStateResponse:
        ref = ContentReference(
            provider_key=data.provider_key,
            content_type=data.content_type,
            external_id=data.external_id,
        )
        state = await user_state_service.toggle_following(session, current_user["id"], ref)
        return UserStateResponse(
            provider_key=state.provider_key,
            content_type=state.content_type,
            external_id=state.external_id,
            is_favorite=state.is_favorite,
            is_following=state.is_following,
        )

    @get(
        "/state/{provider_key:str}/{content_type:str}/{external_id:int}",
        summary="Get content state for current user",
        dependencies={"current_user": get_current_user},
    )
    async def get_state(
        self,
        provider_key: str,
        content_type: str,
        external_id: int,
        session: AsyncSession,
        user_state_service: UserContentStateService,
        current_user: dict,
    ) -> UserStateResponse:
        ref = ContentReference(
            provider_key=provider_key,
            content_type=content_type,
            external_id=external_id,
        )
        state = await user_state_service.get_state(session, current_user["id"], ref)
        if state is None:
            return UserStateResponse(
                provider_key=provider_key,
                content_type=content_type,
                external_id=external_id,
                is_favorite=False,
                is_following=False,
            )
        return UserStateResponse(
            provider_key=state.provider_key,
            content_type=state.content_type,
            external_id=state.external_id,
            is_favorite=state.is_favorite,
            is_following=state.is_following,
        )

    @get(
        "/favorites",
        summary="List user's favorites",
        dependencies={"current_user": get_current_user},
    )
    async def list_favorites(
        self,
        session: AsyncSession,
        user_state_service: UserContentStateService,
        current_user: dict,
        content_type: str | None = None,
    ) -> list[UserStateResponse]:
        states = await user_state_service.list_favorites(session, current_user["id"], content_type)
        return [
            UserStateResponse(
                provider_key=s.provider_key,
                content_type=s.content_type,
                external_id=s.external_id,
                is_favorite=s.is_favorite,
                is_following=s.is_following,
            )
            for s in states
        ]

    @get(
        "/following",
        summary="List user's followed content",
        dependencies={"current_user": get_current_user},
    )
    async def list_following(
        self,
        session: AsyncSession,
        user_state_service: UserContentStateService,
        current_user: dict,
        content_type: str | None = None,
    ) -> list[UserStateResponse]:
        states = await user_state_service.list_following(session, current_user["id"], content_type)
        return [
            UserStateResponse(
                provider_key=s.provider_key,
                content_type=s.content_type,
                external_id=s.external_id,
                is_favorite=s.is_favorite,
                is_following=s.is_following,
            )
            for s in states
        ]
