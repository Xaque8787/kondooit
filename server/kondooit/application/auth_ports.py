"""Authentication and authorization port definitions.

These abstract interfaces define what the application layer needs from
infrastructure for security operations (password hashing, token management).
The infrastructure layer provides concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol
from uuid import UUID

from kondooit.domain.user import User


class PasswordHasher(ABC):
    """Hash and verify passwords."""

    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenService(ABC):
    """Create and verify authentication tokens."""

    @abstractmethod
    def create_access_token(self, user: User) -> str: ...

    @abstractmethod
    def verify_token(self, token: str) -> TokenPayload | None: ...



class TokenPayload(Protocol):
    """Decoded token payload — infrastructure-agnostic shape."""
    user_id: UUID
    username: str
    role: str
    exp: int
