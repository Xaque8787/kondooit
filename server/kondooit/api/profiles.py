"""Profile API endpoints."""

from __future__ import annotations

from litestar import Controller, get, post, put, delete
from litestar.exceptions import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from kondooit.api.guards import jwt_guard, get_current_user
from kondooit.application.profile_service import ProfileService


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    display_name: str
    avatar_color: str
    is_admin: bool
    max_resolution: int
    allow_direct_play: bool
    allow_remux: bool
    allow_transcode: bool
    auto_play: bool
    client_video_codecs: str
    client_audio_codecs: str


class CreateProfileRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    avatar_color: str = Field(default="#3B82F6", max_length=20)


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    avatar_color: str | None = Field(default=None, max_length=20)
    max_resolution: int | None = None
    allow_direct_play: bool | None = None
    allow_remux: bool | None = None
    allow_transcode: bool | None = None
    auto_play: bool | None = None
    client_video_codecs: str | None = None
    client_audio_codecs: str | None = None


class ProfileController(Controller):
    path = "/profiles"
    tags = ["Profiles"]
    guards = [jwt_guard]

    @get(
        "/",
        summary="List profiles for the current account",
        dependencies={"current_user": get_current_user},
    )
    async def list_profiles(
        self,
        session: AsyncSession,
        profile_service: ProfileService,
        current_user: dict,
    ) -> list[ProfileResponse]:
        profiles = await profile_service.list_profiles(session, current_user["id"])
        return [_to_response(p) for p in profiles]

    @post(
        "/",
        summary="Create a new profile",
        dependencies={"current_user": get_current_user},
    )
    async def create_profile(
        self,
        data: CreateProfileRequest,
        session: AsyncSession,
        profile_service: ProfileService,
        current_user: dict,
    ) -> ProfileResponse:
        try:
            profile = await profile_service.create_profile(
                session,
                user_id=current_user["id"],
                display_name=data.display_name,
                avatar_color=data.avatar_color,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return _to_response(profile)

    @get(
        "/{profile_id:str}",
        summary="Get a specific profile",
        dependencies={"current_user": get_current_user},
    )
    async def get_profile(
        self,
        profile_id: str,
        session: AsyncSession,
        profile_service: ProfileService,
        current_user: dict,
    ) -> ProfileResponse:
        from uuid import UUID
        profile = await profile_service.get_profile(session, UUID(profile_id))
        if profile is None or profile.user_id != current_user["id"]:
            raise HTTPException(status_code=404, detail="Profile not found")
        return _to_response(profile)

    @put(
        "/{profile_id:str}",
        summary="Update a profile",
        dependencies={"current_user": get_current_user},
    )
    async def update_profile(
        self,
        profile_id: str,
        data: UpdateProfileRequest,
        session: AsyncSession,
        profile_service: ProfileService,
        current_user: dict,
    ) -> ProfileResponse:
        from uuid import UUID
        profile = await profile_service.update_profile(
            session,
            profile_id=UUID(profile_id),
            user_id=current_user["id"],
            display_name=data.display_name,
            avatar_color=data.avatar_color,
            max_resolution=data.max_resolution,
            allow_direct_play=data.allow_direct_play,
            allow_remux=data.allow_remux,
            allow_transcode=data.allow_transcode,
            auto_play=data.auto_play,
            client_video_codecs=data.client_video_codecs,
            client_audio_codecs=data.client_audio_codecs,
        )
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        return _to_response(profile)

    @delete(
        "/{profile_id:str}",
        summary="Delete a profile (non-admin only)",
        dependencies={"current_user": get_current_user},
        status_code=200,
    )
    async def delete_profile(
        self,
        profile_id: str,
        session: AsyncSession,
        profile_service: ProfileService,
        current_user: dict,
    ) -> dict:
        from uuid import UUID
        deleted = await profile_service.delete_profile(
            session, profile_id=UUID(profile_id), user_id=current_user["id"],
        )
        if not deleted:
            raise HTTPException(status_code=400, detail="Cannot delete this profile")
        return {"deleted": True}


def _to_response(p) -> ProfileResponse:
    return ProfileResponse(
        id=str(p.id),
        user_id=str(p.user_id),
        display_name=p.display_name,
        avatar_color=p.avatar_color,
        is_admin=p.is_admin,
        max_resolution=p.max_resolution,
        allow_direct_play=p.allow_direct_play,
        allow_remux=p.allow_remux,
        allow_transcode=p.allow_transcode,
        auto_play=p.auto_play,
        client_video_codecs=p.client_video_codecs,
        client_audio_codecs=p.client_audio_codecs,
    )
