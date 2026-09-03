"""Observaciones / Multas / Faltas de empleados.

Porta `observaciones/TOTAL_OSERVACIONES_4_0.pyw` (consulta) y la lógica de slots
RPEMPOBSERV refer1..refer7 (la escritura se implementa en Fase 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.config import get_settings
from core.db import sqlserver, supabase_client
from core.db.health import FUENTE_SUPABASE
from core.utils import a_float, normalizar_cedula

CLASE_MULTA = 203
SLOTS_REFER = tuple(f"refer{i}" for i in range(1, 8))  # RPEMPOBSERV tiene 7 slots


@dataclass
class FilaObservacion:
    empleado: str
    apellidos_nombres: str
    fecha_ven: str
    textos: list[str] = field(default_factory=list)  # refer1..7 no vacíos


@dataclass
class Multa:
    fecha: str
    valor: float
    concepto: str
    observ: str


@dataclass
class Falta:
    periodo: str
    ausencias: float
    faltas_justificadas: float
    faltas_injustificadas: float
    total: float


def _filtro_sqlserver(ident: str) -> tuple[str, tuple]:
    ident = ident.strip()
    if ident.isdigit():
        return "o.empleado = ?", (ident,)
    like = f"%{ident}%"
    return (
        "(e.APELLIDOS LIKE ? OR e.NOMBRES LIKE ? OR "
        "(ISNULL(e.APELLIDOS,'') + ' ' + ISNULL(e.NOMBRES,'')) LIKE ?)",
        (like, like, like),
    )


def observaciones(ident: str, fuente: str) -> list[FilaObservacion]:
    if fuente == FUENTE_SUPABASE:
        return _observaciones_supabase(ident)
    cond, params = _filtro_sqlserver(ident)
    filas = sqlserver.filas(
        f"""SELECT o.empleado, o.fecha_ven,
                   {', '.join('o.' + s for s in SLOTS_REFER)},
                   e.APELLIDOS, e.NOMBRES
            FROM dbo.RPEMPOBSERV o
            LEFT JOIN dbo.RPEMPLEA e ON o.empleado = e.EMPLEADO
            WHERE {cond}
            ORDER BY o.fecha_ven ASC""",
        params,
    )
    return [_fila_obs(r, [r.get(s.upper()) or r.get(s) for s in SLOTS_REFER]) for r in filas]


def _observaciones_supabase(ident: str) -> list[FilaObservacion]:
    sb = supabase_client.get_client()
    q = sb.table("rpempobserv").select("*")
    ident = ident.strip()
    q = q.eq("empleado", ident) if ident.isdigit() else q.ilike("empleado", f"%{ident}%")
    filas = q.order("fecha_ven").execute().data or []
    emps = {
        str(x["empleado"]).strip(): x
        for x in (sb.table("rpemplea").select("empleado,apellidos,nombres").eq("codemp", "10").execute().data or [])
    }
    out = []
    for r in filas:
        e = emps.get(str(r.get("empleado")).strip(), {})
        r = {**r, "APELLIDOS": e.get("apellidos"), "NOMBRES": e.get("nombres")}
        out.append(_fila_obs(r, [r.get(s) for s in SLOTS_REFER]))
    return out


def _fila_obs(r: dict, refers: list) -> FilaObservacion:
    ap = (r.get("APELLIDOS") or "").strip()
    no = (r.get("NOMBRES") or "").strip()
    return FilaObservacion(
        empleado=str(r.get("empleado") or r.get("EMPLEADO") or "").strip(),
        apellidos_nombres=f"{ap} {no}".strip(),
        fecha_ven=str(r.get("fecha_ven") or r.get("FECHA_VEN") or "")[:10],
        textos=[str(t).strip() for t in refers if t and str(t).strip()],
    )


def multas(empleado: str, fuente: str) -> list[Multa]:
    if not empleado.strip().isdigit():
        return []
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        filas = (
            sb.table("rphistor_temp")
            .select("fecha,valor,concepto,observ")
            .eq("empleado", empleado.strip())
            .eq("clase", CLASE_MULTA)
            .order("fecha", desc=True)
            .execute()
            .data
            or []
        )
        return [
            Multa(
                str(r.get("fecha") or "")[:10],
                a_float(r.get("valor")),
                r.get("concepto") or "",
                r.get("observ") or "",
            )
            for r in filas
        ]
    filas = sqlserver.filas(
        """SELECT FECHA, VALOR, CONCEPTO, OBSERV FROM dbo.RPHISTOR
           WHERE EMPLEADO = ? AND CLASE = '203' ORDER BY FECHA DESC""",
        (empleado.strip(),),
    )
    return [
        Multa(str(r.get("FECHA") or "")[:10], a_float(r.get("VALOR")), r.get("CONCEPTO") or "", r.get("OBSERV") or "")
        for r in filas
    ]


def faltas(empleado: str, fuente: str, *, historicas: bool = False) -> list[Falta]:
    if not empleado.strip():
        return []
    tabla_sql = "RPHORHIS" if historicas else "RPHORTOT"
    tabla_sb = "rphorhis" if historicas else "rphortot"
    cols = "FECHA_VEN, ISNULL(TOTAUS,0) TOTAUS, ISNULL(TOTFJ,0) TOTFJ, ISNULL(TOTFI,0) TOTFI"
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        filas = (
            sb.table(tabla_sb)
            .select("fecha_ven,totaus,totfj,totfi")
            .eq("empleado", empleado.strip())
            .order("fecha_ven", desc=True)
            .execute()
            .data
            or []
        )
        return [_falta({k.upper(): v for k, v in r.items()}) for r in filas]
    _ = get_settings()
    filas = sqlserver.filas(
        f"SELECT {cols} FROM dbo.{tabla_sql} WHERE EMPLEADO = ? ORDER BY FECHA_VEN DESC",
        (empleado.strip(),),
    )
    return [_falta(r) for r in filas]


def _falta(r: dict) -> Falta:
    aus = a_float(r.get("TOTAUS"))
    fj = a_float(r.get("TOTFJ"))
    fi = a_float(r.get("TOTFI"))
    return Falta(
        periodo=str(r.get("FECHA_VEN") or "")[:7],
        ausencias=aus,
        faltas_justificadas=fj,
        faltas_injustificadas=fi,
        total=round(aus + fj + fi, 2),
    )


def guardar_observacion(empleado: str, periodo: str, texto: str, *, usuario: str, roles: set[str]) -> str:
    """Guarda `texto` en el primer slot refer1..7 libre del mes/año de `periodo`
    (YYYY-MM) en RPEMPOBSERV. Crea fila si los 7 están llenos. Evita duplicados exactos.
    Escribe solo a SQL Server, con auditoría y advisory lock por empleado.
    """
    from core.audit.writer import audit_scope
    from core.db import sqlserver

    texto = texto.strip()[:256]
    if not texto:
        raise ValueError("Texto vacío")
    anio, mes = periodo.split("-")
    ini, fin = f"{anio}-{int(mes):02d}-01", (
        f"{int(anio) + 1}-01-01" if int(mes) == 12 else f"{anio}-{int(mes) + 1:02d}-01"
    )
    with audit_scope(
        "observaciones", "crear", usuario=usuario, roles=roles,
        target_table="RPEMPOBSERV", target_key=empleado, after={"periodo": periodo, "texto": texto},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        # serializa la asignación de slot entre usuarios
        cur.execute("SELECT APPLOCK_MODE('public', ?, 'Session')", (f"obs_{empleado}",))
        cur.execute(
            f"""SELECT TOP 1 {', '.join(SLOTS_REFER)}, fecha_ven
                    FROM dbo.RPEMPOBSERV
                    WHERE empleado = ? AND fecha_ven >= ? AND fecha_ven < ?
                    ORDER BY fecha_ven""",
            (empleado, ini, fin),
        )
        fila = cur.fetchone()
        if fila is not None:
            actuales = [fila[i] for i in range(7)]
            if texto in [str(a).strip() for a in actuales if a]:
                return "duplicado"
            for i, slot in enumerate(SLOTS_REFER):
                if not actuales[i]:
                    cur.execute(
                        f"UPDATE TOP (1) dbo.RPEMPOBSERV SET {slot} = ? "
                        f"WHERE empleado = ? AND fecha_ven = ?",
                        (texto, empleado, fila[7]),
                    )
                    conn.commit()
                    return slot
        # sin fila con hueco -> insertar nueva
        cur.execute(
            f"INSERT INTO dbo.RPEMPOBSERV (empleado, codemp, codsuc, fecha_ven, {SLOTS_REFER[0]}) "
            f"VALUES (?, '10', '10', ?, ?)",
            (empleado, f"{anio}-{int(mes):02d}-01", texto),
        )
        conn.commit()
        return "nueva_fila"


def buscar_empleados(texto: str, fuente: str) -> list[dict]:
    """Devuelve [{'empleado','apellidos_nombres','cedula'}] para el selector."""
    texto = texto.strip()
    if not texto:
        return []
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        q = sb.table("rpemplea").select("empleado,apellidos,nombres,cedula").eq("codemp", "10")
        if texto.isdigit():
            q = q.or_(f"empleado.eq.{texto},cedula.eq.{texto}")
        else:
            q = q.or_(f"apellidos.ilike.%{texto}%,nombres.ilike.%{texto}%")
        filas = q.limit(50).execute().data or []
        return [
            {
                "empleado": str(r["empleado"]).strip(),
                "apellidos_nombres": f"{(r.get('apellidos') or '').strip()} {(r.get('nombres') or '').strip()}".strip(),
                "cedula": normalizar_cedula(r.get("cedula")),
            }
            for r in filas
        ]
    flt = get_settings().sqlserver_filter
    params: tuple
    if texto.isdigit():
        cond, params = "([EMPLEADO] = ? OR [CEDULA] = ?)", (texto, int(texto))
    else:
        like = f"%{texto}%"
        cond, params = "([APELLIDOS] LIKE ? OR [NOMBRES] LIKE ?)", (like, like)
    filas = sqlserver.filas(
        f"""SELECT TOP 50 [EMPLEADO],[APELLIDOS],[NOMBRES],[CEDULA]
            FROM [insevig].[dbo].[RPEMPLEA] WHERE {flt} AND {cond}""",
        params,
    )
    return [
        {
            "empleado": str(r["EMPLEADO"]).strip(),
            "apellidos_nombres": f"{(r.get('APELLIDOS') or '').strip()} {(r.get('NOMBRES') or '').strip()}".strip(),
            "cedula": normalizar_cedula(r.get("CEDULA")),
        }
        for r in filas
    ]
