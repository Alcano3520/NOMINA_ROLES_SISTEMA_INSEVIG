"""Post-procesado común de nómina (antes duplicado en `shared/obtener_datos.py`).

Consolidación de conceptos por CLASE, regla ASENTADO para décimos, cálculo de
DIAS desde la CLASE 101, totales de ingresos/egresos y traducción de catálogos.
"""

from __future__ import annotations

from core.concepts import (
    CAMPOS_EGRESO,
    CAMPOS_INGRESO,
    CLASE_DIAS,
    CLASES_IGNORADAS,
    CONCEPTOS_CONDICIONADOS_ASENTADO,
    concepto_de_clase,
)
from core.datos.port import DatosCrudos, EmpleadoNomina
from core.utils import a_float, a_int, normalizar_cedula

DIAS_DEFAULT = 30.0


def consolidar_conceptos(movimientos: list[dict]) -> dict[str, float]:
    """Suma los valores por concepto. Ignora `CLASES_IGNORADAS`; para
    DECIMO_TERCERA/CUARTA solo suma los movimientos con ``asentado`` verdadero."""
    conceptos: dict[str, float] = {}
    for row in movimientos:
        clase = a_int(row.get("clase"))
        if clase in CLASES_IGNORADAS:
            continue
        concepto = concepto_de_clase(clase)
        if concepto in CONCEPTOS_CONDICIONADOS_ASENTADO and not row.get("asentado"):
            continue
        conceptos[concepto] = conceptos.get(concepto, 0.0) + a_float(row.get("valor"))
    return conceptos


def dias_del_periodo(movimientos: list[dict], default: float = DIAS_DEFAULT) -> float:
    """DIAS tomados de la fila CLASE 101 del período (30 si no existe).

    Nota: unifica el comportamiento divergente del legado — la versión SQL Server
    solo consultaba DIAS si había SUELDO y con una query aparte sin filtro de
    período; la de Supabase usaba la fila 101 ya traída. Nos quedamos con esta
    última (en-período), más correcta.
    """
    for row in movimientos:
        if a_int(row.get("clase")) == CLASE_DIAS:
            d = row.get("dias")
            return a_float(d, default) if d is not None else default
    return default


def construir_empleado_nomina(crudos: DatosCrudos) -> EmpleadoNomina:
    conceptos = consolidar_conceptos(crudos.movimientos)
    ingresos = round(sum(conceptos.get(k, 0.0) for k in CAMPOS_INGRESO), 2)
    egresos = round(sum(conceptos.get(k, 0.0) for k in CAMPOS_EGRESO), 2)
    cargo_cod = str(crudos.cargo_codigo).strip()
    depto_cod = str(crudos.depto_codigo).strip()
    return EmpleadoNomina(
        empleado=str(crudos.empleado).strip(),
        apellidos_nombres=f"{crudos.apellidos} {crudos.nombres}".strip(),
        cedula=normalizar_cedula(crudos.cedula),
        cargo=crudos.catalogo_cargos.get(cargo_cod, cargo_cod),
        depto=crudos.catalogo_deptos.get(depto_cod, depto_cod),
        dias=dias_del_periodo(crudos.movimientos),
        total_ingresos=ingresos,
        total_egresos=egresos,
        total_recibir=round(ingresos - egresos, 2),
        conceptos=conceptos,
    )
