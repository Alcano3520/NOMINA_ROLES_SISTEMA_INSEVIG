"""Reporte consolidado de nómina (una fila por empleado, columnas por concepto).

Porta `reportes/reporte_nomina_SQL_SERVER.pyw` / `_SUPABASE.pyw` / `_GUI.pyw` y el
`_COMPARADOR`. Solo lectura. La consolidación por CLASE reutiliza `core.datos.postproceso`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from core.concepts import CAMPOS_EGRESO, CAMPOS_INGRESO
from core.config import get_settings
from core.datos.postproceso import consolidar_conceptos
from core.db import sqlserver, supabase_client
from core.db.health import FUENTE_SQLSERVER, FUENTE_SUPABASE
from core.utils import a_float, normalizar_cedula

log = logging.getLogger(__name__)

_COLS_MOV = "EMPLEADO, CLASE, VALOR, ASENTADO, DIAS, DEPTO, SECCION, FECHA_VEN"


def _rango(periodo: str) -> tuple[str, str]:
    anio, mes = periodo.split("-")
    ini = f"{anio}-{int(mes):02d}-01"
    fin = f"{int(anio) + 1}-01-01" if int(mes) == 12 else f"{anio}-{int(mes) + 1:02d}-01"
    return ini, fin


# ── Lectura de movimientos ───────────────────────────────────────────────────


def _mov_sqlserver(periodo: str, historico: bool) -> Iterator[dict]:
    tabla = "RPHISTOR" if historico else "RPINGDES"
    flt = get_settings().sqlserver_filter
    ini, fin = _rango(periodo)
    with sqlserver.conexion() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT {_COLS_MOV} FROM [insevig].[dbo].[{tabla}]
                WHERE {flt} AND [FECHA_VEN] IS NOT NULL
                  AND CAST([FECHA_VEN] AS DATE) >= CAST(? AS DATE)
                  AND CAST([FECHA_VEN] AS DATE) <  CAST(? AS DATE)""",
            (ini, fin),
        )
        cols = [c[0] for c in cur.description]
        while True:
            lote = cur.fetchmany(2000)
            if not lote:
                break
            for row in lote:
                yield dict(zip(cols, row, strict=True))


def _mov_supabase(periodo: str, historico: bool) -> Iterator[dict]:
    tabla = "rphistor_temp" if historico else "rpingdesres"
    sb = supabase_client.get_client()
    ini, fin = _rango(periodo)
    paso = 1000
    desde = 0
    while True:
        r = (
            sb.table(tabla)
            .select("empleado,clase,valor,asentado,dias,depto,seccion,fecha_ven")
            .eq("codemp", "10")
            .gte("fecha_ven", ini)
            .lt("fecha_ven", fin)
            .range(desde, desde + paso - 1)
            .execute()
        )
        filas = r.data or []
        for row in filas:
            yield {k.upper(): v for k, v in row.items()}
        if len(filas) < paso:
            break
        desde += paso


_LECTORES: dict[str, Callable[[str, bool], Iterator[dict]]] = {
    FUENTE_SQLSERVER: _mov_sqlserver,
    FUENTE_SUPABASE: _mov_supabase,
}


def leer_movimientos(
    periodo: str, *, historico: bool, fuente: str, _lectores=None
) -> Iterator[dict]:
    lectores = _lectores or _LECTORES
    if fuente not in lectores:
        raise ValueError(f"Fuente desconocida: {fuente!r}")
    yield from lectores[fuente](periodo, historico)


# ── Catálogos de nombres ─────────────────────────────────────────────────────


def _catalogos(fuente: str) -> dict[str, dict[str, str]]:
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        out = {}
        for tipo in ("FNC", "DPT", "SEC"):
            r = sb.table("dbtablas").select("codigo,nombre").eq("tipo", tipo).eq("codemp", "10").execute()
            out[tipo] = {str(x["codigo"]).strip(): (x.get("nombre") or "").strip() for x in (r.data or [])}
        return out
    out = {}
    for tipo in ("FNC", "DPT", "SEC"):
        filas = sqlserver.filas(
            "SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO = ? AND CODEMP='10'", (tipo,)
        )
        out[tipo] = {str(r["CODIGO"]).strip(): (r["NOMBRE"] or "").strip() for r in filas}
    return out


