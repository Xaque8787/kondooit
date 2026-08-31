"""Security infrastructure implementations.

Concrete implementations of the application-layer security ports:
password hashing with bcrypt and JWT token management with PyJWT.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt

from kondooit.application.auth_ports import PasswordHasher, TokenService
from kondooit.config import Settings
from kondooit.domain.user import User


@dataclass(frozen=True)
class JwtTokenPayload:
    """Decoded JWT token payload."""
    user_id: UUID
    username: str
    role: str
    exp: int


class BcryptPasswordHasher(PasswordHasher):
    """Password hashing using bcrypt."""

    def hash(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )


class JwtTokenService(TokenService):
    """JWT token creation and verification using PyJWT."""

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret
        self._algorithm = settings.jwt_algorithm
        self._expiry_minutes = settings.jwt_expiry_minutes

    def create_access_token(self, user: User) -> str:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=self._expiry_minutes)
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value,
            "exp": int(exp.timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def verify_token(self, token: str) -> JwtTokenPayload | None:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.PyJWTError:
            return None
        return JwtTokenPayload(
            user_id=UUID(payload["sub"]),
            username=payload["username"],
            role=payload["role"],
            exp=payload["exp"],
        )
