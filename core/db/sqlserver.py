"""Conexión a SQL Server con fallback de drivers ODBC.

Reemplaza los ~20 helpers `_get_sql_conn` / `get_sql_conn` copiados en los .pyw
y las credenciales hardcodeadas de `shared/obtener_datos.py` / `shared/detect_db.py`.

- `conexion()` — context manager de una conexión pyodbc (operaciones puntuales).
- `filas()` — SELECT → list[dict].
- `get_engine()` — Engine SQLAlchemy con pool (para reportes sobre RPHISTOR ~2.5M).

NOTA (despliegue, ver plan §4a): el hack `OPENSSL_CONF=openssl_legacy.cnf` NO se
porta — el TLS 1.0 de SQL Server 2008 R2 se resuelve a nivel Windows Server
(parchear la BD con SP3+KB3144114, o reactivar SCHANNEL TLS 1.0 Client).
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from functools import lru_cache
from typing import TYPE_CHECKING

from core.config import get_settings

if TYPE_CHECKING:
    import pyodbc

log = logging.getLogger(__name__)

_driver_activo: str | None = None


class SqlServerNoDisponible(RuntimeError):
    """Ningún driver ODBC logró conectar."""


def _connect(*, write: bool = False) -> pyodbc.Connection:
    global _driver_activo
    import pyodbc

    s = get_settings()
    candidatos = (
        [_driver_activo, *s.driver_list] if _driver_activo else list(s.driver_list)
    )
    errores: list[str] = []
    for driver in dict.fromkeys(candidatos):  # únicos, preservando orden
        try:
            conn = pyodbc.connect(
                s.sqlserver_dsn(driver=driver, write=write), timeout=s.sqlserver_timeout
            )
            _driver_activo = driver
            return conn
        except pyodbc.Error as e:  # noqa: PERF203
            errores.append(f"{driver}: {e}")
    raise SqlServerNoDisponible(
        "No se pudo conectar a SQL Server con ningún driver ODBC:\n  "
        + "\n  ".join(errores)
    )


@contextlib.contextmanager
def conexion(*, write: bool = False) -> Iterator[pyodbc.Connection]:
    """Context manager que abre y cierra una conexión.

    `write=True` usa el login de escritura (`insevig_rw`); por defecto, el de
    solo lectura (`insevig_ro`, con `ApplicationIntent=ReadOnly`).
    """
    conn = _connect(write=write)
    try:
        yield conn
    finally:
        with contextlib.suppress(Exception):
            conn.close()


def filas(query: str, params: tuple = ()) -> list[dict]:
    """Ejecuta un SELECT y devuelve filas como dicts (claves = nombres de columna)."""
    with conexion() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def driver_activo() -> str:
    """Driver ODBC que funciona (lo detecta con una conexión de prueba)."""
    global _driver_activo
    if _driver_activo is None:
        _connect().close()
    assert _driver_activo is not None
    return _driver_activo


@lru_cache
def get_engine(write: bool = False):
    """Engine SQLAlchemy con pool acotado — para lecturas grandes (reportes)."""
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL

    s = get_settings()
    url = URL.create(
        "mssql+pyodbc",
        query={"odbc_connect": s.sqlserver_dsn(driver=driver_activo(), write=write)},
    )
    return create_engine(
        url,
        pool_size=s.sqlserver_pool_size,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
