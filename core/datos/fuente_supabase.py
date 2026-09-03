"""Fetch crudo desde Supabase (PostgREST). Porta
`ObtenerDatos.obtener_datos_empleado_supabase` (shared/obtener_datos.py:279).

Tablas en minúscula: rpemplea, rpingdesres, rphistor_temp, dbtablas.
"""

from __future__ import annotations

from core.datos.port import DatosCrudos
from core.db import supabase_client


def _rango_periodo(periodo: str) -> tuple[str, str]:
    anio, mes = periodo.split("-")
    inicio = f"{anio}-{int(mes):02d}-01"
    fin = f"{int(anio) + 1}-01-01" if int(mes) == 12 else f"{anio}-{int(mes) + 1:02d}-01"
    return inicio, fin


def _buscar_empleado(sb, ident: str) -> dict | None:
    def tbl():
        return sb.table("rpemplea").select("*").eq("codemp", "10")

    consultas = [
        tbl().eq("empleado", str(ident)),
        tbl().ilike("nombres", f"%{ident}%"),
        tbl().ilike("apellidos", f"%{ident}%"),
    ]
    if str(ident).strip().replace(".", "", 1).isdigit():
        consultas.append(tbl().eq("cedula", float(ident)))
    for c in consultas:
        r = c.limit(1).execute()
        if r.data:
            return r.data[0]
    return None


def _movimientos(sb, empleado: str, inicio: str, fin: str) -> list[dict]:
    def q(tabla: str) -> list[dict]:
        r = (
            sb.table(tabla)
            .select("*")
            .eq("codemp", "10")
            .eq("empleado", str(empleado))
            .gte("fecha_ven", inicio)
            .lt("fecha_ven", fin)
            .execute()
        )
        return r.data or []

    filas = q("rpingdesres") or q("rphistor_temp")
    return [
        {
            "clase": row.get("clase"),
            "valor": row.get("valor"),
            "asentado": bool(row.get("asentado")),
            "dias": row.get("dias"),
        }
        for row in filas
    ]


def _catalogo(sb, tipo: str) -> dict[str, str]:
    r = (
        sb.table("dbtablas")
        .select("codigo,nombre")
        .eq("tipo", tipo)
        .eq("codemp", "10")
        .execute()
    )
    return {
        str(x.get("codigo", "")).strip(): (x.get("nombre") or "").strip()
        for x in (r.data or [])
    }


def fetch_empleado(periodo: str, cedula_o_nombre: str) -> DatosCrudos | None:
    sb = supabase_client.get_client()
    emp = _buscar_empleado(sb, cedula_o_nombre)
    if emp is None:
        return None
    empleado = str(emp.get("empleado") or "").strip()
    inicio, fin = _rango_periodo(periodo)
    return DatosCrudos(
        empleado=empleado,
        apellidos=str(emp.get("apellidos") or ""),
        nombres=str(emp.get("nombres") or ""),
        cedula=emp.get("cedula"),
        cargo_codigo=str(emp.get("cargo") or ""),
        depto_codigo=str(emp.get("depto") or ""),
        movimientos=_movimientos(sb, empleado, inicio, fin),
        catalogo_cargos=_catalogo(sb, "FNC"),
        catalogo_deptos=_catalogo(sb, "DPT"),
    )
