"""Authentication API endpoints."""

from __future__ import annotations

from litestar import Controller, post, get
from litestar.exceptions import HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from kondooit.api.guards import jwt_guard, get_current_user
from kondooit.application.auth_service import AuthService
from kondooit.application.profile_service import ProfileService


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=512)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class BootstrapAdminRequest(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=512)


class BootstrapAdminResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    access_token: str
    token_type: str = "bearer"


class ProfileBrief(BaseModel):
    id: str
    display_name: str
    avatar_color: str
    is_admin: bool


class MeResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    profiles: list[ProfileBrief] = []


class AuthController(Controller):
    path = "/auth"
    tags = ["Authentication"]

    @post("/login", summary="Login and receive a JWT token")
    async def login(
        self,
        data: LoginRequest,
        session: AsyncSession,
        auth_service: AuthService,
        profile_service: ProfileService,
    ) -> LoginResponse:
        token = await auth_service.login(session, data.username, data.password)
        if token is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        user = await auth_service.get_user_from_token(session, token)
        if user:
            await profile_service.ensure_admin_profile(session, user.id, user.username)
        return LoginResponse(access_token=token)

    @post("/bootstrap", summary="Create the initial admin (only if no admin exists)")
    async def bootstrap_admin(
        self,
        data: BootstrapAdminRequest,
        session: AsyncSession,
        auth_service: AuthService,
    ) -> BootstrapAdminResponse:
        result = await auth_service.bootstrap_admin(
            session,
            username=data.username,
            email=data.email,
            password=data.password,
        )
        if result is None:
            raise HTTPException(status_code=409, detail="An administrator already exists")
        user, token = result
        return BootstrapAdminResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            role=user.role.value,
            access_token=token,
        )

    @get(
        "/me",
        summary="Get the current authenticated user with profiles",
        guards=[jwt_guard],
        dependencies={"current_user": get_current_user},
    )
    async def me(
        self,
        current_user: dict,
        session: AsyncSession,
        profile_service: ProfileService,
    ) -> MeResponse:
        user_id = current_user["id"]
        await profile_service.ensure_admin_profile(session, user_id, current_user["username"])
        profiles = await profile_service.list_profiles(session, user_id)
        return MeResponse(
            id=str(user_id),
            username=current_user["username"],
            email=current_user["email"],
            role=current_user["role"],
            is_active=current_user["is_active"],
            profiles=[
                ProfileBrief(
                    id=str(p.id),
                    display_name=p.display_name,
                    avatar_color=p.avatar_color,
                    is_admin=p.is_admin,
                )
                for p in profiles
            ],
        )
