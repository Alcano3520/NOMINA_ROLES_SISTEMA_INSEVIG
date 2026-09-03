"""Entorno de Alembic para la BD de la app (SQLModel)."""

from __future__ import annotations

from logging.config import fileConfig

from sqlmodel import SQLModel

from alembic import context
from core.config import get_settings
from core.db import models  # noqa: F401  registra las tablas en SQLModel.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().app_db_url)
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from core.db.appdb import get_engine

    with get_engine().connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
