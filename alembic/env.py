"""Alembic migration environment.

DATABASE_URL is loaded from app config (.env). All SQLAlchemy models must be
imported via app.modules so autogenerate can detect schema changes.
"""

from __future__ import annotations

import sys

if sys.version_info < (3, 10):
    import eval_type_backport  # noqa: F401 — PEP 604 unions on Python 3.9

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

import app.modules  # noqa: F401 — register all models on Base.metadata
from app.core.config import settings
from app.core.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ConfigParser treats % as interpolation; escape for passwords/query params.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
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
        if connection.dialect.name == "mysql":
            connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            # Default alembic_version.version_num is VARCHAR(32); several
            # revision ids exceed that (e.g. i6d7e8f9a0b1_rate_plan_inclusions).
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS alembic_version ("
                    "version_num VARCHAR(128) NOT NULL, "
                    "PRIMARY KEY (version_num))"
                )
            )
            connection.execute(
                text("ALTER TABLE alembic_version MODIFY version_num VARCHAR(128) NOT NULL")
            )
            connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

        if connection.dialect.name == "mysql":
            connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
