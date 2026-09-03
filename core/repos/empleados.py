"""CRUD de empleados (RPEMPLEA). Porta `empleados/SISTEMA_GESTION_EMPLEADOS_10.pyw`.

Escrituras SOLO a SQL Server (login RW), con vista previa y `AuditWriter`.
Concurrencia optimista: hash de los campos editables al abrir el editor; si cambió
al guardar, se rechaza.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from core.audit.writer import audit_scope
from core.config import get_settings
from core.db import sqlserver, supabase_client
from core.db.health import FUENTE_SUPABASE
from core.utils import a_float, normalizar_cedula

# Campos editables de RPEMPLEA, agrupados para el formulario.
GRUPOS: dict[str, tuple[str, ...]] = {
    "Datos generales": (
        "NOMBRES", "APELLIDOS", "CEDULA", "SEXO", "ESTADO_CI", "FECHA_NAC", "LUGAR_NAC",
    ),
    "Contacto": ("DIRECCION", "PROVINCIA", "CANTON", "PARROQUIA", "TELEFONO", "emp_mail"),
    "Laboral": ("FECHA_ING", "FECHA_SAL", "DEPTO", "SECCION", "CARGO", "ESTADO"),
    "Ingresos / descuentos": (
        "SUELDO", "BONIFI", "TRANSP", "LUNCH", "DECIMO3", "DECIMO4", "VACACION", "CARGAS",
    ),
    "Bancarios": ("TIPO_PGO", "CODCTA", "CTA_CTE", "CTA_AHO", "CODIESS", "NUM_AFIL"),
}
CAMPOS_EDITABLES: tuple[str, ...] = tuple(c for cs in GRUPOS.values() for c in cs)
CAMPOS_NUMERICOS = frozenset(
    {"SUELDO", "BONIFI", "TRANSP", "LUNCH", "DECIMO3", "DECIMO4", "VACACION", "CARGAS"}
)

# Catálogos de DBTABLAS: TIPO -> etiqueta
CATALOGOS = {
    "CAR": "cargos", "SEC": "secciones", "DPT": "departamentos", "SEX": "sexos",
    "ECS": "estados_civiles", "TTR": "tipos_trabajo", "FPA": "formas_pago", "BCO": "bancos",
}


@dataclass
class Empleado:
    empleado: str
    campos: dict[str, object]
    token: str  # hash de concurrencia
    creado_por: str = ""
    fecha_crea: str = ""
    mod_por: str = ""
    fecha_mod: str = ""


def _token(campos: dict) -> str:
    payload = json.dumps({k: str(campos.get(k, "")) for k in CAMPOS_EDITABLES}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ── Lectura ──────────────────────────────────────────────────────────────────


def buscar(texto: str, fuente: str, *, solo_activos: bool = False, limite: int = 200) -> list[dict]:
    texto = texto.strip()
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        q = sb.table("rpemplea").select("empleado,apellidos,nombres,cedula,cargo,estado").eq("codemp", "10")
        if solo_activos:
            q = q.eq("estado", "ACT")
        if texto:
            q = (
                q.eq("empleado", texto)
                if texto.isdigit()
                else q.or_(f"apellidos.ilike.%{texto}%,nombres.ilike.%{texto}%")
            )
        filas = q.limit(limite).execute().data or []
        return [
            {
                "empleado": str(r["empleado"]).strip(),
                "apellidos_nombres": f"{(r.get('apellidos') or '').strip()} {(r.get('nombres') or '').strip()}".strip(),
                "cedula": normalizar_cedula(r.get("cedula")),
                "cargo": str(r.get("cargo") or ""),
                "estado": r.get("estado") or "",
            }
            for r in filas
        ]
    flt = get_settings().sqlserver_filter
    cond = flt
    params: list = []
    if solo_activos:
        cond += " AND [ESTADO]='ACT'"
    if texto:
        if texto.isdigit():
            cond += " AND [EMPLEADO] = ?"
            params.append(texto)
        else:
            cond += " AND ([APELLIDOS] LIKE ? OR [NOMBRES] LIKE ?)"
            params += [f"%{texto}%", f"%{texto}%"]
    filas = sqlserver.filas(
        f"""SELECT TOP {limite} [EMPLEADO],[APELLIDOS],[NOMBRES],[CEDULA],[CARGO],[ESTADO]
            FROM [insevig].[dbo].[RPEMPLEA] WHERE {cond} ORDER BY [APELLIDOS]""",
        tuple(params),
    )
    return [
        {
            "empleado": str(r["EMPLEADO"]).strip(),
            "apellidos_nombres": f"{(r.get('APELLIDOS') or '').strip()} {(r.get('NOMBRES') or '').strip()}".strip(),
            "cedula": normalizar_cedula(r.get("CEDULA")),
            "cargo": str(r.get("CARGO") or ""),
            "estado": r.get("ESTADO") or "",
        }
        for r in filas
    ]


def obtener(empleado: str, fuente: str) -> Empleado | None:
    cols = ",".join(f"[{c}]" for c in CAMPOS_EDITABLES)
    aud = "[creado_por],[fecha_crea],[mod_por],[fecha_mod]"
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        r = sb.table("rpemplea").select("*").eq("codemp", "10").eq("empleado", str(empleado)).limit(1).execute()
        if not r.data:
            return None
        row = {k.upper() if k.upper() in CAMPOS_EDITABLES else k: v for k, v in r.data[0].items()}
    else:
        flt = get_settings().sqlserver_filter
        filas = sqlserver.filas(
            f"SELECT {cols},{aud} FROM [insevig].[dbo].[RPEMPLEA] WHERE {flt} AND [EMPLEADO] = ?",
            (str(empleado),),
        )
        if not filas:
            return None
        row = filas[0]
    campos = {c: row.get(c) for c in CAMPOS_EDITABLES}
    return Empleado(
        empleado=str(empleado).strip(),
        campos=campos,
        token=_token(campos),
        creado_por=str(row.get("creado_por") or row.get("CREADO_POR") or ""),
        fecha_crea=str(row.get("fecha_crea") or row.get("FECHA_CREA") or "")[:19],
        mod_por=str(row.get("mod_por") or row.get("MOD_POR") or ""),
        fecha_mod=str(row.get("fecha_mod") or row.get("FECHA_MOD") or "")[:19],
    )


# ── Escritura (siempre SQL Server) ───────────────────────────────────────────


class ConflictoConcurrencia(RuntimeError):
    """Otro usuario modificó el registro desde que se abrió el editor."""


def _normalizar(campos: dict) -> dict:
    out: dict[str, object] = {}
    for k, v in campos.items():
        if k not in CAMPOS_EDITABLES:
            continue
        if k in CAMPOS_NUMERICOS:
            out[k] = a_float(v)
        else:
            out[k] = None if v in (None, "") else str(v).strip()
    return out


def actualizar(empleado: str, campos: dict, token_previo: str, *, usuario: str, roles: set[str]) -> None:
    actual = obtener(empleado, "sqlserver")
    if actual is None:
        raise LookupError(f"Empleado {empleado} no existe")
    if actual.token != token_previo:
        raise ConflictoConcurrencia(
            "Otro usuario modificó este empleado. Recarga el editor y vuelve a intentar."
        )
    nuevos = _normalizar(campos)
    flt = get_settings().sqlserver_filter
    sets = ", ".join(f"[{c}] = ?" for c in nuevos)
    with audit_scope(
        "empleados", "editar", usuario=usuario, roles=roles,
        target_table="RPEMPLEA", target_key=empleado,
        antes=actual.campos, after=nuevos,
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE [insevig].[dbo].[RPEMPLEA] SET {sets}, [mod_por] = ?, [fecha_mod] = GETDATE() "
            f"WHERE [EMPLEADO] = ? AND {flt}",
            (*nuevos.values(), usuario, empleado),
        )
        conn.commit()


def crear(campos: dict, *, usuario: str, roles: set[str]) -> str:
    nuevos = _normalizar(campos)
    empleado = str(campos.get("EMPLEADO") or "").strip()
    if not empleado:
        raise ValueError("Falta el código de empleado (EMPLEADO)")
    s = get_settings()
    cols = ["EMPLEADO", "CODEMP", "CODSUC", *nuevos.keys(), "creado_por", "fecha_crea"]
    vals: list = [empleado, "10", "10", *nuevos.values(), usuario]
    placeholders = ", ".join(["?"] * (len(vals)) + ["GETDATE()"])
    with audit_scope(
        "empleados", "crear", usuario=usuario, roles=roles,
        target_table="RPEMPLEA", target_key=empleado, after=nuevos,
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO [insevig].[dbo].[RPEMPLEA] ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(vals),
        )
        conn.commit()
    _ = s
    return empleado


def eliminar(empleado: str, *, usuario: str, roles: set[str]) -> None:
    actual = obtener(empleado, "sqlserver")
    if actual is None:
        raise LookupError(f"Empleado {empleado} no existe")
    flt = get_settings().sqlserver_filter
    with audit_scope(
        "empleados", "eliminar", usuario=usuario, roles=roles,
        target_table="RPEMPLEA", target_key=empleado, antes=actual.campos,
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM [insevig].[dbo].[RPEMPLEA] WHERE [EMPLEADO] = ? AND {flt}",
            (empleado,),
        )
        conn.commit()


def job_carga_masiva(ctx, filas: list[dict], *, usuario: str, roles: set[str]) -> None:
    """Aplica una carga masiva fila por fila; audita cada una; deja un xlsx de resultados."""
    from core import storage
    from core.excel.empleados_builders import reporte_resultados

    resultados: list[dict] = []
    total = len(filas)
    for i, fila in enumerate(filas, 1):
        if ctx.cancelado:
            break
        cod = str(fila.get("EMPLEADO") or "").strip()
        try:
            actual = obtener(cod, "sqlserver")
            if actual is None:
                resultados.append({"empleado": cod, "ok": False, "detalle": "no existe"})
            else:
                actualizar(cod, fila, actual.token, usuario=usuario, roles=roles)
                resultados.append({"empleado": cod, "ok": True, "detalle": f"{len(fila) - 1} campos"})
        except Exception as e:  # noqa: BLE001
            resultados.append({"empleado": cod, "ok": False, "detalle": str(e)[:200]})
        ctx.progreso(i, total, f"{i}/{total} · OK {sum(r['ok'] for r in resultados)}")
    ruta = storage.guardar(ctx.job_id, "CARGA_MASIVA_RESULTADO.xlsx", reporte_resultados(resultados))
    ctx.set_resultado(str(ruta))
    ok = sum(r["ok"] for r in resultados)
    ctx.progreso(total, total, f"Terminado: {ok} OK, {len(resultados) - ok} con error")


def catalogos(fuente: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        for tipo in CATALOGOS:
            r = (
                sb.table("dbtablas")
                .select("codigo,nombre")
                .eq("tipo", tipo)
                .eq("codemp", "10")
                .execute()
            )
            out[tipo] = [
                {"codigo": str(x["codigo"]).strip(), "nombre": (x.get("nombre") or "").strip()}
                for x in (r.data or [])
            ]
        return out
    for tipo in CATALOGOS:
        filas = sqlserver.filas(
            "SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO = ? AND CODEMP='10'", (tipo,)
        )
        out[tipo] = [{"codigo": str(r["CODIGO"]).strip(), "nombre": (r["NOMBRE"] or "").strip()} for r in filas]
    return out
