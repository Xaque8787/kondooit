"""User domain entity — pure Python, no infrastructure dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class UserRole(str, Enum):
    """User role for authorization."""
    ADMIN = "admin"


@dataclass(frozen=True)
class User:
    """Canonical user entity owned by Kondooit."""
    id: UUID
    username: str
    email: str
    password_hash: str
    role: UserRole = UserRole.ADMIN
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
