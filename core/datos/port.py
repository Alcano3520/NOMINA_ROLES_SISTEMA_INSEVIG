"""Contratos de la capa de datos: DatosCrudos (entrada) y EmpleadoNomina (salida)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd


@dataclass(slots=True)
class DatosCrudos:
    """Datos sin procesar de un empleado + sus movimientos de un período.

    Lo que devuelve cada fuente (SQL Server / Supabase) tras normalizar nombres
    de campo. El post-procesado (consolidación de conceptos, totales, DIAS,
    traducción de catálogos) es común y no depende de la fuente.
    """

    empleado: str
    apellidos: str
    nombres: str
    cedula: object
    cargo_codigo: str
    depto_codigo: str
    # cada movimiento: {"clase": int, "valor": float, "asentado": bool, "dias": float | None}
    movimientos: list[dict]
    catalogo_cargos: dict[str, str]  # código -> nombre (DBTABLAS TIPO='FNC')
    catalogo_deptos: dict[str, str]  # código -> nombre (DBTABLAS TIPO='DPT')


@dataclass(slots=True)
class EmpleadoNomina:
    """Resultado consolidado. Misma forma que la `pandas.Series` de `ObtenerDatos`.

    `conceptos` se aplana al nivel superior en `to_dict()` / `to_series()` para
    mantener compatibilidad con los consumidores actuales (roles/, reportes/).
    """

    empleado: str
    apellidos_nombres: str
    cedula: str
    cargo: str
    depto: str
    dias: float
    total_ingresos: float
    total_egresos: float
    total_recibir: float
    conceptos: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        base: dict[str, object] = {
            "EMPLEADO": self.empleado,
            "APELLIDOS_NOMBRES": self.apellidos_nombres,
            "CEDULA": self.cedula,
            "CARGO": self.cargo,
            "DEPTO": self.depto,
            "DIAS": self.dias,
            "TOTAL_INGRESOS": self.total_ingresos,
            "TOTAL_EGRESOS": self.total_egresos,
            "TOTAL_RECIBIR": self.total_recibir,
        }
        base.update(self.conceptos)
        return base

    def to_series(self) -> pd.Series:
        return pd.Series(self.to_dict())


class FuenteDatos(Protocol):
    """Una fuente sabe traer los datos crudos de un empleado para un período."""

    def fetch_empleado(self, periodo: str, cedula_o_nombre: str) -> DatosCrudos | None:
        ...
