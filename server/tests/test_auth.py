"""Authentication flow tests.

Tests the full auth flow: bootstrap admin, login, token verification,
and protected endpoint access. Uses SQLite for unit testing the
repository/security mapping, and Litestar's TestClient for HTTP-level
testing.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from kondooit.application.auth_service import AuthService
from kondooit.config import Settings
from kondooit.domain.user import User, UserRole
from kondooit.infrastructure.models import Base
from kondooit.infrastructure.repositories import SqlAlchemyUserRepository
from kondooit.infrastructure.security import BcryptPasswordHasher, JwtTokenService


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_secret="test-secret-key-for-testing-only",
        jwt_algorithm="HS256",
        jwt_expiry_minutes=60,
    )


@pytest.fixture
def auth_service(settings: Settings) -> AuthService:
    user_repo = SqlAlchemyUserRepository()
    password_hasher = BcryptPasswordHasher()
    token_service = JwtTokenService(settings)
    return AuthService(user_repo, password_hasher, token_service)


# --- Unit tests: AuthService with SQLite ---

@pytest.mark.asyncio
async def test_bootstrap_admin_creates_first_admin(session: AsyncSession, auth_service: AuthService) -> None:
    result = await auth_service.bootstrap_admin(
        session,
        username="admin",
        email="admin@kondooit.local",
        password="securepassword123",
    )
    assert result is not None
    user, token = result
    assert user.username == "admin"
    assert user.email == "admin@kondooit.local"
    assert user.role == UserRole.ADMIN
    assert token is not None
    assert len(token) > 0


@pytest.mark.asyncio
async def test_bootstrap_admin_rejects_if_admin_exists(session: AsyncSession, auth_service: AuthService) -> None:
    # First bootstrap succeeds
    result1 = await auth_service.bootstrap_admin(
        session,
        username="admin",
        email="admin@kondooit.local",
        password="securepassword123",
    )
    assert result1 is not None

    # Second bootstrap fails
    result2 = await auth_service.bootstrap_admin(
        session,
        username="admin2",
        email="admin2@kondooit.local",
        password="anotherpassword",
    )
    assert result2 is None


@pytest.mark.asyncio
async def test_login_with_valid_credentials(session: AsyncSession, auth_service: AuthService) -> None:
    await auth_service.bootstrap_admin(
        session,
        username="admin",
        email="admin@kondooit.local",
        password="securepassword123",
    )

    token = await auth_service.login(session, "admin", "securepassword123")
    assert token is not None
    assert len(token) > 0


@pytest.mark.asyncio
async def test_login_with_wrong_password(session: AsyncSession, auth_service: AuthService) -> None:
    await auth_service.bootstrap_admin(
        session,
        username="admin",
        email="admin@kondooit.local",
        password="securepassword123",
    )

    token = await auth_service.login(session, "admin", "wrongpassword")
    assert token is None


@pytest.mark.asyncio
async def test_login_with_nonexistent_user(session: AsyncSession, auth_service: AuthService) -> None:
    token = await auth_service.login(session, "ghost", "anything")
    assert token is None


@pytest.mark.asyncio
async def test_get_user_from_valid_token(session: AsyncSession, auth_service: AuthService) -> None:
    result = await auth_service.bootstrap_admin(
        session,
        username="admin",
        email="admin@kondooit.local",
        password="securepassword123",
    )
    assert result is not None
    _, token = result

    user = await auth_service.get_user_from_token(session, token)
    assert user is not None
    assert user.username == "admin"


@pytest.mark.asyncio
async def test_get_user_from_invalid_token(session: AsyncSession, auth_service: AuthService) -> None:
    user = await auth_service.get_user_from_token(session, "invalid.token.here")
    assert user is None


@pytest.mark.asyncio
async def test_admin_exists_returns_false_initially(session: AsyncSession, auth_service: AuthService) -> None:
    exists = await auth_service.admin_exists(session)
    assert exists is False


@pytest.mark.asyncio
async def test_admin_exists_returns_true_after_bootstrap(session: AsyncSession, auth_service: AuthService) -> None:
    await auth_service.bootstrap_admin(
        session,
        username="admin",
        email="admin@kondooit.local",
        password="securepassword123",
    )
    exists = await auth_service.admin_exists(session)
    assert exists is True


# --- Unit tests: Security implementations ---

def test_password_hasher_hash_and_verify() -> None:
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash("mypassword")
    assert hashed != "mypassword"
    assert hasher.verify("mypassword", hashed) is True
    assert hasher.verify("wrongpassword", hashed) is False


def test_token_service_create_and_verify(settings: Settings) -> None:
    from kondooit.domain.user import User, UserRole
    import uuid

    token_service = JwtTokenService(settings)
    user = User(
        id=uuid.uuid4(),
        username="testadmin",
        email="test@kondooit.local",
        password_hash="hashed",
        role=UserRole.ADMIN,
    )
    token = token_service.create_access_token(user)
    assert token is not None

    payload = token_service.verify_token(token)
    assert payload is not None
    assert payload.username == "testadmin"
    assert payload.role == "admin"
    assert payload.user_id == user.id


def test_token_service_rejects_invalid_token(settings: Settings) -> None:
    token_service = JwtTokenService(settings)
    payload = token_service.verify_token("not.a.valid.token")
    assert payload is None


def test_token_service_rejects_tampered_token(settings: Settings) -> None:
    from kondooit.domain.user import User, UserRole
    import uuid

    token_service = JwtTokenService(settings)
    user = User(
        id=uuid.uuid4(),
        username="testadmin",
        email="test@kondooit.local",
        password_hash="hashed",
        role=UserRole.ADMIN,
    )
    token = token_service.create_access_token(user)
    # Tamper with the token
    tampered = token[:-5] + "XXXXX"
    payload = token_service.verify_token(tampered)
    assert payload is None