def _empleados(fuente: str) -> dict[str, dict]:
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        r = (
            sb.table("rpemplea")
            .select("empleado,apellidos,nombres,cedula,cargo,depto,seccion,sueldo")
            .eq("codemp", "10")
            .execute()
        )
        return {
            str(x["empleado"]).strip(): {k.upper(): v for k, v in x.items()}
            for x in (r.data or [])
        }
    filas = sqlserver.filas(
        "SELECT EMPLEADO,APELLIDOS,NOMBRES,CEDULA,CARGO,DEPTO,SECCION,SUELDO "
        "FROM [insevig].[dbo].[RPEMPLEA] WHERE " + get_settings().sqlserver_filter
    )
    return {str(r["EMPLEADO"]).strip(): r for r in filas}


# ── Consolidación ────────────────────────────────────────────────────────────


@dataclass
class FilaConsolidada:
    empleado: str
    apellidos_nombres: str
    cedula: str
    cargo: str
    depto: str
    seccion: str
    sueldo_base: float
    total_ingresos: float
    total_egresos: float
    total_recibir: float
    conceptos: dict[str, float] = field(default_factory=dict)

    def to_row(self) -> dict[str, object]:
        base = {
            "EMPLEADO": self.empleado,
            "APELLIDOS_NOMBRES": self.apellidos_nombres,
            "CEDULA": self.cedula,
            "CARGO": self.cargo,
            "DEPTO": self.depto,
            "SECCION": self.seccion,
            "SUELDO_BASE": self.sueldo_base,
        }
        base.update({k: round(v, 2) for k, v in self.conceptos.items()})
        base["TOTAL_INGRESOS"] = self.total_ingresos
        base["TOTAL_EGRESOS"] = self.total_egresos
        base["TOTAL_RECIBIR"] = self.total_recibir
        return base


def consolidar(
    movimientos: Iterator[dict],
    catalogos: dict[str, dict[str, str]],
    empleados: dict[str, dict],
    *,
    progreso: Callable[[int], None] | None = None,
) -> list[FilaConsolidada]:
    por_emp: dict[str, list[dict]] = {}
    for i, mov in enumerate(movimientos, 1):
        cod = str(mov.get("EMPLEADO") or "").strip()
        if cod:
            por_emp.setdefault(cod, []).append(
                {
                    "clase": mov.get("CLASE"),
                    "valor": mov.get("VALOR"),
                    "asentado": bool(mov.get("ASENTADO")),
                    "dias": mov.get("DIAS"),
                }
            )
        if progreso and i % 5000 == 0:
            progreso(i)

    fnc, dpt, sec = catalogos["FNC"], catalogos["DPT"], catalogos["SEC"]
    filas: list[FilaConsolidada] = []
    for cod, movs in sorted(por_emp.items()):
        emp = empleados.get(cod, {})
        conceptos = consolidar_conceptos(movs)
        ingresos = round(sum(conceptos.get(k, 0.0) for k in CAMPOS_INGRESO), 2)
        egresos = round(sum(conceptos.get(k, 0.0) for k in CAMPOS_EGRESO), 2)
        ap = str(emp.get("APELLIDOS") or "").strip()
        no = str(emp.get("NOMBRES") or "").strip()
        filas.append(
            FilaConsolidada(
                empleado=cod,
                apellidos_nombres=f"{ap} {no}".strip(),
                cedula=normalizar_cedula(emp.get("CEDULA")),
                cargo=fnc.get(str(emp.get("CARGO") or "").strip(), str(emp.get("CARGO") or "")),
                depto=dpt.get(str(emp.get("DEPTO") or "").strip(), str(emp.get("DEPTO") or "")),
                seccion=sec.get(str(emp.get("SECCION") or "").strip(), str(emp.get("SECCION") or "")),
                sueldo_base=a_float(emp.get("SUELDO")),
                total_ingresos=ingresos,
                total_egresos=egresos,
                total_recibir=round(ingresos - egresos, 2),
                conceptos=conceptos,
            )
        )
    return filas


