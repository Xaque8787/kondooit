"""Baseline: the schema as created from the ORM models at startup.

Tables are created by kondooit.infrastructure.schema from the models, not
by migrations. Later revisions only alter existing tables and must check
current state first, so they are no-ops on a freshly created database.

Revision ID: 0001
Revises:
Create Date: 2026-10-07
"""
from __future__ import annotations

from typing import Sequence, Union

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
