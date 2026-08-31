"""JWT authentication guard for Litestar.

This guard extracts the Bearer token from the Authorization header,
verifies it, and attaches the current user to the request state.
Unauthenticated requests are rejected with 401.
"""

from __future__ import annotations

from typing import Any

from litestar import Request
from litestar.connection import ASGIConnection
from litestar.exceptions import HTTPException
from litestar.handlers.base import BaseRouteHandler

from kondooit.application.auth_service import AuthService


async def jwt_guard(connection: ASGIConnection[Any, Any, Any, Any], _: BaseRouteHandler) -> None:
    """Verify the JWT token and attach the current user to request state."""
    auth_header = connection.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[7:]

    auth_service: AuthService = connection.app.state.get("auth_service")
    if auth_service is None:
        raise HTTPException(status_code=500, detail="Auth service not configured")

    session_factory = connection.app.state.get("session_factory")
    if session_factory is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    async with session_factory() as session:
        user = await auth_service.get_user_from_token(session, token)

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    connection.state.current_user = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
    }


def get_current_user(request: Request) -> dict:
    """Dependency that returns the authenticated user's info from request state."""
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
