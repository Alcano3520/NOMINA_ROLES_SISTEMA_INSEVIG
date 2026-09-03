"""Registro de egresos/ingresos en RPINGDES. Alcance acotado (plan Fase 5):
import BIESS quirografarios + alta manual + posteo auditado con dry-run y dedupe.

Porta lo esencial de `registrdor_vizulizador_egresosingresos/REGISTRAR_PRESTAMOS_UNIFICADO.pyw`.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.audit.writer import audit_scope
from core.config import get_settings
from core.db import sqlserver
from core.utils import normalizar_cedula

CLASE_QUIROGRAFARIO = 204


@dataclass
class Movimiento:
    empleado: str
    clase: int
    valor: float
    concepto: str
    periodo: str  # YYYY-MM
    estado_biess: str = ""  # activo | liquidado | no_encontrado


def _empleado_por_cedula(cedula: str) -> dict | None:
    flt = get_settings().sqlserver_filter
    filas = sqlserver.filas(
        f"""SELECT [EMPLEADO],[APELLIDOS],[NOMBRES],[ESTADO]
            FROM [insevig].[dbo].[RPEMPLEA]
            WHERE {flt} AND CAST([CEDULA] AS BIGINT) = ?""",
        (int(cedula),),
    )
    return filas[0] if filas else None


def preparar_biess(filas: list[dict], periodo: str) -> tuple[list[Movimiento], list[str]]:
    """`filas`: [{'cedula','valor'}]. Empareja con RPEMPLEA y clasifica.
    Devuelve (movimientos_listos, avisos)."""
    movs: list[Movimiento] = []
    avisos: list[str] = []
    for f in filas:
        ced = normalizar_cedula(f["cedula"])
        emp = _empleado_por_cedula(ced)
        if emp is None:
            movs.append(
                Movimiento("", CLASE_QUIROGRAFARIO, f["valor"], "BIESS QUIROGRAFARIO", periodo, "no_encontrado")
            )
            avisos.append(f"Cédula {ced}: sin empleado en RPEMPLEA.")
            continue
        estado = "activo" if (emp.get("ESTADO") or "").strip() == "ACT" else "liquidado"
        movs.append(
            Movimiento(
                str(emp["EMPLEADO"]).strip(),
                CLASE_QUIROGRAFARIO,
                round(float(f["valor"]), 2),
                "BIESS QUIROGRAFARIO",
                periodo,
                estado,
            )
        )
    return movs, avisos


def _ya_existe(cur, empleado: str, clase: int, valor: float, ini: str, fin: str) -> bool:
    flt = get_settings().sqlserver_filter
    cur.execute(
        f"""SELECT COUNT(*) FROM [insevig].[dbo].[RPINGDES]
            WHERE {flt} AND [EMPLEADO] = ? AND [CLASE] = ? AND ABS([VALOR] - ?) < 0.01
              AND [FECHA_VEN] >= ? AND [FECHA_VEN] < ?""",
        (empleado, clase, valor, ini, fin),
    )
    return cur.fetchone()[0] > 0


def postear(
    movimientos: list[Movimiento],
    *,
    usuario: str,
    roles: set[str],
    dry_run: bool = True,
) -> dict:
    """Inserta en RPINGDES los movimientos con empleado. `dry_run=True` solo cuenta.
    Devuelve {'insertados','omitidos_dedupe','sin_empleado'}."""
    validos = [m for m in movimientos if m.empleado]
    sin_empleado = len(movimientos) - len(validos)
    if not validos:
        return {"insertados": 0, "omitidos_dedupe": 0, "sin_empleado": sin_empleado}

    anio, mes = validos[0].periodo.split("-")
    ini = f"{anio}-{int(mes):02d}-01"
    fin = f"{int(anio) + 1}-01-01" if int(mes) == 12 else f"{anio}-{int(mes) + 1:02d}-01"
    fecha_ven = f"{anio}-{int(mes):02d}-28"
    insertados = omitidos = 0

    if dry_run:
        with sqlserver.conexion() as conn:
            cur = conn.cursor()
            for m in validos:
                if _ya_existe(cur, m.empleado, m.clase, m.valor, ini, fin):
                    omitidos += 1
                else:
                    insertados += 1
        return {"insertados": insertados, "omitidos_dedupe": omitidos, "sin_empleado": sin_empleado}

    with audit_scope(
        "registrador", "registrar_rpingdes", usuario=usuario, roles=roles,
        target_table="RPINGDES", target_key=validos[0].periodo,
        after={"n": len(validos), "clase": validos[0].clase},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        for m in validos:
            if _ya_existe(cur, m.empleado, m.clase, m.valor, ini, fin):
                omitidos += 1
                continue
            cur.execute(
                """INSERT INTO [insevig].[dbo].[RPINGDES]
                   ([EMPLEADO],[CODEMP],[CODSUC],[CLASE],[VALOR],[CONCEPTO],[FECHA_VEN],[ASENTADO])
                   VALUES (?, '10', '10', ?, ?, ?, ?, 0)""",
                (m.empleado, m.clase, m.valor, m.concepto, fecha_ven),
            )
            insertados += 1
        conn.commit()
    return {"insertados": insertados, "omitidos_dedupe": omitidos, "sin_empleado": sin_empleado}
