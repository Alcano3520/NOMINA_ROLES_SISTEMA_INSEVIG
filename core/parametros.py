"""Parámetros de negocio editables desde Administración (guardados en AppConfig).

Hoy: SBU por año (para liquidaciones). Ampliable a proveedor de IA, plantilla de
correo, etc.
"""

from __future__ import annotations

import json

import sqlmodel

from core.db import appdb
from core.db.models import AppConfig


def _leer(key: str) -> dict:
    with appdb.session() as s:
        row = s.exec(
            sqlmodel.select(AppConfig).where(AppConfig.key == key, AppConfig.scope == "global")
        ).first()
    if not row:
        return {}
    try:
        return json.loads(row.value_json) or {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _guardar(key: str, data: dict) -> None:
    with appdb.session() as s:
        row = s.exec(
            sqlmodel.select(AppConfig).where(AppConfig.key == key, AppConfig.scope == "global")
        ).first()
        if row is None:
            row = AppConfig(key=key, scope="global")
        row.value_json = json.dumps(data)
        s.add(row)
        s.commit()


def get_sbu() -> dict[str, float]:
    """{'2026': 482.0, ...}. Si no hay nada guardado devuelve {} (se usan los
    valores por defecto de `core.repos.liquidaciones.SBU_DEFECTO`)."""
    d = _leer("sbu_por_anio")
    return {str(k): float(v) for k, v in d.items() if str(v).replace(".", "", 1).isdigit()}


def set_sbu(sbu: dict[str, float]) -> None:
    _guardar("sbu_por_anio", {str(k): float(v) for k, v in sbu.items()})


def config_liquidacion(region: str = "COSTA"):
    """`ConfigLiquidacion` con los SBU guardados (o los por defecto)."""
    from core.repos.liquidaciones import SBU_DEFECTO, ConfigLiquidacion

    sbu = dict(SBU_DEFECTO)
    sbu.update(get_sbu())
    return ConfigLiquidacion(region=region, sbu_por_anio=sbu)
