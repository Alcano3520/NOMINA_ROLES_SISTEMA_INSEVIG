"""Valores monetarios por tipo de sanción (para la hoja "Detalle Resumen" del
Excel). En el legado vivían en SQLite `valores_sanciones`; acá van en `AppConfig`
(clave `valores_sanciones`), editables desde la página de sanciones (rol admin).
"""

from __future__ import annotations

import json

import sqlmodel

from core.db import appdb
from core.db.models import AppConfig

_KEY = "valores_sanciones"

# Defaults del legado (`local_db.inicializar_db`).
DEFAULTS: dict[str, float] = {
    "FALTA": 1, "PERMISO": 1,
    "HORAS EXTRAS (FACTOR/HORA)": 2.5, "HORAS EXTRAS 12H (FIJO)": 30,
    "FRANCO TRABAJADO 8H": 25, "FRANCO TRABAJADO 12H": 37.5,
    "ATRASO": 16, "DORMIDO": 35, "MALA URBANIDAD": 30,
    "FALTA DE RESPETO": 30, "MAL UNIFORMADO": 30,
    "ABANDONO DE PUESTO": 40, "MAL SERVICIO DE GUARDIA": 30,
    "INCUMPLIMIENTO DE POLITICAS": 30, "MAL USO DEL EQUIPO DE DOTACION": 30,
}


def get_valores() -> dict[str, float]:
    """`{tipo_sancion: valor}` — defaults + lo guardado en AppConfig."""
    with appdb.session() as s:
        row = s.exec(
            sqlmodel.select(AppConfig).where(AppConfig.key == _KEY, AppConfig.scope == "global")
        ).first()
    out = dict(DEFAULTS)
    if row:
        try:
            for k, v in (json.loads(row.value_json) or {}).items():
                out[str(k).strip().upper()] = float(v)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return out


def set_valor(tipo_sancion: str, valor: float) -> None:
    with appdb.session() as s:
        row = s.exec(
            sqlmodel.select(AppConfig).where(AppConfig.key == _KEY, AppConfig.scope == "global")
        ).first()
        data: dict[str, float] = {}
        if row:
            try:
                data = json.loads(row.value_json) or {}
            except (json.JSONDecodeError, TypeError):
                data = {}
        else:
            row = AppConfig(key=_KEY, scope="global")
        data[str(tipo_sancion).strip().upper()] = float(valor)
        row.value_json = json.dumps(data)
        s.add(row)
        s.commit()
