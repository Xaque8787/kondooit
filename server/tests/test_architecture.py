"""Architectural boundary verification.

Verifies that the domain and application layers have zero imports of
infrastructure technologies. This is a structural test, not a runtime test.
"""

import ast
import pathlib

import pytest


DOMAIN_DIR = pathlib.Path("kondooit/domain")
APPLICATION_DIR = pathlib.Path("kondooit/application")

FORBIDDEN_PREFIXES = (
    "litestar",
    "sqlalchemy",
    "asyncpg",
    "iroh",
    "uvicorn",
    "httpx",
    "alembic",
    "bcrypt",
    "jwt",
    "pyjwt",
)


def _collect_imports(directory: pathlib.Path) -> list[tuple[str, str]]:
    """Return (file, module_name) for every import in the directory tree."""
    violations = []
    for py in directory.rglob("*.py"):
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    violations.append((str(py), alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module:
                violations.append((str(py), node.module))
    return violations


def test_domain_layer_has_no_infrastructure_imports() -> None:
    imports = _collect_imports(DOMAIN_DIR)
    violations = [
        (f, m) for f, m in imports
        if any(m.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)
    ]
    assert not violations, (
        f"Domain layer has forbidden infrastructure imports:\n"
        + "\n".join(f"  {f}: {m}" for f, m in violations)
    )


def test_application_layer_has_no_infrastructure_imports() -> None:
    imports = _collect_imports(APPLICATION_DIR)
    violations = [
        (f, m) for f, m in imports
        if any(m.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)
    ]
    assert not violations, (
        f"Application layer has forbidden infrastructure imports:\n"
        + "\n".join(f"  {f}: {m}" for f, m in violations)
    )


def test_domain_entities_are_not_sqlalchemy_models() -> None:
    """Verify domain entity classes do not inherit from SQLAlchemy bases."""
    from kondooit.domain.content import Movie, Series, Season, Episode, Genre, Collection
    from kondooit.domain.user import User

    domain_classes = [Movie, Series, Season, Episode, Genre, Collection, User]
    for cls in domain_classes:
        for base in cls.__mro__:
            assert "DeclarativeBase" not in base.__name__, (
                f"{cls.__name__} inherits from {base.__name__} — domain entities must not be SQLAlchemy models"
            )


def test_application_auth_service_does_not_import_security_infrastructure() -> None:
    """Verify the auth service depends on ports, not on bcrypt/jwt directly."""
    from kondooit.application.auth_service import AuthService
    import inspect

    source = inspect.getsource(AuthService)
    assert "bcrypt" not in source, "AuthService must not import bcrypt directly"
    assert "import jwt" not in source, "AuthService must not import jwt directly"
    assert "JwtTokenService" not in source, "AuthService must not reference infrastructure implementations"
    assert "BcryptPasswordHasher" not in source, "AuthService must not reference infrastructure implementations"
