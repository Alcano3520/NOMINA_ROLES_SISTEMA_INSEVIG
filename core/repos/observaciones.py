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


def _rango_mes(periodo: str) -> tuple[str, str]:
    anio, mes = periodo.split("-")
    ini = f"{anio}-{int(mes):02d}-01"
    fin = f"{int(anio) + 1}-01-01" if int(mes) == 12 else f"{anio}-{int(mes) + 1:02d}-01"
    return ini, fin


def observaciones_mes(empleado: str, periodo: str, fuente: str) -> dict:
    """Los 7 slots refer1..7 de la fila del mes `periodo` (YYYY-MM) para el editor
    de empleados. Devuelve {'existe': bool, 'fecha_ven': str, 'slots': [7 textos]}.
    """
    ini, fin = _rango_mes(periodo)
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        filas = (
            sb.table("rpempobserv")
            .select("*")
            .eq("empleado", str(empleado))
            .gte("fecha_ven", ini)
            .lt("fecha_ven", fin)
            .order("fecha_ven")
            .limit(1)
            .execute()
            .data
            or []
        )
        r = filas[0] if filas else None
        get = (lambda s: (r or {}).get(s))  # noqa: E731
    else:
        flt = get_settings().sqlserver_filter
        filas = sqlserver.filas(
            f"""SELECT TOP 1 {', '.join(SLOTS_REFER)}, fecha_ven
                FROM dbo.RPEMPOBSERV
                WHERE empleado = ? AND fecha_ven >= ? AND fecha_ven < ? AND {flt}
                ORDER BY fecha_ven""",
            (str(empleado), ini, fin),
        )
        r = filas[0] if filas else None
        get = (lambda s: (r or {}).get(s.upper()) or (r or {}).get(s))  # noqa: E731
    if r is None:
        return {"existe": False, "fecha_ven": "", "slots": [""] * 7}
    return {
        "existe": True,
        "fecha_ven": str(get("fecha_ven") or "")[:10],
        "slots": [str(get(s) or "").strip() for s in SLOTS_REFER],
    }


