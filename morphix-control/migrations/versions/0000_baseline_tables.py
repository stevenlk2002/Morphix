"""baseline: create all tables from ORM metadata

Revision ID: 0000_baseline_tables
Revises:
Create Date: 2026-07-17 23:35:00.000000

This is the first migration. It lets Alembic own the database schema: all
tables (and the CHECK constraints declared on the ORM models, e.g.
`ck_session_runtime_session_state` / `ck_session_runtime_hosting_status`) are
created here via `Base.metadata.create_all`.

Subsequent migrations layer additional constraints/columns on top of this
baseline. Application startup no longer calls `create_all`; the schema is
managed exclusively by `alembic upgrade head`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.database import Base
import app.models  # noqa: F401  (register all ORM tables on Base.metadata)


revision: str = "0000_baseline_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Bind the metadata to the migration connection and create every table
    # exactly as the ORM models declare them.
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
