"""Consulta de préstamos (CLASE 205). Solo lectura.

Porta `prestamos/HISTORIAL_PRESTAMOS_10.pyw`. Combina:
  - SQL Server RPINGDES (vivo) / RPHISTOR (cerrado), CLASE 205
  - LoanHistoryMigrated (Postgres app) — lo que antes vivía en el SQLite sobre SMB

Cero acceso a SMB / SQLite en runtime.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlmodel

from core.config import get_settings
from core.db import appdb, sqlserver, supabase_client
from core.db.health import FUENTE_SUPABASE
from core.db.models import LoanHistoryMigrated
from core.utils import a_float, normalizar_cedula

CLASE_PRESTAMO = 205

# NUMERO de RPHISTOR ya migrados al SQLite (herencia de obtener_numeros_excluir()).
_NUMEROS_MIGRADOS = frozenset({
    "27958", "28215", "28592", "29301", "29633", "29790", "30062", "30437",
    "30691", "30928", "31777", "32211", "32721", "33089", "33634", "33944",
    "33964", "34483", "34492", "34797", "35168", "35616", "35923",
})


@dataclass
class SaldoPrestamo:
    empleado: str
    apellidos_nombres: str
    cedula: str
    saldo: float


@dataclass
class MovimientoPrestamo:
    fecha: str
    valor: float
    concepto: str
    numero: str
    origen: str  # RPINGDES | RPHISTOR | MIGRADO
    es_cuadre: bool = False


# ── Saldos (todos los empleados) ─────────────────────────────────────────────


def saldos(fuente: str) -> list[SaldoPrestamo]:
    if fuente == FUENTE_SUPABASE:
        return _saldos_supabase()
    return _saldos_sqlserver()


def _saldos_sqlserver() -> list[SaldoPrestamo]:
    flt = get_settings().sqlserver_filter
    filas = sqlserver.filas(
        f"""SELECT i.EMPLEADO,
                   RTRIM(e.APELLIDOS) + ' ' + RTRIM(e.NOMBRES) AS NOMBRE,
                   e.CEDULA,
                   ISNULL(SUM(i.VALOR), 0) AS SALDO
            FROM [insevig].[dbo].[RPINGDES] i
            LEFT JOIN [insevig].[dbo].[RPEMPLEA] e ON e.EMPLEADO = i.EMPLEADO
            WHERE i.CLASE = {CLASE_PRESTAMO} AND {flt.replace('CODEMP', 'i.CODEMP').replace('CODSUC', 'i.CODSUC')}
            GROUP BY i.EMPLEADO, RTRIM(e.APELLIDOS) + ' ' + RTRIM(e.NOMBRES), e.CEDULA
            HAVING ISNULL(SUM(i.VALOR), 0) <> 0
            ORDER BY SALDO DESC"""
    )
    return [
        SaldoPrestamo(
            empleado=str(r["EMPLEADO"]).strip(),
            apellidos_nombres=(r.get("NOMBRE") or "").strip(),
            cedula=normalizar_cedula(r.get("CEDULA")),
            saldo=round(a_float(r.get("SALDO")), 2),
        )
        for r in filas
    ]


def _saldos_supabase() -> list[SaldoPrestamo]:
    sb = supabase_client.get_client()
    r = (
        sb.table("rpingdesres")
        .select("empleado,valor")
        .eq("codemp", "10")
        .eq("clase", CLASE_PRESTAMO)
        .execute()
    )
    por_emp: dict[str, float] = {}
    for row in r.data or []:
        cod = str(row["empleado"]).strip()
        por_emp[cod] = por_emp.get(cod, 0.0) + a_float(row.get("valor"))
    emps = {
        str(x["empleado"]).strip(): x
        for x in (
            sb.table("rpemplea").select("empleado,apellidos,nombres,cedula").eq("codemp", "10").execute().data
            or []
        )
    }
    out = []
    for cod, saldo in por_emp.items():
        if round(saldo, 2) == 0:
            continue
        e = emps.get(cod, {})
        nombre = f"{(e.get('apellidos') or '').strip()} {(e.get('nombres') or '').strip()}".strip()
        out.append(SaldoPrestamo(cod, nombre, normalizar_cedula(e.get("cedula")), round(saldo, 2)))
    out.sort(key=lambda s: s.saldo, reverse=True)
    return out


# ── Historial de un empleado ─────────────────────────────────────────────────


def historial_empleado(codigo: str, fuente: str) -> list[MovimientoPrestamo]:
    movs: list[MovimientoPrestamo] = list(_historial_migrado(codigo))
    if fuente == FUENTE_SUPABASE:
        movs += _historial_supabase(codigo)
    else:
        movs += _historial_sqlserver(codigo)
    movs.sort(key=lambda m: m.fecha)
    return movs


def _historial_migrado(codigo: str) -> list[MovimientoPrestamo]:
    with appdb.session() as s:
        filas = s.exec(
            sqlmodel.select(LoanHistoryMigrated).where(LoanHistoryMigrated.empleado == str(codigo))
        ).all()
    out = []
    for f in filas:
        valor = f.ingreso if f.ingreso else -f.egreso
        out.append(
            MovimientoPrestamo(
                fecha=f.fecha,
                valor=round(valor, 2),
                concepto=f.concepto or "",
                numero=f"MIG_{f.numero_fila}",
                origen="MIGRADO",
                es_cuadre=f.tipo in ("CUADRE", "CRUZE"),
            )
        )
    return out


def _historial_sqlserver(codigo: str) -> list[MovimientoPrestamo]:
    flt = get_settings().sqlserver_filter
    out: list[MovimientoPrestamo] = []
    for tabla, origen in (("RPINGDES", "RPINGDES"), ("RPHISTOR", "RPHISTOR")):
        filas = sqlserver.filas(
            f"""SELECT [NUMERO],[FECHA],[VALOR],[CONCEPTO],[OBSERV]
                FROM [insevig].[dbo].[{tabla}]
                WHERE {flt} AND [EMPLEADO] = ? AND [CLASE] = {CLASE_PRESTAMO}
                ORDER BY [NUMERO], [FECHA]""",
            (str(codigo),),
        )
        for r in filas:
            num = str(r.get("NUMERO") or "").strip()
            if origen == "RPHISTOR" and num in _NUMEROS_MIGRADOS:
                continue
            fecha = str(r.get("FECHA") or "")[:10]
            out.append(
                MovimientoPrestamo(
                    fecha=fecha,
                    valor=round(a_float(r.get("VALOR")), 2),
                    concepto=(r.get("CONCEPTO") or r.get("OBSERV") or "").strip(),
                    numero=num,
                    origen=origen,
                )
            )
    return out


def _historial_supabase(codigo: str) -> list[MovimientoPrestamo]:
    sb = supabase_client.get_client()
    out: list[MovimientoPrestamo] = []
    for tabla, origen in (("rpingdesres", "RPINGDES"), ("rphistor_temp", "RPHISTOR")):
        r = (
            sb.table(tabla)
            .select("numero,fecha,valor,concepto,observ")
            .eq("codemp", "10")
            .eq("empleado", str(codigo))
            .eq("clase", CLASE_PRESTAMO)
            .execute()
        )
        for row in r.data or []:
            num = str(row.get("numero") or "").strip()
            if origen == "RPHISTOR" and num in _NUMEROS_MIGRADOS:
                continue
            out.append(
                MovimientoPrestamo(
                    fecha=str(row.get("fecha") or "")[:10],
                    valor=round(a_float(row.get("valor")), 2),
                    concepto=(row.get("concepto") or row.get("observ") or "").strip(),
                    numero=num,
                    origen=origen,
                )
            )
    return out


def saldo_total(codigo: str, fuente: str) -> float:
    return round(sum(m.valor for m in historial_empleado(codigo, fuente)), 2)


@dataclass
class ResumenPrestamo:
    numero: str
    desde: str
    hasta: str
    prestado: float       # suma de ingresos (VALOR > 0)
    abonado: float        # suma de |egresos| (VALOR < 0)
    saldo: float
    cuotas: int
    cuota_promedio: float = 0.0
    meses_brecha: int = 0          # meses sin descuento entre la primera y última cuota
    cancelado: bool = False
    meses_para_cancelar: int = 0   # estimación: saldo / cuota_promedio
    estado: str = ""              # texto legible


def _meses_brecha(claves: list[tuple[int, int]]) -> int:
    """Meses sin descuento entre cuotas consecutivas (como el legado)."""
    faltantes = 0
    for i in range(1, len(claves)):
        py, pm = claves[i - 1]
        cy, cm = claves[i]
        diff = (cy - py) * 12 + (cm - pm)
        if diff > 1:
            faltantes += diff - 1
    return faltantes


def agrupar_por_numero(movs: list[MovimientoPrestamo]) -> list[ResumenPrestamo]:
    """Agrupa los movimientos por NUMERO de préstamo (como `agrupar_prestamos_por_numero`
    + el resumen detallado de `_preparar_contexto_ia` del legado): total prestado,
    abonado, saldo, nº de cuotas, cuota promedio, brechas y estimación para cancelar.
    """
    import math

    grupos: dict[str, list[MovimientoPrestamo]] = {}
    for m in movs:
        grupos.setdefault(m.numero or "(sin nº)", []).append(m)
    out: list[ResumenPrestamo] = []
    for num, ms in grupos.items():
        fechas = sorted(x.fecha for x in ms if x.fecha)
        prestado = round(sum(x.valor for x in ms if x.valor > 0), 2)
        abonado = round(sum(-x.valor for x in ms if x.valor < 0), 2)
        saldo = round(prestado - abonado, 2)
        egresos = [x for x in ms if x.valor < 0]
        n_cuotas = len(egresos)
        cuota_prom = round(abonado / n_cuotas, 2) if n_cuotas else 0.0
        claves = sorted({(int(x.fecha[:4]), int(x.fecha[5:7])) for x in egresos if len(x.fecha) >= 7})
        brecha = _meses_brecha(claves)
        cancelado = saldo <= 0.01
        meses_rest = math.ceil(saldo / cuota_prom) if (cuota_prom > 0 and not cancelado) else 0
        if cancelado:
            estado = f"Cancelado · {n_cuotas} cuotas de ~{cuota_prom:,.2f}"
        else:
            cont = "pagos continuos" if not brecha else f"{brecha} mes(es) sin descuento"
            estado = (
                f"Pendiente {saldo:,.2f} · ~{meses_rest} mes(es) para cancelar "
                f"({n_cuotas} cuotas ~{cuota_prom:,.2f}/mes, {cont})"
            )
        out.append(
            ResumenPrestamo(
                numero=num,
                desde=fechas[0] if fechas else "",
                hasta=fechas[-1] if fechas else "",
                prestado=prestado, abonado=abonado, saldo=saldo, cuotas=n_cuotas,
                cuota_promedio=cuota_prom, meses_brecha=brecha, cancelado=cancelado,
                meses_para_cancelar=meses_rest, estado=estado,
            )
        )
    out.sort(key=lambda r: r.hasta, reverse=True)
    return out


def movimientos_de_numero(movs: list[MovimientoPrestamo], numero: str) -> list[MovimientoPrestamo]:
    """Los movimientos individuales de un préstamo (para el detalle por fila)."""
    return sorted((m for m in movs if (m.numero or "(sin nº)") == numero), key=lambda m: m.fecha)
