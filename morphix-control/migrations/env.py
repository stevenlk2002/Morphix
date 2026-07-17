"""Alembic environment for morphix-control.

Syncs migrations against the same SQLite database the app uses, resolved from
the MORPHIX_DB environment variable (default: data/morphix.db).
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.core.database import Base

# Import all models so their tables are registered on Base.metadata.
import app.models  # noqa: F401

config = context.config

# Inject the app's resolved database URL into the Alembic config so the
# migration engine and the running app point at the exact same SQLite file.
settings = get_settings()
config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.DB_PATH}")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite cannot ALTER TABLE ADD CONSTRAINT in a single statement; batch
        # mode rewrites the table so constraint changes apply correctly.
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
