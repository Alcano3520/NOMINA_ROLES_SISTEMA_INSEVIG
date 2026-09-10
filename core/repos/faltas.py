"""Gestión de Faltas / Permisos / Suspensiones / Restas de Horas — escritura.

Trasplante de `sistema_sanciones_RRHH/nucleo_modular/repos/faltas.py`
(`faltas_datos.py` SQL Server + `faltas_calculo.py` + `faltas_reportes.py`).
Origen legado: `gestion_faltas.py` (4 pestañas: Registro Masivo, Registro Uno a
Uno, Ver/Editar Período, Cargador de Restas de Horas).

Superficie de escritura: `RPHORTOT` (período de faltas abierto, contrato C1) y
`RPEMPLEA` (HOR25/HOR50/HOR100). `RPHORHIS` (meses cerrados) = SOLO lectura.
Toda escritura: `dry_run=True` por defecto (vista previa) + `AuditWriter`.
Lecturas: SQL Server (el módulo legado era SQL-Server-only; el visor de
`observaciones` cubre la lectura por Supabase).

Decisiones sobre los bugs del legado (aprobadas por el usuario 2026-09-09,
ver docs/modulos/faltas.md):
- Bug #1 (SUSPENSION vs SUSPENSIÓN en VALIDAR/REGISTRAR): replicado (está en
  `core/faltas/calculo.py`, no afecta la escritura).
- Bug #2 (días de suspensión con +1): replicado — es correcto.
- Bug #3 (descuento de horas extra sin clamp en masivo → negativos): CORREGIDO
  aquí: el descuento SIEMPRE se acota (`clamp=True`), nunca se deja HOR negativo.
- Bug #4 (LEVANTAMIENTO SUSPENSIÓN sumaba a TOTAUS): CORREGIDO aquí: el
  levantamiento RESTA horas de TOTAUS.
- Bug #5 (rama muerta de `generar_observacion`): replicado (código, sin efecto).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from core.audit.writer import audit_scope
from core.config import get_settings
from core.db import sqlserver, supabase_client
from core.db.health import FUENTE_SUPABASE, fuente_por_defecto
from core.faltas import calculo as fc
from core.utils import normalizar_cedula

CODEMP = "10"
CODSUC = "10"

_TIPO_PGO = "3"
_TIPO_TRA = "1"


# ── DTOs ────────────────────────────────────────────────────────────────────


@dataclass
class EmpleadoFalta:
    empleado: str
    apellidos: str
    nombres: str
    cedula: str
    fecha_sal: str = ""
    seccion: str = ""

    @property
    def nombre(self) -> str:
        return f"{self.apellidos} {self.nombres}".strip()


@dataclass
class RegistroPeriodo:
    empleado: str
    nombre: str
    cedula: str
    totaus: float
    observ: str
    fecha_ven: str


@dataclass
class Vista:
    """Vista previa / resultado de una escritura."""
    ok: bool
    accion: str = ""            # INSERTADO | ACTUALIZADO | ELIMINADO | ...
    detalle: str = ""
    horas: int = 0
    observ: str = ""
    alerta: dict = field(default_factory=dict)
    descuento: dict = field(default_factory=dict)   # {pct, HOR25, HOR50, HOR100}
    ejecutado: bool = False
    error: str = ""


# ── helpers de lectura (dual: SQL Server + Supabase) ────────────────────────
#
# El módulo legado `gestion_faltas.py` solo leía SQL Server. En la web las
# lecturas respetan el selector de fuente (igual que `core/repos/observaciones.py`):
# el espejo de Supabase tiene `rphortot` / `rphorhis` / `rpemplea` (proyecto
# empleados-insevig). Las **escrituras** siguen yendo SOLO a SQL Server.


def _filtro() -> str:
    return get_settings().sqlserver_filter  # "CODEMP='10' AND CODSUC='10'"


def _fuente(fuente: str) -> str:
    return fuente or fuente_por_defecto()


def _sb():
    return supabase_client.get_client()


def _emp_de_dict(r: dict, *, sb: bool) -> EmpleadoFalta:
    g = (lambda k: r.get(k.lower())) if sb else (lambda k: r.get(k.upper()) if k.upper() in r else r.get(k))
    return EmpleadoFalta(
        empleado=str(g("empleado") or "").strip(),
        apellidos=str(g("apellidos") or "").strip(),
        nombres=str(g("nombres") or "").strip(),
        cedula=normalizar_cedula(g("cedula")),
        fecha_sal=str(g("fecha_sal") or "")[:10],
        seccion=str(g("seccion") or "").strip(),
    )


def buscar_empleado(*, codigo: str = "", cedula: str = "", fuente: str = "") -> EmpleadoFalta | None:
    """RPEMPLEA por código o cédula. Puerto de `buscar_empleado_bd`."""
    codigo, cedula = str(codigo).strip(), str(cedula).strip()
    if not codigo and not cedula:
        return None
    if _fuente(fuente) == FUENTE_SUPABASE:
        q = _sb().table("rpemplea").select(
            "empleado,apellidos,nombres,cedula,fecha_sal,seccion"
        ).eq("codemp", "10")
        q = q.eq("empleado", codigo) if codigo else q.eq("cedula", normalizar_cedula(cedula).lstrip("0"))
        filas = q.limit(1).execute().data or []
        return _emp_de_dict(filas[0], sb=True) if filas else None
    flt = _filtro()
    if codigo:
        rows = sqlserver.filas(
            f"SELECT EMPLEADO, APELLIDOS, NOMBRES, CEDULA, FECHA_SAL, SECCION "
            f"FROM dbo.RPEMPLEA WHERE {flt} AND EMPLEADO = ?", (codigo,),
        )
    else:
        rows = sqlserver.filas(
            f"SELECT EMPLEADO, APELLIDOS, NOMBRES, CEDULA, FECHA_SAL, SECCION "
            f"FROM dbo.RPEMPLEA WHERE {flt} AND CAST(CEDULA AS VARCHAR) = ?",
            (normalizar_cedula(cedula).lstrip("0"),),
        )
    return _emp_de_dict(rows[0], sb=False) if rows else None


def buscar_empleados_texto(termino: str, top: int = 20, fuente: str = "") -> list[EmpleadoFalta]:
    """Buscador de empleados (código o apellidos/nombres). Puerto de `buscar_empleados_texto`."""
    termino = (termino or "").strip()
    if not termino:
        return []
    top = max(1, min(int(top), 100))
    if _fuente(fuente) == FUENTE_SUPABASE:
        cols = "empleado,apellidos,nombres,cedula,seccion"
        q = _sb().table("rpemplea").select(cols).eq("codemp", "10")
        if termino.isdigit():
            q = q.ilike("empleado", f"%{termino}%")
        else:
            q = q.or_(f"apellidos.ilike.%{termino}%,nombres.ilike.%{termino}%")
        filas = q.limit(top).execute().data or []
        return [_emp_de_dict(r, sb=True) for r in filas]
    flt = _filtro()
    if termino.isdigit():
        rows = sqlserver.filas(
            f"SELECT TOP {top} EMPLEADO, APELLIDOS, NOMBRES, CEDULA, SECCION "
            f"FROM dbo.RPEMPLEA WHERE {flt} AND EMPLEADO LIKE ?", (f"%{termino}%",),
        )
    else:
        rows = sqlserver.filas(
            f"SELECT TOP {top} EMPLEADO, APELLIDOS, NOMBRES, CEDULA, SECCION "
            f"FROM dbo.RPEMPLEA WHERE {flt} AND (APELLIDOS LIKE ? OR NOMBRES LIKE ?)",
            (f"%{termino}%", f"%{termino}%"),
        )
    return [_emp_de_dict(r, sb=False) for r in rows]


def horas_extra_empleado(empleado: str, fuente: str = "") -> dict[str, int]:
    """HOR25/HOR50/HOR100 actuales. Puerto de `obtener_horas_extra_empleado`."""
    if _fuente(fuente) == FUENTE_SUPABASE:
        filas = (
            _sb().table("rpemplea").select("hor25,hor50,hor100")
            .eq("codemp", "10").eq("empleado", str(empleado)).limit(1).execute().data or []
        )
        r = filas[0] if filas else {}
        return {"HOR25": int(r.get("hor25") or 0), "HOR50": int(r.get("hor50") or 0),
                "HOR100": int(r.get("hor100") or 0)}
    flt = _filtro()
    rows = sqlserver.filas(
        f"SELECT ISNULL(HOR25,0) HOR25, ISNULL(HOR50,0) HOR50, ISNULL(HOR100,0) HOR100 "
        f"FROM dbo.RPEMPLEA WHERE {flt} AND EMPLEADO = ?", (str(empleado),),
    )
    if not rows:
        return {"HOR25": 0, "HOR50": 0, "HOR100": 0}
    r = rows[0]
    return {"HOR25": int(r.get("HOR25") or 0), "HOR50": int(r.get("HOR50") or 0),
            "HOR100": int(r.get("HOR100") or 0)}


def _seccion_empleado(empleado: str) -> str:
    flt = _filtro()
    rows = sqlserver.filas(
        f"SELECT SECCION FROM dbo.RPEMPLEA WHERE {flt} AND EMPLEADO = ?", (str(empleado),)
    )
    return str(rows[0].get("SECCION") or "").strip() if rows else ""


def _registro_existente(empleado: str, fecha_ven: date, fuente: str = "") -> dict | None:
    """RPHORTOT para (empleado, fecha_ven). Puerto de `verificar_existe`."""
    if _fuente(fuente) == FUENTE_SUPABASE:
        filas = (
            _sb().table("rphortot").select("totaus,observ")
            .eq("codemp", "10").eq("empleado", str(empleado))
            .eq("fecha_ven", fecha_ven.isoformat()).limit(1).execute().data or []
        )
        if not filas:
            return None
        return {"TOTAUS": filas[0].get("totaus") or 0, "OBSERV": filas[0].get("observ") or ""}
    flt = _filtro()
    rows = sqlserver.filas(
        f"SELECT TOTAUS, OBSERV FROM dbo.RPHORTOT "
        f"WHERE {flt} AND EMPLEADO = ? AND FECHA_VEN = ?", (str(empleado), fecha_ven),
    )
    if not rows:
        return None
    r = rows[0]
    return {"TOTAUS": r.get("TOTAUS") or 0, "OBSERV": r.get("OBSERV") or ""}


def listar_periodo(anio: int, mes: int, *, historicas: bool = False,
                   fuente: str = "") -> list[RegistroPeriodo]:
    """Registros TOTAUS>0 de un período. `historicas=True` → RPHORHIS (solo lectura).
    Puerto de `cargar_periodo_bd`.
    """
    fecha_ini = date(anio, mes, 1)
    fecha_fin = fc.obtener_fecha_fin_mes(anio, mes)

    if _fuente(fuente) == FUENTE_SUPABASE:
        sb = _sb()
        tabla = "rphorhis" if historicas else "rphortot"
        filas = (
            sb.table(tabla).select("empleado,totaus,observ,fecha_ven")
            .eq("codemp", "10").gt("totaus", 0)
            .gte("fecha_ven", fecha_ini.isoformat()).lte("fecha_ven", fecha_fin.isoformat())
            .limit(5000).execute().data or []
        )
        cods = list({str(f["empleado"]) for f in filas if f.get("empleado")})
        emap: dict[str, dict] = {}
        for i in range(0, len(cods), 200):
            for e in (sb.table("rpemplea").select("empleado,apellidos,nombres,cedula")
                      .eq("codemp", "10").in_("empleado", cods[i:i + 200]).execute().data or []):
                emap[str(e["empleado"])] = e
        out = []
        for f in filas:
            e = emap.get(str(f.get("empleado")), {})
            nombre = f"{(e.get('apellidos') or '').strip()} {(e.get('nombres') or '').strip()}".strip()
            out.append(RegistroPeriodo(
                empleado=str(f.get("empleado") or "").strip(),
                nombre=nombre or f"Emp {f.get('empleado')}",
                cedula=fc.formatear_cedula(e.get("cedula")),
                totaus=float(f.get("totaus") or 0),
                observ=str(f.get("observ") or ""),
                fecha_ven=str(f.get("fecha_ven") or "")[:10],
            ))
        out.sort(key=lambda r: r.nombre)
        return out

    tabla = "RPHORHIS" if historicas else "RPHORTOT"
    flt = _filtro().replace("CODEMP", "r.CODEMP").replace("CODSUC", "r.CODSUC")
    rows = sqlserver.filas(
        f"""SELECT r.EMPLEADO,
                   ISNULL(e.APELLIDOS,'') + ' ' + ISNULL(e.NOMBRES,'') AS NOMBRE,
                   ISNULL(CONVERT(VARCHAR(20), CAST(e.CEDULA AS BIGINT)),'') AS CEDULA,
                   r.TOTAUS, ISNULL(r.OBSERV,'') AS OBSERV, r.FECHA_VEN
            FROM dbo.{tabla} r
            LEFT JOIN dbo.RPEMPLEA e
              ON r.EMPLEADO=e.EMPLEADO AND r.CODEMP=e.CODEMP AND r.CODSUC=e.CODSUC
            WHERE {flt} AND r.FECHA_VEN >= ? AND r.FECHA_VEN <= ? AND r.TOTAUS > 0
            ORDER BY ISNULL(e.APELLIDOS,''), ISNULL(e.NOMBRES,'')""",
        (fecha_ini, fecha_fin),
    )
    return [
        RegistroPeriodo(
            empleado=str(r.get("EMPLEADO") or "").strip(),
            nombre=str(r.get("NOMBRE") or "").strip(),
            cedula=fc.formatear_cedula(r.get("CEDULA")),
            totaus=float(r.get("TOTAUS") or 0),
            observ=str(r.get("OBSERV") or ""),
            fecha_ven=str(r.get("FECHA_VEN") or "")[:10],
        )
        for r in rows
    ]


def historial_empleado(empleado: str, fuente: str = "") -> list[dict]:
    """RPHORHIS (TOTAUS>0) de un empleado, más reciente primero. Puerto de `cargar_historial_bd`."""
    if _fuente(fuente) == FUENTE_SUPABASE:
        filas = (
            _sb().table("rphorhis").select("fecha_ven,totaus,observ")
            .eq("codemp", "10").eq("empleado", str(empleado)).gt("totaus", 0)
            .order("fecha_ven", desc=True).execute().data or []
        )
        return [
            {"fecha_ven": str(f.get("fecha_ven") or "")[:10],
             "totaus": float(f.get("totaus") or 0), "observ": str(f.get("observ") or "")}
            for f in filas
        ]
    flt = _filtro()
    rows = sqlserver.filas(
        f"SELECT FECHA_VEN, TOTAUS, ISNULL(OBSERV,'') OBSERV FROM dbo.RPHORHIS "
        f"WHERE {flt} AND EMPLEADO = ? AND TOTAUS > 0 ORDER BY FECHA_VEN DESC", (str(empleado),),
    )
    return [
        {"fecha_ven": str(r.get("FECHA_VEN") or "")[:10],
         "totaus": float(r.get("TOTAUS") or 0), "observ": str(r.get("OBSERV") or "")}
        for r in rows
    ]


def empleados_por_cedulas(cedulas_norm: list[str], fuente: str = "") -> list[dict]:
    """RPEMPLEA para un lote de cédulas normalizadas (sin ceros a la izquierda).
    Puerto de `obtener_empleados_por_cedulas`. Devuelve dicts con CED_N.
    """
    cedulas = [c for c in {str(x).strip().lstrip("0") for x in cedulas_norm} if c]
    if not cedulas:
        return []
    out: list[dict] = []
    if _fuente(fuente) == FUENTE_SUPABASE:
        sb = _sb()
        for i in range(0, len(cedulas), 200):
            for e in (sb.table("rpemplea").select("empleado,cedula,apellidos,nombres,hor50,hor100")
                      .eq("codemp", "10").in_("cedula", cedulas[i:i + 200]).execute().data or []):
                out.append({
                    "EMPLEADO": str(e.get("empleado") or "").strip(),
                    "CEDULA": str(e.get("cedula") or ""),
                    "APELLIDOS": e.get("apellidos") or "", "NOMBRES": e.get("nombres") or "",
                    "HOR50": e.get("hor50") or 0, "HOR100": e.get("hor100") or 0,
                    "CED_N": str(e.get("cedula") or "").strip().lstrip("0"),
                })
        return out
    flt = _filtro().replace("CODEMP", "e.CODEMP").replace("CODSUC", "e.CODSUC")
    for i in range(0, len(cedulas), 500):
        chunk = cedulas[i:i + 500]
        marcas = ",".join("?" * len(chunk))
        rows = sqlserver.filas(
            f"""SELECT e.EMPLEADO, CONVERT(VARCHAR(20), CAST(e.CEDULA AS BIGINT)) AS CEDULA,
                       ISNULL(e.APELLIDOS,'') APELLIDOS, ISNULL(e.NOMBRES,'') NOMBRES,
                       ISNULL(e.HOR50,0) HOR50, ISNULL(e.HOR100,0) HOR100
                FROM dbo.RPEMPLEA e
                WHERE {flt} AND CONVERT(VARCHAR(20), CAST(e.CEDULA AS BIGINT)) IN ({marcas})
                ORDER BY e.APELLIDOS, e.NOMBRES""",
            tuple(chunk),
        )
        for r in rows:
            d = dict(r)
            d["EMPLEADO"] = str(d.get("EMPLEADO") or "").strip()
            d["CED_N"] = str(d.get("CEDULA") or "").strip().lstrip("0")
            out.append(d)
    return out


# ── escrituras ─────────────────────────────────────────────────────────────


def _insert_rphortot(empleado: str, fecha_ven: date, horas: int, observ: str, seccion: str) -> tuple[str, list]:
    q = (
        "INSERT INTO dbo.RPHORTOT "
        "(EMPLEADO,CODEMP,CODSUC,FECHA_VEN,FECHA_ULT,TOTAUS,OBSERV,SECCION,TIPO_PGO,TIPO_TRA) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)"
    )
    v = [str(empleado), CODEMP, CODSUC, fecha_ven, date.today(), horas, observ, seccion, _TIPO_PGO, _TIPO_TRA]
    return q, v


def _update_rphortot_suma(empleado: str, fecha_ven: date, horas_delta: int, observ: str,
                          fecha_ult: date) -> tuple[str, list]:
    q = (
        "UPDATE dbo.RPHORTOT SET TOTAUS=TOTAUS+?, OBSERV=?, FECHA_ULT=? "
        "WHERE EMPLEADO=? AND CODEMP=? AND CODSUC=? AND FECHA_VEN=?"
    )
    v = [horas_delta, observ, fecha_ult, str(empleado), CODEMP, CODSUC, fecha_ven]
    return q, v


def _update_rphortot_set(empleado: str, fecha_ven: date, totaus: float, observ: str) -> tuple[str, list]:
    q = (
        "UPDATE dbo.RPHORTOT SET TOTAUS=?, OBSERV=? "
        "WHERE EMPLEADO=? AND CODEMP=? AND CODSUC=? AND FECHA_VEN=?"
    )
    v = [totaus, observ, str(empleado), CODEMP, CODSUC, fecha_ven]
    return q, v


def registrar(
    empleado: str, tipo: str, cantidad: int, fecha_evento: str, anio: int, mes: int,
    observ_libre: str = "", *, seccion: str | None = None,
    descontar_horas_extra: bool = True, usuario: str = "", roles: set[str] | None = None,
    fuente: str = "", dry_run: bool = True,
) -> Vista:
    """Registra una FALTA / PERMISO / SUSPENSIÓN / LEVANTAMIENTO SUSPENSIÓN /
    PERMISO MÉDICO en RPHORTOT (inserta o acumula). Orquesta lo que en el legado
    hacían `_registrar_todo` (masivo) y `registrar_uno()` (uno a uno).

    `fecha_evento`: día del evento (DD/MM/YYYY o YYYY-MM-DD) — para SUSPENSIÓN es
    la fecha de inicio. `fecha_ven` = último día del período (anio, mes).
    Para SUSPENSIÓN, `cantidad` se ignora: los días salen de (fecha_ven - inicio) + 1.
    """
    roles = roles or set()
    tipo_u = tipo.strip().upper()
    f_evt = fc.parse_fecha(fecha_evento) if fecha_evento else None
    if f_evt is None:
        return Vista(False, error=f"Fecha del evento inválida: {fecha_evento!r}")
    fecha_ven = fc.obtener_fecha_fin_mes(anio, mes)
    fecha_str = f_evt.strftime("%d/%m/%Y")
    if seccion is None and not dry_run:
        seccion = _seccion_empleado(empleado)
    seccion = seccion or ""

    descuento: dict = {}
    if tipo_u == "SUSPENSIÓN":
        dias, horas = fc.calcular_suspension(f_evt, fecha_ven)  # bug #2: +1, correcto
        pct = fc.calcular_porcentaje_descuento_suspension(dias)
        d25 = d50 = d100 = 0
        if descontar_horas_extra and pct > 0:
            he = horas_extra_empleado(empleado, fuente)
            # bug #3 CORREGIDO: clamp=True siempre -> nunca HOR negativo
            d25, d50, d100 = fc.calcular_descuento_horas_extra(
                he["HOR25"], he["HOR50"], he["HOR100"], pct, clamp=True
            )
            descuento = {"pct": pct, "HOR25": d25, "HOR50": d50, "HOR100": d100}
        observ = fc.generar_observacion_suspension(fecha_str, dias, horas, observ_libre, pct, d25, d50, d100)
        signo = +1
    elif tipo_u == "LEVANTAMIENTO SUSPENSIÓN":
        horas = fc.calcular_horas_levantamiento_suspension(int(cantidad))
        observ = fc.generar_observacion_levantamiento(fecha_str, int(cantidad), horas, observ_libre or "")
        signo = -1  # bug #4 CORREGIDO: el levantamiento RESTA horas de TOTAUS
    else:
        horas, dias = fc.calcular_horas(tipo_u, int(cantidad))
        observ = fc.generar_observacion(tipo_u, int(cantidad), fecha_str, observ_libre, horas, dias)
        signo = +1

    if not fc.validar_longitud_observacion(observ):
        return Vista(False, error=f"La observación supera 255 caracteres ({len(observ)}).")

    existente = _registro_existente(empleado, fecha_ven, fuente)
    alerta: dict = {}
    if existente is not None:
        totaus_actual = float(existente["TOTAUS"] or 0)
        if tipo_u == "FALTA":
            alerta = fc.evaluar_alerta_faltas(int(totaus_actual), horas)
        observ = fc.concatenar_observ(existente["OBSERV"], observ)
        if not fc.validar_longitud_observacion(observ):
            return Vista(False, error=f"La observación concatenada supera 255 caracteres ({len(observ)}).")
        accion = "ACTUALIZADO"
        q, v = _update_rphortot_suma(empleado, fecha_ven, signo * horas, observ, f_evt)
    else:
        if signo < 0:
            return Vista(False, error="No hay registro previo del que restar horas.")
        accion = "INSERTADO"
        q, v = _insert_rphortot(empleado, fecha_ven, horas, observ, seccion)

    detalle = f"{tipo_u} · {horas}h · {accion} · vence {fecha_ven:%d/%m/%Y}"
    if dry_run:
        return Vista(True, accion=accion, detalle=detalle, horas=horas, observ=observ,
                     alerta=alerta, descuento=descuento)

    with audit_scope(
        "faltas", "crear", usuario=usuario, roles=roles,
        target_table="RPHORTOT", target_key=f"{empleado}/{fecha_ven}",
        antes=existente, after={"tipo": tipo_u, "horas": signo * horas, "observ": observ},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        if accion == "INSERTADO" and not seccion:
            cur.execute(
                f"SELECT SECCION FROM dbo.RPEMPLEA WHERE {_filtro()} AND EMPLEADO = ?", (str(empleado),)
            )
            row = cur.fetchone()
            v[7] = str(row[0]).strip() if row and row[0] else ""
        cur.execute(q, v)
        if descuento:
            cur.execute(
                f"UPDATE dbo.RPEMPLEA SET HOR25=HOR25-?, HOR50=HOR50-?, HOR100=HOR100-? "
                f"WHERE {_filtro()} AND EMPLEADO = ?",
                (descuento["HOR25"], descuento["HOR50"], descuento["HOR100"], str(empleado)),
            )
        conn.commit()
    return Vista(True, accion=accion, detalle=detalle, horas=horas, observ=observ,
                alerta=alerta, descuento=descuento, ejecutado=True)


def editar_registro(
    empleado: str, fecha_ven: str, totaus_nuevo: float, observ_nuevo: str,
    *, usuario: str = "", roles: set[str] | None = None, dry_run: bool = True,
) -> Vista:
    """Fija TOTAUS/OBSERV de un registro RPHORTOT (edición manual). Solo período
    abierto. Puerto de `_editar_seleccionado` → `actualizar_totaus_observ`.
    """
    roles = roles or set()
    fv = fc.parse_fecha(fecha_ven)
    if fv is None:
        return Vista(False, error=f"Fecha de vencimiento inválida: {fecha_ven!r}")
    if not fc.validar_longitud_observacion(observ_nuevo):
        return Vista(False, error=f"La observación supera 255 caracteres ({len(observ_nuevo)}).")
    existente = _registro_existente(empleado, fv)
    if existente is None:
        return Vista(False, error="No existe un registro para ese empleado/período.")
    q, v = _update_rphortot_set(empleado, fv, totaus_nuevo, observ_nuevo)
    if dry_run:
        return Vista(True, accion="ACTUALIZADO", detalle=f"TOTAUS → {totaus_nuevo}", observ=observ_nuevo)
    with audit_scope(
        "faltas", "editar", usuario=usuario, roles=roles,
        target_table="RPHORTOT", target_key=f"{empleado}/{fv}",
        antes=existente, after={"TOTAUS": totaus_nuevo, "OBSERV": observ_nuevo},
    ), sqlserver.conexion(write=True) as conn:
        conn.cursor().execute(q, v)
        conn.commit()
    return Vista(True, accion="ACTUALIZADO", detalle=f"TOTAUS → {totaus_nuevo}",
                observ=observ_nuevo, ejecutado=True)


def eliminar_registro(
    empleado: str, fecha_ven: str, *, usuario: str = "", roles: set[str] | None = None,
    dry_run: bool = True,
) -> Vista:
    """Eliminación lógica (TOTAUS=0, OBSERV='') de un registro RPHORTOT. Solo
    período abierto. Puerto de `eliminar_falta`.
    """
    roles = roles or set()
    fv = fc.parse_fecha(fecha_ven)
    if fv is None:
        return Vista(False, error=f"Fecha de vencimiento inválida: {fecha_ven!r}")
    existente = _registro_existente(empleado, fv)
    if existente is None:
        return Vista(False, error="No existe un registro para ese empleado/período.")
    q = ("UPDATE dbo.RPHORTOT SET TOTAUS=0, OBSERV='' "
         "WHERE EMPLEADO=? AND CODEMP=? AND CODSUC=? AND FECHA_VEN=?")
    v = [str(empleado), CODEMP, CODSUC, fv]
    if dry_run:
        return Vista(True, accion="ELIMINADO", detalle=f"{empleado} · {fv:%d/%m/%Y}")
    with audit_scope(
        "faltas", "eliminar", usuario=usuario, roles=roles,
        target_table="RPHORTOT", target_key=f"{empleado}/{fv}", antes=existente,
    ), sqlserver.conexion(write=True) as conn:
        conn.cursor().execute(q, v)
        conn.commit()
    return Vista(True, accion="ELIMINADO", detalle=f"{empleado} · {fv:%d/%m/%Y}", ejecutado=True)


def aplicar_restas(
    resultados: list[dict], *, usuario: str = "", roles: set[str] | None = None,
    dry_run: bool = True,
) -> dict:
    """Aplica el resultado del Cargador de Restas de Horas: fija HOR50/HOR100 de
    cada empleado con estado OK. Puerto de `_ejecutar_restas` → `aplicar_resta_horas`.
    `resultados` = salida de `core.faltas.calculo.calcular_resultados_resta`.
    """
    roles = roles or set()
    aplicables = [r for r in resultados if r.get("ESTADO") == "OK" and r.get("EMPLEADO")]
    resumen = {"aplicables": len(aplicables), "aplicados": 0, "omitidos": len(resultados) - len(aplicables)}
    if dry_run or not aplicables:
        return resumen
    with audit_scope(
        "faltas", "cargar_masivo", usuario=usuario, roles=roles,
        target_table="RPEMPLEA", target_key="restas-horas",
        after={"n": len(aplicables)},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        for r in aplicables:
            cur.execute(
                f"UPDATE dbo.RPEMPLEA SET HOR50=?, HOR100=? WHERE {_filtro()} AND EMPLEADO = ?",
                (r["HOR50_NUEVO"], r["HOR100_NUEVO"], str(r["EMPLEADO"])),
            )
            resumen["aplicados"] += 1
        conn.commit()
    return resumen