def reporte_consolidado(
    periodo: str, *, historico: bool, fuente: str,
    progreso: Callable[[int], None] | None = None,
) -> list[dict]:
    """Lista de filas (dicts) lista para exportar a Excel."""
    catalogos = _catalogos(fuente)
    empleados = _empleados(fuente)
    movs = leer_movimientos(periodo, historico=historico, fuente=fuente)
    return [f.to_row() for f in consolidar(movs, catalogos, empleados, progreso=progreso)]


# ── Comparador SQL Server vs Supabase ────────────────────────────────────────


@dataclass
class Discrepancia:
    tipo: str
    detalle: str


def comparar(sql_rows: list[dict], sup_rows: list[dict], *, tolerancia: float = 1.0) -> list[Discrepancia]:
    d: list[Discrepancia] = []
    if len(sql_rows) != len(sup_rows):
        d.append(Discrepancia("conteo_filas", f"SQL={len(sql_rows)} vs Supabase={len(sup_rows)}"))
    cols_sql = {k for r in sql_rows for k in r}
    cols_sup = {k for r in sup_rows for k in r}
    if cols_sql - cols_sup:
        d.append(Discrepancia("columnas", f"faltan en Supabase: {sorted(cols_sql - cols_sup)}"))
    if cols_sup - cols_sql:
        d.append(Discrepancia("columnas", f"sobran en Supabase: {sorted(cols_sup - cols_sql)}"))
    for campo in ("TOTAL_INGRESOS", "TOTAL_EGRESOS", "TOTAL_RECIBIR"):
        s1 = round(sum(a_float(r.get(campo)) for r in sql_rows), 2)
        s2 = round(sum(a_float(r.get(campo)) for r in sup_rows), 2)
        if abs(s1 - s2) > tolerancia:
            d.append(Discrepancia("suma", f"{campo}: SQL={s1} vs Supabase={s2} (dif {round(s1 - s2, 2)})"))
    return d


# ── Jobs (para core.jobs.JobRunner) ──────────────────────────────────────────


def job_consolidado(ctx, periodo: str, historico: bool, fuente: str) -> None:
    """Genera el consolidado y guarda el xlsx en storage; deja la ruta en el Job."""
    from core import storage
    from core.excel.nomina_builders import consolidado_xlsx

    ctx.progreso(0, 0, f"Leyendo movimientos de {fuente}…")
    filas = reporte_consolidado(
        periodo, historico=historico, fuente=fuente,
        progreso=lambda n: ctx.progreso(n, n, f"{n} movimientos procesados…"),
    )
    if ctx.cancelado:
        return
    ctx.progreso(len(filas), len(filas), "Generando Excel…")
    datos = consolidado_xlsx(filas)
    nombre = f"CONSOLIDADO_{periodo}_{'HIST' if historico else 'ACTUAL'}.xlsx"
    ruta = storage.guardar(ctx.job_id, nombre, datos)
    ctx.set_resultado(str(ruta))
    ctx.progreso(len(filas), len(filas), f"Listo: {len(filas)} empleados")


def job_comparador(ctx, periodo: str, historico: bool) -> None:
    from core import storage
    from core.excel.nomina_builders import comparador_xlsx

    ctx.progreso(0, 3, "Reconstruyendo desde SQL Server…")
    sql_rows = reporte_consolidado(periodo, historico=historico, fuente=FUENTE_SQLSERVER)
    if ctx.cancelado:
        return
    ctx.progreso(1, 3, "Reconstruyendo desde Supabase…")
    sup_rows = reporte_consolidado(periodo, historico=historico, fuente=FUENTE_SUPABASE)
    if ctx.cancelado:
        return
    ctx.progreso(2, 3, "Comparando…")
    difs = comparar(sql_rows, sup_rows)
    datos = comparador_xlsx(difs, sql_rows, sup_rows)
    ruta = storage.guardar(ctx.job_id, f"COMPARADOR_{periodo}.xlsx", datos)
    ctx.set_resultado(str(ruta))
    ctx.progreso(3, 3, "SIN diferencias" if not difs else f"{len(difs)} discrepancias")
