"""Profile repository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from kondooit.domain.profile import Profile


class ProfileRepository(ABC):

    @abstractmethod
    async def get_by_id(self, session, profile_id: UUID) -> Profile | None: ...

    @abstractmethod
    async def list_by_user(self, session, user_id: UUID) -> list[Profile]: ...

    @abstractmethod
    async def create(self, session, profile: Profile) -> Profile: ...

    @abstractmethod
    async def update(self, session, profile: Profile) -> Profile: ...

    @abstractmethod
    async def delete(self, session, profile_id: UUID) -> bool: ...
