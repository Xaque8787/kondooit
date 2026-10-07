"""Database schema initialization, run once at server startup.

The ORM models are the complete definition of the schema. Startup creates
any missing tables from them, then either records a new database as current
(no migration history yet) or applies pending Alembic revisions. Revisions
only alter tables that already exist and must check current state first.
Everything runs in one transaction; any failure aborts startup.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from kondooit.infrastructure import profile_repo, user_state_repo, watch_progress_repo  # noqa: F401
from kondooit.infrastructure.models import Base

logger = logging.getLogger(__name__)

metadata = Base.metadata

_ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"


def _alembic_config(connection: Connection) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    cfg.attributes["connection"] = connection
    return cfg


def _initialize(connection: Connection) -> None:
    metadata.create_all(connection)
    cfg = _alembic_config(connection)
    current = MigrationContext.configure(connection).get_current_revision()
    if current is None:
        command.stamp(cfg, "head")
        logger.info("Database schema created and recorded at the latest revision")
    else:
        command.upgrade(cfg, "head")
        logger.info("Database schema up to date (was at revision %s)", current)


async def initialize_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(_initialize)