def guardar_observaciones_mes(
    empleado: str, periodo: str, slots: list[str], *, usuario: str, roles: set[str]
) -> int:
    """Reescribe los 7 slots refer1..7 de la fila del mes `periodo` en RPEMPOBSERV
    (edición inline, como el legado). Crea la fila si no existe. SQL Server + auditoría.
    Devuelve cuántos slots cambiaron.
    """
    from core.audit.writer import audit_scope

    slots = [(s or "").strip()[:256] for s in slots][:7]
    slots += [""] * (7 - len(slots))
    ini, fin = _rango_mes(periodo)
    flt = get_settings().sqlserver_filter
    anio, mes = periodo.split("-")
    with audit_scope(
        "empleados", "editar", usuario=usuario, roles=roles,
        target_table="RPEMPOBSERV", target_key=empleado,
        after={"periodo": periodo, "slots": slots},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT APPLOCK_MODE('public', ?, 'Session')", (f"obs_{empleado}",))
        cur.execute(
            f"""SELECT TOP 1 {', '.join(SLOTS_REFER)}, fecha_ven FROM dbo.RPEMPOBSERV
                WHERE empleado = ? AND fecha_ven >= ? AND fecha_ven < ? AND {flt}
                ORDER BY fecha_ven""",
            (empleado, ini, fin),
        )
        fila = cur.fetchone()
        if fila is None:
            cur.execute(
                f"INSERT INTO dbo.RPEMPOBSERV (empleado, codemp, codsuc, fecha_ven, "
                f"{', '.join(SLOTS_REFER)}) VALUES (?, '10', '10', ?, {', '.join(['?'] * 7)})",
                (empleado, f"{anio}-{int(mes):02d}-01", *slots),
            )
            conn.commit()
            return sum(1 for s in slots if s)
        actuales = [str(fila[i] or "").strip() for i in range(7)]
        fecha_ven = fila[7]
        cambios = 0
        for i, slot in enumerate(SLOTS_REFER):
            if slots[i] != actuales[i]:
                cur.execute(
                    f"UPDATE TOP (1) dbo.RPEMPOBSERV SET {slot} = ? "
                    f"WHERE empleado = ? AND fecha_ven = ? AND {flt}",
                    (slots[i] or None, empleado, fecha_ven),
                )
                cambios += 1
        conn.commit()
        return cambios


def historial_observaciones(empleado: str, fuente: str) -> list[dict]:
    """Todas las filas de RPEMPOBSERV del empleado, para imprimir historial completo."""
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        filas = (
            sb.table("rpempobserv").select("*").eq("empleado", str(empleado))
            .order("fecha_ven", desc=True).execute().data or []
        )
        get = lambda r, s: r.get(s)  # noqa: E731
    else:
        flt = get_settings().sqlserver_filter
        filas = sqlserver.filas(
            f"""SELECT {', '.join(SLOTS_REFER)}, fecha_ven FROM dbo.RPEMPOBSERV
                WHERE empleado = ? AND {flt} ORDER BY fecha_ven DESC""",
            (str(empleado),),
        )
        get = lambda r, s: r.get(s.upper()) or r.get(s)  # noqa: E731
    out = []
    for r in filas:
        textos = [str(get(r, s) or "").strip() for s in SLOTS_REFER]
        textos = [t for t in textos if t]
        if textos:
            out.append({"fecha_ven": str(get(r, "fecha_ven") or "")[:10], "textos": textos})
    return out


def datos_basicos_empleado(empleado: str, fuente: str) -> dict:
    """Ficha resumida para la cabecera del visor de observaciones
    (como `obtener_datos_empleado` del legado)."""
    cols = "empleado,apellidos,nombres,cedula,cargo,depto,seccion,fecha_ing,fecha_sal,estado,telefono,direccion"
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        r = sb.table("rpemplea").select(cols).eq("codemp", "10").eq("empleado", str(empleado)).limit(1).execute()
        d = r.data[0] if r.data else {}
        g = lambda k: d.get(k)  # noqa: E731
    else:
        flt = get_settings().sqlserver_filter
        filas = sqlserver.filas(
            f"""SELECT EMPLEADO,APELLIDOS,NOMBRES,CEDULA,CARGO,DEPTO,SECCION,FECHA_ING,FECHA_SAL,
                       ESTADO,TELEFONO,DIRECCION
                FROM dbo.RPEMPLEA WHERE {flt} AND EMPLEADO = ?""",
            (str(empleado),),
        )
        d = filas[0] if filas else {}
        g = lambda k: d.get(k.upper()) or d.get(k)  # noqa: E731
    if not d:
        return {}
    return {
        "empleado": str(g("empleado") or empleado).strip(),
        "nombre": f"{(g('apellidos') or '').strip()} {(g('nombres') or '').strip()}".strip(),
        "cedula": normalizar_cedula(g("cedula")),
        "cargo": str(g("cargo") or ""),
        "depto": str(g("depto") or ""),
        "seccion": str(g("seccion") or ""),
        "fecha_ing": str(g("fecha_ing") or "")[:10],
        "fecha_sal": str(g("fecha_sal") or "")[:10],
        "estado": str(g("estado") or ""),
        "telefono": str(g("telefono") or ""),
        "direccion": str(g("direccion") or ""),
    }


def reporte_html(empleado: str, nombre: str, obs: list[dict], multas_: list[dict], faltas_: list[dict]) -> str:
    """HTML imprimible con observaciones + multas + faltas de un empleado
    (porta `guardar_texto` / generación de reporte del legado)."""
    import datetime as _dt
    import html as _h

    def _fila_obs(o: dict) -> str:
        f = _h.escape(str(o.get("fecha_ven", "")))
        t = _h.escape(str(o.get("texto", "")))
        return f"<tr><td>{f}</td><td>{t}</td></tr>"

    def _fila_multa(m: dict) -> str:
        return (
            f"<tr><td>{_h.escape(str(m.get('fecha', '')))}</td>"
            f"<td style='text-align:right'>{m.get('valor', 0):.2f}</td>"
            f"<td>{_h.escape(str(m.get('concepto', '')))}</td>"
            f"<td>{_h.escape(str(m.get('observ', '')))}</td></tr>"
        )

    def _fila_falta(f: dict) -> str:
        return (
            f"<tr><td>{_h.escape(str(f.get('periodo', '')))}</td>"
            f"<td>{f.get('ausencias', 0)}</td><td>{f.get('faltas_justificadas', 0)}</td>"
            f"<td>{f.get('faltas_injustificadas', 0)}</td><td>{f.get('total', 0)}</td></tr>"
        )

    ahora = _dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    t_obs = "".join(_fila_obs(o) for o in obs) or "<tr><td colspan=2>Sin datos</td></tr>"
    t_mul = "".join(_fila_multa(m) for m in multas_) or "<tr><td colspan=4>Sin datos</td></tr>"
    t_fal = "".join(_fila_falta(f) for f in faltas_) or "<tr><td colspan=5>Sin datos</td></tr>"
    nom, emp = _h.escape(nombre), _h.escape(str(empleado))
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<title>Observaciones — {nom}</title><style>
 body{{font-family:'Segoe UI',Arial,sans-serif;margin:32px;color:#222}}
 h1{{font-size:18px}} h2{{font-size:14px;background:#0D1B2A;color:#fff;padding:6px 10px;margin-top:20px}}
 table{{border-collapse:collapse;width:100%;font-size:12px;margin-top:6px}}
 th,td{{border:1px solid #bbb;padding:4px 6px;text-align:left}} th{{background:#1a4d8f;color:#fff}}
 .info{{color:#555;font-size:12px;margin-bottom:12px}}
</style></head><body>
<h1>INSEVIG — Observaciones, multas y faltas</h1>
<div class="info">Empleado: <b>{nom}</b> &nbsp;|&nbsp; Código: {emp} &nbsp;|&nbsp; Generado: {ahora}</div>
<h2>Observaciones</h2>
<table><tr><th>Fecha</th><th>Texto</th></tr>{t_obs}</table>
<h2>Multas (CLASE 203)</h2>
<table><tr><th>Fecha</th><th>Valor</th><th>Concepto</th><th>Observación</th></tr>{t_mul}</table>
<h2>Faltas</h2>
<table><tr><th>Período</th><th>Ausencias</th><th>F. just.</th><th>F. injust.</th><th>Total</th></tr>{t_fal}</table>
<p style="margin-top:24px;font-size:12px;color:#666">Listo para imprimir (Ctrl+P).</p>
</body></html>"""


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
