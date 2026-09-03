"""Fetch crudo desde SQL Server. Porta las queries de
`ObtenerDatos.obtener_datos_empleado_rapido` (shared/obtener_datos.py:53).

Solo trae datos; la consolidación vive en `postproceso`.
"""

from __future__ import annotations

from core.config import get_settings
from core.datos.port import DatosCrudos
from core.db import sqlserver
from core.utils import a_int

_COLS_EMP = "[EMPLEADO],[APELLIDOS],[NOMBRES],[CEDULA],[SUELDO],[CARGO],[DEPTO],[SECCION]"


def _rango_periodo(periodo: str) -> tuple[str, str]:
    anio, mes = periodo.split("-")
    inicio = f"{anio}-{int(mes):02d}-01"
    fin = f"{int(anio) + 1}-01-01" if int(mes) == 12 else f"{anio}-{int(mes) + 1:02d}-01"
    return inicio, fin


def _rows(cur, query: str, params: tuple) -> list[dict]:
    cur.execute(query, params)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def _buscar_empleado(cur, flt: str, ident: str) -> dict | None:
    base = (
        f"SELECT {_COLS_EMP} FROM [insevig].[dbo].[RPEMPLEA] "
        f"WHERE {flt} AND [ESTADO]='ACT'"
    )
    intentos: list[tuple[str, tuple]] = []
    if len(str(ident)) <= 6:
        intentos.append((f"{base} AND [EMPLEADO] = ?", (str(ident),)))
    if str(ident).strip().isdigit():
        intentos.append((f"{base} AND [CEDULA] = ?", (a_int(ident),)))
    like = f"%{ident}%"
    intentos.append(
        (
            f"{base} AND ([NOMBRES] LIKE ? OR [APELLIDOS] LIKE ? "
            f"OR CAST([CEDULA] AS VARCHAR(20)) LIKE ?)",
            (like, like, like),
        )
    )
    for query, params in intentos:
        filas = _rows(cur, query, params)
        if filas:
            return filas[0]
    return None


def _movimientos(cur, flt: str, empleado: str, inicio: str, fin: str) -> list[dict]:
    def q(tabla: str) -> list[dict]:
        return _rows(
            cur,
            f"""SELECT * FROM [insevig].[dbo].[{tabla}]
                WHERE {flt} AND [EMPLEADO] = ? AND [FECHA_VEN] IS NOT NULL
                  AND CAST([FECHA_VEN] AS DATE) >= CAST(? AS DATE)
                  AND CAST([FECHA_VEN] AS DATE) <  CAST(? AS DATE)""",
            (empleado, inicio, fin),
        )

    filas = q("RPINGDES") or q("RPHISTOR")
    return [
        {
            "clase": row.get("CLASE"),
            "valor": row.get("VALOR"),
            "asentado": bool(row.get("ASENTADO")),
            "dias": row.get("DIAS"),
        }
        for row in filas
    ]


def _catalogo(cur, tipo: str) -> dict[str, str]:
    filas = _rows(
        cur,
        "SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO = ? AND CODEMP='10'",
        (tipo,),
    )
    return {str(r["CODIGO"]).strip(): (r["NOMBRE"] or "").strip() for r in filas}


def fetch_empleado(periodo: str, cedula_o_nombre: str) -> DatosCrudos | None:
    flt = get_settings().sqlserver_filter
    with sqlserver.conexion() as conn:
        cur = conn.cursor()
        emp = _buscar_empleado(cur, flt, cedula_o_nombre)
        if emp is None:
            return None
        empleado = str(emp["EMPLEADO"]).strip()
        inicio, fin = _rango_periodo(periodo)
        return DatosCrudos(
            empleado=empleado,
            apellidos=str(emp.get("APELLIDOS") or ""),
            nombres=str(emp.get("NOMBRES") or ""),
            cedula=emp.get("CEDULA"),
            cargo_codigo=str(emp.get("CARGO") or ""),
            depto_codigo=str(emp.get("DEPTO") or ""),
            movimientos=_movimientos(cur, flt, empleado, inicio, fin),
            catalogo_cargos=_catalogo(cur, "FNC"),
            catalogo_deptos=_catalogo(cur, "DPT"),
        )
