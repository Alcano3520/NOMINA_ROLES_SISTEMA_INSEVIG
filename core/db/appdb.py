"""Motor y sesiones de la BD propia de la app (Postgres en prod, SQLite en dev).

NO es SQL Server ni Supabase. Aquí viven: usuarios/roles, auditoría, jobs,
config e historial de préstamos migrado.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from core.config import get_settings


@lru_cache
def get_engine():
    url = get_settings().app_db_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    if url.startswith("sqlite:///") and "/" in url[10:]:
        Path(url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, echo=False, connect_args=connect_args)


def crear_tablas() -> None:
    """Crea las tablas que falten (dev / primer arranque). En prod: alembic.

    El llamador debe haber importado antes el módulo de modelos para que estén
    registrados en `SQLModel.metadata`.
    """
    SQLModel.metadata.create_all(get_engine())


@contextlib.contextmanager
def session() -> Iterator[Session]:
    with Session(get_engine()) as s:
        yield s
