"""Repository pattern tests using an in-memory SQLite database.

These tests verify that the SQLAlchemy repository implementations correctly
map between ORM models and domain entities. They use SQLite for testing
isolation — the production database is PostgreSQL, but the repository
pattern abstracts the database driver.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from kondooit.domain.content import Genre, Movie, Series
from kondooit.domain.user import User, UserRole
from kondooit.infrastructure.models import Base
from kondooit.infrastructure.repositories import (
    SqlAlchemyGenreRepository,
    SqlAlchemyMovieRepository,
    SqlAlchemySeriesRepository,
    SqlAlchemyUserRepository,
)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_user_repository_create_and_get(session: AsyncSession) -> None:
    repo = SqlAlchemyUserRepository()
    user = User(
        id=uuid.uuid4(),
        username="admin",
        email="admin@kondooit.local",
        password_hash="hashed_password_here",
        role=UserRole.ADMIN,
    )
    created = await repo.create(session, user)
    await session.commit()

    assert created.username == "admin"
    assert created.email == "admin@kondooit.local"
    assert created.role == UserRole.ADMIN

    found = await repo.get_by_username(session, "admin")
    assert found is not None
    assert found.username == "admin"


@pytest.mark.asyncio
async def test_genre_repository_create_and_get(session: AsyncSession) -> None:
    repo = SqlAlchemyGenreRepository()
    genre = Genre(
        id=uuid.uuid4(),
        name="Action",
        tmdb_id=28,
    )
    created = await repo.create(session, genre)
    await session.commit()

    assert created.name == "Action"

    found = await repo.get_by_tmdb_id(session, 28)
    assert found is not None
    assert found.name == "Action"


@pytest.mark.asyncio
async def test_movie_repository_create_and_list(session: AsyncSession) -> None:
    genre_repo = SqlAlchemyGenreRepository()
    genre = Genre(id=uuid.uuid4(), name="Sci-Fi", tmdb_id=878)
    await genre_repo.create(session, genre)
    await session.flush()

    movie_repo = SqlAlchemyMovieRepository()
    movie = Movie(
        id=uuid.uuid4(),
        title="The Matrix",
        overview="A computer hacker learns about reality.",
        release_date=date(1999, 3, 31),
        runtime_minutes=136,
        vote_average=8.2,
        genres=[genre],
        tmdb_id=603,
    )
    created = await movie_repo.create(session, movie)
    await session.commit()

    assert created.title == "The Matrix"
    assert created.tmdb_id == 603
    assert len(created.genres) == 1
    assert created.genres[0].name == "Sci-Fi"

    movies = await movie_repo.list(session)
    assert len(movies) == 1
    assert movies[0].title == "The Matrix"

    found = await movie_repo.get_by_tmdb_id(session, 603)
    assert found is not None
    assert found.title == "The Matrix"


@pytest.mark.asyncio
async def test_series_repository_create_and_search(session: AsyncSession) -> None:
    series_repo = SqlAlchemySeriesRepository()
    series = Series(
        id=uuid.uuid4(),
        title="Breaking Bad",
        overview="A chemistry teacher turns to crime.",
        first_air_date=date(2008, 1, 20),
        vote_average=9.5,
        tmdb_id=1396,
    )
    created = await series_repo.create(session, series)
    await session.commit()

    assert created.title == "Breaking Bad"

    results = await series_repo.search(session, "breaking")
    assert len(results) == 1
    assert results[0].title == "Breaking Bad"


@pytest.mark.asyncio
async def test_domain_entity_is_dataclass_not_orm(session: AsyncSession) -> None:
    """Verify that domain entities returned from repos are pure dataclasses,
    not SQLAlchemy ORM model instances."""
    movie_repo = SqlAlchemyMovieRepository()
    movie = Movie(
        id=uuid.uuid4(),
        title="Test Movie",
        tmdb_id=99999,
    )
    created = await movie_repo.create(session, movie)
    await session.commit()

    # Domain entities should be frozen dataclasses, not ORM models
    from kondooit.infrastructure.models import MovieModel
    assert not isinstance(created, MovieModel), "Repository returned an ORM model instead of a domain entity"
    assert hasattr(created, "__dataclass_fields__"), "Domain entity should be a dataclass"
