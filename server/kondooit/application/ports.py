"""Application-layer port definitions.

These abstract interfaces define what the application layer needs from
infrastructure. The infrastructure layer implements them. The application
and domain layers depend only on these interfaces, never on SQLAlchemy,
asyncpg, or other infrastructure details.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from kondooit.domain.content import Collection, Episode, Genre, Movie, Season, Series
from kondooit.domain.user import User
from kondooit.application.provider_ports import ProviderConfig

if TYPE_CHECKING:
    from kondooit.application.user_state_service import UserContentState


class AsyncSessionProtocol(Protocol):
    """Minimal async session protocol the application expects."""
    pass


class UserRepository(ABC):
    """Abstract repository for User persistence."""

    @abstractmethod
    async def get_by_id(self, session: AsyncSessionProtocol, user_id) -> User | None: ...

    @abstractmethod
    async def get_by_username(self, session: AsyncSessionProtocol, username: str) -> User | None: ...

    @abstractmethod
    async def create(self, session: AsyncSessionProtocol, user: User) -> User: ...

    @abstractmethod
    async def count(self, session: AsyncSessionProtocol) -> int: ...


class MovieRepository(ABC):
    """Abstract repository for Movie persistence."""

    @abstractmethod
    async def get_by_id(self, session: AsyncSessionProtocol, movie_id) -> Movie | None: ...

    @abstractmethod
    async def get_by_tmdb_id(self, session: AsyncSessionProtocol, tmdb_id: int) -> Movie | None: ...

    @abstractmethod
    async def get_by_tvdb_id(self, session: AsyncSessionProtocol, tvdb_id: int) -> Movie | None: ...

    @abstractmethod
    async def create(self, session: AsyncSessionProtocol, movie: Movie) -> Movie: ...

    @abstractmethod
    async def list(self, session: AsyncSessionProtocol, limit: int = 20, offset: int = 0) -> list[Movie]: ...

    @abstractmethod
    async def search(self, session: AsyncSessionProtocol, query: str, limit: int = 20) -> list[Movie]: ...


class SeriesRepository(ABC):
    """Abstract repository for Series persistence."""

    @abstractmethod
    async def get_by_id(self, session: AsyncSessionProtocol, series_id) -> Series | None: ...

    @abstractmethod
    async def get_by_tmdb_id(self, session: AsyncSessionProtocol, tmdb_id: int) -> Series | None: ...

    @abstractmethod
    async def get_by_tvdb_id(self, session: AsyncSessionProtocol, tvdb_id: int) -> Series | None: ...

    @abstractmethod
    async def create(self, session: AsyncSessionProtocol, series: Series) -> Series: ...

    @abstractmethod
    async def list(self, session: AsyncSessionProtocol, limit: int = 20, offset: int = 0) -> list[Series]: ...

    @abstractmethod
    async def search(self, session: AsyncSessionProtocol, query: str, limit: int = 20) -> list[Series]: ...


class SeasonRepository(ABC):
    """Abstract repository for Season persistence."""

    @abstractmethod
    async def get_by_id(self, session: AsyncSessionProtocol, season_id) -> Season | None: ...

    @abstractmethod
    async def get_by_series(self, session: AsyncSessionProtocol, series_id) -> list[Season]: ...

    @abstractmethod
    async def create(self, session: AsyncSessionProtocol, season: Season) -> Season: ...


class EpisodeRepository(ABC):
    """Abstract repository for Episode persistence."""

    @abstractmethod
    async def get_by_id(self, session: AsyncSessionProtocol, episode_id) -> Episode | None: ...

    @abstractmethod
    async def get_by_season(self, session: AsyncSessionProtocol, season_id) -> list[Episode]: ...

    @abstractmethod
    async def create(self, session: AsyncSessionProtocol, episode: Episode) -> Episode: ...


class GenreRepository(ABC):
    """Abstract repository for Genre persistence."""

    @abstractmethod
    async def get_all(self, session: AsyncSessionProtocol) -> list[Genre]: ...

    @abstractmethod
    async def get_by_id(self, session: AsyncSessionProtocol, genre_id) -> Genre | None: ...

    @abstractmethod
    async def get_by_tmdb_id(self, session: AsyncSessionProtocol, tmdb_id: int) -> Genre | None: ...

    @abstractmethod
    async def create(self, session: AsyncSessionProtocol, genre: Genre) -> Genre: ...


class CollectionRepository(ABC):
    """Abstract repository for Collection persistence."""

    @abstractmethod
    async def get_by_id(self, session: AsyncSessionProtocol, collection_id) -> Collection | None: ...

    @abstractmethod
    async def list(self, session: AsyncSessionProtocol, limit: int = 20, offset: int = 0) -> list[Collection]: ...

    @abstractmethod
    async def create(self, session: AsyncSessionProtocol, collection: Collection) -> Collection: ...


class ProviderConfigRepository(ABC):
    """Abstract repository for provider configuration persistence."""

    @abstractmethod
    async def get(self, session: AsyncSessionProtocol, key: str) -> ProviderConfig | None: ...

    @abstractmethod
    async def get_all(self, session: AsyncSessionProtocol) -> list[ProviderConfig]: ...

    @abstractmethod
    async def save(self, session: AsyncSessionProtocol, config: ProviderConfig) -> ProviderConfig: ...

    @abstractmethod
    async def delete(self, session: AsyncSessionProtocol, key: str) -> bool: ...


class UserContentStateRepository(ABC):
    """Abstract repository for user content state (favorites/following)."""

    @abstractmethod
    async def get(
        self, session: AsyncSessionProtocol, user_id: UUID,
        provider_key: str, content_type: str, external_id: int
    ) -> "UserContentState | None": ...

    @abstractmethod
    async def save(self, session: AsyncSessionProtocol, state: "UserContentState") -> "UserContentState": ...

    @abstractmethod
    async def list_favorites(
        self, session: AsyncSessionProtocol, user_id: UUID, content_type: str | None = None
    ) -> "list[UserContentState]": ...

    @abstractmethod
    async def list_following(
        self, session: AsyncSessionProtocol, user_id: UUID, content_type: str | None = None
    ) -> "list[UserContentState]": ...
