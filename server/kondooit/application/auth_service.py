"""Authentication use cases.

These are the application-layer services that orchestrate authentication
flows. They depend on repository and security port interfaces, never on
infrastructure implementations directly.
"""

from __future__ import annotations

import uuid

from kondooit.application.auth_ports import PasswordHasher, TokenService
from kondooit.application.ports import UserRepository
from kondooit.domain.user import User, UserRole


class AuthService:
    """Application service for authentication operations."""

    def __init__(
        self,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._token_service = token_service

    async def login(self, session, username: str, password: str) -> str | None:
        """Authenticate a user and return a JWT token, or None if invalid."""
        user = await self._user_repo.get_by_username(session, username)
        if user is None:
            return None
        if not user.is_active:
            return None
        if not self._password_hasher.verify(password, user.password_hash):
            return None
        return self._token_service.create_access_token(user)

    async def get_user_from_token(self, session, token: str) -> User | None:
        """Verify a token and return the corresponding user, or None."""
        payload = self._token_service.verify_token(token)
        if payload is None:
            return None
        return await self._user_repo.get_by_id(session, payload.user_id)

    async def bootstrap_admin(
        self,
        session,
        username: str,
        email: str,
        password: str,
    ) -> tuple[User, str] | None:
        """Create the initial admin if no users exist.

        Returns (user, token) on success, or None if an admin already exists.
        """
        count = await self._user_repo.count(session)
        if count > 0:
            return None

        user = User(
            id=uuid.uuid4(),
            username=username,
            email=email,
            password_hash=self._password_hasher.hash(password),
            role=UserRole.ADMIN,
        )
        created = await self._user_repo.create(session, user)
        await session.commit()
        token = self._token_service.create_access_token(created)
        return created, token

    async def admin_exists(self, session) -> bool:
        """Check if any admin user exists."""
        count = await self._user_repo.count(session)
        return count > 0
