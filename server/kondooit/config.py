"""Application configuration.

All configuration is sourced from environment variables. The domain and
application layers receive configuration through typed settings objects
or constructor injection — they never read environment variables directly.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="KONDOOIT_",
        env_file=".env",
        extra="ignore",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://kondooit:kondooit@localhost:5432/kondooit"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 1440

    # iroh — optional, server operates without it
    iroh_enabled: bool = False
    iroh_data_dir: str = "/data/iroh"
    iroh_binary_path: str = "/usr/local/bin/kondooit-iroh"
    iroh_control_socket: str = "/tmp/kondooit-iroh.sock"
    iroh_target_port: int = 8000
    runtime_base_url: str = "https://xaque8787.github.io/kondooit/runtime/"


def get_settings() -> Settings:
    """Return a Settings instance. Can be overridden in tests."""
    return Settings()
