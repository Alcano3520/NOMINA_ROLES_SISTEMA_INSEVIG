"""Fachada de la capa de datos. Reemplaza a `ObtenerDatos`.

    from core.datos.service import datos_empleado
    emp = datos_empleado("2026-06", "1712345678", fuente="sqlserver")
    if emp:
        serie = emp.to_series()   # compatible con roles/ y reportes/
"""

from __future__ import annotations

from typing import Any

from core.datos import fuente_sqlserver, fuente_supabase
from core.datos.port import EmpleadoNomina
from core.datos.postproceso import construir_empleado_nomina
from core.db.health import FUENTE_SQLSERVER, FUENTE_SUPABASE, FUENTES_VALIDAS

_FUENTES: dict[str, Any] = {
    FUENTE_SQLSERVER: fuente_sqlserver,
    FUENTE_SUPABASE: fuente_supabase,
}


def datos_empleado(
    periodo: str,
    cedula_o_nombre: str,
    fuente: str = FUENTE_SQLSERVER,
    *,
    _fuentes: dict[str, Any] | None = None,
) -> EmpleadoNomina | None:
    """Datos consolidados de un empleado para un período (`YYYY-MM`).

    `fuente` ∈ {"sqlserver", "supabase"}. Devuelve `None` si no se encuentra.
    `_fuentes` es un punto de inyección para tests.
    """
    fuentes = _fuentes or _FUENTES
    if fuente not in fuentes:
        raise ValueError(
            f"Fuente desconocida: {fuente!r}. Válidas: {sorted(FUENTES_VALIDAS)}"
        )
    crudos = fuentes[fuente].fetch_empleado(periodo, cedula_o_nombre)
    return construir_empleado_nomina(crudos) if crudos is not None else None
