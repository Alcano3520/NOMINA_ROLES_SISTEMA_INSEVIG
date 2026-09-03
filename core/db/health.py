"""Detección de disponibilidad de fuentes (ex `shared/detect_db.py`)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

FUENTE_SQLSERVER = "sqlserver"
FUENTE_SUPABASE = "supabase"
FUENTES_VALIDAS = (FUENTE_SQLSERVER, FUENTE_SUPABASE)


def sqlserver_disponible() -> bool:
    from core.db import sqlserver

    try:
        with sqlserver.conexion() as conn:
            conn.cursor().execute("SELECT 1").fetchone()
        return True
    except Exception as e:  # noqa: BLE001
        log.info("SQL Server no disponible: %s", e)
        return False


def supabase_disponible() -> bool:
    from core.db import supabase_client

    try:
        supabase_client.get_client().table("rpemplea").select("codemp").limit(1).execute()
        return True
    except Exception as e:  # noqa: BLE001
        log.info("Supabase no disponible: %s", e)
        return False


def fuente_recomendada() -> str:
    """`sqlserver` si responde; si no, `supabase`; si ninguno, `sqlserver`."""
    if sqlserver_disponible():
        return FUENTE_SQLSERVER
    if supabase_disponible():
        return FUENTE_SUPABASE
    log.warning("Ni SQL Server ni Supabase respondieron; se asume SQL Server.")
    return FUENTE_SQLSERVER
