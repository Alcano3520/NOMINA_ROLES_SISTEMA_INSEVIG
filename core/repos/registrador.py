"""Registro de egresos/ingresos en RPINGDES — puerto completo de
`registrdor_vizulizador_egresosingresos/REGISTRAR_PRESTAMOS_UNIFICADO.pyw`.

Cubre las 6 pestañas del sistema anterior:
  1. Préstamo individual (CLASE 205, con planificación de cuotas)
  2. Carga masiva de préstamos
  3. Egresos / Ingresos (todos los tipos de `CLASES_SIMPLIFICADAS`)
  4. Registro individual (un movimiento de cualquier tipo)
  5. BIESS quirografarios (Excel -> CLASE 204)
  6. Consulta / edición de movimientos existentes

Escrituras SOLO a SQL Server, con vista previa (dry_run) + `AuditWriter`.
Números de movimiento desde RPCONTRL (ULT_EGR / ULT_ING).
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass, field

from core.audit.writer import audit_scope
from core.config import get_settings
from core.db import sqlserver, supabase_client
from core.db.health import FUENTE_SUPABASE
from core.utils import a_float, normalizar_cedula

CLASE_PRESTAMO = "205"
CLASE_QUIROGRAFARIO = 204  # compat BIESS

# CLASE -> configuración del INSERT (del legado: CLASES_SIMPLIFICADAS).
CLASES_SIMPLIFICADAS: dict[str, dict] = {
    "250": {"concepto": "ANTICIPOS SURTIDOS", "codigo": "EGR", "tipo": "EGR", "aporta": 0},
    "219": {"concepto": "IMPUESTO A LA RENTA", "codigo": "EGR", "tipo": "EGR", "aporta": 0},
    "218": {"concepto": "APORT.IESS CONYUGE", "codigo": "EGR", "tipo": "EGR", "aporta": 1},
    "206": {"concepto": "PENSION ALIMENTICIA", "codigo": "EGR", "tipo": "EGR", "aporta": 0},
    "203": {"concepto": "MULTAS", "codigo": "EGR", "tipo": "EGR", "aporta": 0},
    "202": {"concepto": "ANTICIPO DE SUELDO", "codigo": "EGR", "tipo": "EGR", "aporta": 0},
    "204": {"concepto": "PRESTAMOS QUIROGRAFARIOS", "codigo": "EGR", "tipo": "EGR", "aporta": 0},
    "207": {"concepto": "PRESTAMO HIPOTECARIO", "codigo": "EGR", "tipo": "EGR", "aporta": 0},
    "217": {"concepto": "ANTICIPOS OTROS", "codigo": "EGR", "tipo": "EGR", "aporta": 0},
    "102": {"concepto": "BONIFICACION OTROS INGRESOS", "codigo": "ING", "tipo": "ING", "aporta": 1},
    "120": {"concepto": "MOVILIZACION", "codigo": "ING", "tipo": "ING", "aporta": 0},
    "111": {"concepto": "REEMBOLSOS", "codigo": "ING", "tipo": "ING", "aporta": 0},
    "110": {"concepto": "MANIOBRAS", "codigo": "ING", "tipo": "ING", "aporta": 1},
}


# Etiqueta libre que se antepone a la observación (del legado: TIPOS_TRANSACCION).
# El legado guardaba el código interno (ej. "PRESTAMO_PRE01"); aquí se guarda la
# etiqueta legible, más útil para quien lea la observación después.
TIPOS_TRANSACCION: dict[str, str] = {
    "": "(Sin tipo)",
    "PRESTAMO": "Préstamo",
    "DESCUENTO": "Descuento",
    "EGRESO": "Egreso",
    "DEVOLUCION": "Devolución",
    "CUADRE": "Cuadre",
    "DES_LIQUIDACION": "Descuento liquidación",
    "CRUCE": "Cruce",
}

NOMBRE_CLASE: dict[str, str] = {
    "205": "Préstamo", "202": "Anticipo de sueldo", "203": "Multa",
    "204": "Quirografario", "206": "Pensión alimenticia", "207": "Préstamo hipotecario",
    "217": "Anticipos otros", "218": "IESS cónyuge", "219": "Impuesto a la renta",
    "250": "Anticipos surtidos", "102": "Bonificación", "110": "Maniobras",
    "111": "Reembolsos", "120": "Movilización",
}

# Constantes del INSERT de préstamo (del legado).
_CODIGO_PRESTAMO = "EGR"
_CONCEPTO_PRESTAMO = "PRESTAMOS COMPAÑIA"
_APORTA_FIJO = 0
_TIPO_PGO_FIJO = 3
_TIPO_TRA_FIJO = 1


# ── Cálculo de cuotas ────────────────────────────────────────────────────────


@dataclass
class Cuota:
    secuencia: int
    fecha_vencimiento: str  # YYYY-MM-DD (último día del mes)
    valor: float


def _ultimo_dia(anio: int, mes: int) -> dt.date:
    return dt.date(anio, mes, calendar.monthrange(anio, mes)[1])


def _mes_siguiente(anio: int, mes: int) -> tuple[int, int]:
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def cuotas_tradicional(valor_total: float, num_cuotas: int, fecha_inicio: dt.date) -> list[Cuota]:
    """N cuotas iguales; el ajuste de redondeo va en la primera."""
    if valor_total <= 0 or num_cuotas <= 0:
        raise ValueError("Valor total y número de cuotas deben ser positivos")
    vc = round(valor_total / num_cuotas, 2)
    ajuste = round(valor_total - vc * num_cuotas, 2)
    out: list[Cuota] = []
    anio, mes = fecha_inicio.year, fecha_inicio.month
    for i in range(num_cuotas):
        val = vc + ajuste if (i == 0 and ajuste) else vc
        out.append(Cuota(i + 1, _ultimo_dia(anio, mes).isoformat(), round(val, 2)))
        anio, mes = _mes_siguiente(anio, mes)
    return out


def cuotas_por_valor(
    valor_total: float, cuota_mensual: float, fecha_inicio: dt.date,
    proyeccion_existente: dict[tuple[int, int], float] | None = None,
) -> tuple[list[Cuota], str]:
    """Planificación inteligente: cuotas de `cuota_mensual` respetando lo que el
    empleado ya tiene programado ese mes (proyeccion_existente {(anio,mes): valor}).
    """
    if valor_total <= 0 or cuota_mensual <= 0:
        raise ValueError("Valores inválidos")
    proy = proyeccion_existente or {}
    saldo = round(float(valor_total), 2)
    cuota_mensual = round(float(cuota_mensual), 2)
    out: list[Cuota] = []
    sec = 1
    anio, mes = fecha_inicio.year, fecha_inicio.month
    for _ in range(600):
        if saldo <= 0.005:
            break
        carga = round(proy.get((anio, mes), 0.0), 2)
        espacio = max(0.0, cuota_mensual - carga)
        vc = round(min(saldo, espacio), 2)
        if vc > 0.005:
            out.append(Cuota(sec, _ultimo_dia(anio, mes).isoformat(), vc))
            saldo = round(saldo - vc, 2)
            sec += 1
        anio, mes = _mes_siguiente(anio, mes)
    aviso = ""
    if saldo > 0.005:
        aviso = f"Queda un saldo de {saldo:.2f}: la cuota es muy baja frente a lo ya programado."
    return out, aviso


def proyeccion_pagos_futuros(empleado: str, fuente: str, desde: dt.date | None = None) -> dict[tuple[int, int], float]:
    """Suma de cuotas de préstamo (CLASE 205, ASENTADO=0) pendientes por mes."""
    desde = (desde or dt.date.today()).replace(day=1)
    out: dict[tuple[int, int], float] = {}
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        filas = (
            sb.table("rpingdesres").select("fecha_ven,valor")
            .eq("codemp", "10").eq("empleado", str(empleado)).eq("clase", 205).eq("asentado", 0)
            .gte("fecha_ven", desde.isoformat()).execute().data or []
        )
    else:
        flt = get_settings().sqlserver_filter
        filas = sqlserver.filas(
            f"""SELECT FECHA_VEN, VALOR FROM dbo.RPINGDES
                WHERE {flt} AND EMPLEADO = ? AND CLASE = '205' AND ASENTADO = 0
                  AND FECHA_VEN >= ?""",
            (str(empleado), desde.isoformat()),
        )
    for r in filas:
        fv = str(r.get("FECHA_VEN") or r.get("fecha_ven") or "")[:10]
        if len(fv) < 7:
            continue
        y, m = int(fv[:4]), int(fv[5:7])
        out[(y, m)] = round(out.get((y, m), 0.0) + a_float(r.get("VALOR") or r.get("valor")), 2)
    return out


# ── Consulta de movimientos (pestañas 3 y 6) ─────────────────────────────────


@dataclass
class MovimientoRegistrado:
    numero: str
    clase: str
    tipo_clase: str
    empleado: str
    nombre: str
    fecha: str
    valor: float
    cuotas: int
    concepto: str
    asentado: bool = False


def historial_movimientos(
    fuente: str, filtro: str = "", limite: int = 200, *, empleado: str = "",
) -> list[MovimientoRegistrado]:
    """Movimientos de RPINGDES (ASENTADO=0) agrupados por NUMERO. Para préstamos
    (205) agrupa las cuotas en una fila con el total. Filtro por número o nombre;
    `empleado` (código exacto) restringe al panel de un empleado."""
    filtro = (filtro or "").strip()
    empleado = str(empleado or "").strip()
    out: list[MovimientoRegistrado] = []
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        cols = "numero,clase,empleado,fecha,valor,observ,concepto"
        q = sb.table("rpingdesres").select(cols).eq("codemp", "10").eq("asentado", 0)
        if empleado:
            q = q.eq("empleado", empleado)
        if filtro.isdigit():
            q = q.eq("numero", int(filtro))
        filas = q.order("fecha", desc=True).limit(2000).execute().data or []
        emps = {
            str(x["empleado"]).strip(): x
            for x in (sb.table("rpemplea").select("empleado,apellidos,nombres").eq("codemp", "10").execute().data or [])
        }
        grp: dict[tuple, dict] = {}
        for r in filas:
            k = (str(r.get("numero")), str(r.get("clase")), str(r.get("empleado")))
            g = grp.setdefault(k, {"fecha": r.get("fecha"), "valor": 0.0, "cuotas": 0,
                                   "observ": r.get("observ"), "concepto": r.get("concepto")})
            g["valor"] += a_float(r.get("valor"))
            g["cuotas"] += 1
        for (num, clase, emp), g in grp.items():
            e = emps.get(str(emp).strip(), {})
            nombre = f"{(e.get('apellidos') or '').strip()} {(e.get('nombres') or '').strip()}".strip() or f"Emp {emp}"
            if filtro and not filtro.isdigit() and filtro.lower() not in nombre.lower():
                continue
            out.append(_mov_reg(num, clase, emp, nombre, g))
        out.sort(key=lambda m: m.numero, reverse=True)
        return out[:limite]

    flt = get_settings().sqlserver_filter
    params: list = []
    cond = ""
    if empleado:
        cond += " AND r.EMPLEADO = ?"
        params.append(empleado)
    if filtro:
        if filtro.isdigit():
            cond += " AND (CAST(r.NUMERO AS VARCHAR) LIKE ? OR CAST(r.EMPLEADO AS VARCHAR) LIKE ?)"
            params += [f"%{filtro}%", f"%{filtro}%"]
        else:
            cond += " AND (e.APELLIDOS LIKE ? OR e.NOMBRES LIKE ?)"
            params += [f"%{filtro}%", f"%{filtro}%"]
    filas = sqlserver.filas(
        f"""SELECT TOP {limite} r.NUMERO, r.CLASE, r.EMPLEADO,
                   MIN(r.FECHA) FECHA_EMISION, SUM(r.VALOR) VALOR_TOTAL, COUNT(*) CUOTAS,
                   MAX(r.OBSERV) OBSERV, MAX(r.CONCEPTO) CONCEPTO, e.APELLIDOS, e.NOMBRES
            FROM dbo.RPINGDES r
            LEFT JOIN dbo.RPEMPLEA e ON r.EMPLEADO = e.EMPLEADO
            WHERE r.ASENTADO = 0 AND {flt.replace('CODEMP', 'r.CODEMP').replace('CODSUC', 'r.CODSUC')}
            {cond}
            GROUP BY r.NUMERO, r.CLASE, r.EMPLEADO, e.APELLIDOS, e.NOMBRES
            ORDER BY MAX(r.FECHA) DESC, r.NUMERO DESC""",
        tuple(params),
    )
    for r in filas:
        ap = (r.get("APELLIDOS") or "").strip()
        no = (r.get("NOMBRES") or "").strip()
        nombre = f"{ap} {no}".strip() or f"Emp {r.get('EMPLEADO')}"
        out.append(_mov_reg(
            str(r.get("NUMERO")), str(r.get("CLASE") or "").strip(), str(r.get("EMPLEADO")).strip(), nombre,
            {"fecha": r.get("FECHA_EMISION"), "valor": a_float(r.get("VALOR_TOTAL")),
             "cuotas": int(r.get("CUOTAS") or 1), "observ": r.get("OBSERV"), "concepto": r.get("CONCEPTO")},
        ))
    return out


def _mov_reg(num: str, clase: str, emp: str, nombre: str, g: dict) -> MovimientoRegistrado:
    fecha = str(g["fecha"] or "")[:10]
    concepto = (str(g.get("concepto") or "").strip() or str(g.get("observ") or "").strip())
    return MovimientoRegistrado(
        numero=str(num).strip(), clase=clase, tipo_clase=NOMBRE_CLASE.get(clase, clase),
        empleado=str(emp).strip(), nombre=nombre, fecha=fecha,
        valor=round(g["valor"], 2), cuotas=int(g["cuotas"]), concepto=concepto,
    )


@dataclass
class FilaMovimiento:
    """Una fila individual de RPINGDES (para la consulta detallada del legado)."""
    numero: str
    empleado: str
    nombre: str
    secuencia: int
    clase: str
    tipo_clase: str
    fecha_ven: str
    valor: float
    concepto: str
    observ: str
    asentado: bool


def consultar_filas(
    fuente: str, *, empleado: str = "", clase: str = "", desde: str = "", hasta: str = "",
    numero: str = "", solo_pendientes: bool = False, limite: int = 3000,
) -> list[FilaMovimiento]:
    """Filas individuales de RPINGDES con los filtros de la pestaña Consulta del
    legado: empleado (código o nombre), clase, rango de FECHA_VEN, número, y
    'solo no procesados' (ASENTADO=0)."""
    empleado, clase, numero = empleado.strip(), clase.strip(), numero.strip()
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        q = sb.table("rpingdesres").select(
            "numero,empleado,secuencia,clase,fecha_ven,valor,concepto,observ,asentado"
        ).eq("codemp", "10")
        if clase:
            q = q.eq("clase", int(clase) if clase.isdigit() else clase)
        if numero.isdigit():
            q = q.eq("numero", int(numero))
        if empleado.isdigit():
            q = q.eq("empleado", empleado)
        if solo_pendientes:
            q = q.eq("asentado", 0)
        if desde:
            q = q.gte("fecha_ven", desde)
        if hasta:
            q = q.lte("fecha_ven", hasta)
        filas = q.order("fecha_ven", desc=True).limit(limite).execute().data or []
        emps = {
            str(x["empleado"]).strip(): x
            for x in (sb.table("rpemplea").select("empleado,apellidos,nombres").eq("codemp", "10").execute().data or [])
        }
        out: list[FilaMovimiento] = []
        for r in filas:
            emp = str(r.get("empleado") or "").strip()
            e = emps.get(emp, {})
            nombre = f"{(e.get('apellidos') or '').strip()} {(e.get('nombres') or '').strip()}".strip() or f"Emp {emp}"
            if empleado and not empleado.isdigit() and empleado.lower() not in nombre.lower():
                continue
            out.append(_fila_mov(r, nombre, sb_keys=True))
        return out

    flt = get_settings().sqlserver_filter
    where = [flt.replace("CODEMP", "r.CODEMP").replace("CODSUC", "r.CODSUC")]
    params: list = []
    if empleado:
        if empleado.isdigit():
            where.append("r.EMPLEADO = ?")
            params.append(int(empleado))
        else:
            where.append("(e.APELLIDOS LIKE ? OR e.NOMBRES LIKE ?)")
            params += [f"%{empleado}%", f"%{empleado}%"]
    if clase:
        where.append("r.CLASE = ?")
        params.append(clase)
    if solo_pendientes:
        where.append("r.ASENTADO = 0")
    if desde:
        where.append("r.FECHA_VEN >= ?")
        params.append(desde)
    if hasta:
        where.append("r.FECHA_VEN <= ?")
        params.append(hasta)
    if numero.isdigit():
        where.append("r.NUMERO = ?")
        params.append(int(numero))
    filas = sqlserver.filas(
        f"""SELECT TOP {limite} r.NUMERO, r.EMPLEADO, r.SECUENCIA, r.CLASE, r.FECHA_VEN,
                   r.VALOR, r.OBSERV, r.CONCEPTO, r.ASENTADO, e.APELLIDOS, e.NOMBRES
            FROM dbo.RPINGDES r
            LEFT JOIN dbo.RPEMPLEA e ON r.EMPLEADO = e.EMPLEADO
            WHERE {' AND '.join(where)}
            ORDER BY r.FECHA_VEN DESC, r.NUMERO DESC, r.SECUENCIA""",
        tuple(params),
    )
    salida: list[FilaMovimiento] = []
    for r in filas:
        ap = (r.get("APELLIDOS") or "").strip()
        no = (r.get("NOMBRES") or "").strip()
        nombre = f"{ap} {no}".strip() or f"Emp {r.get('EMPLEADO')}"
        salida.append(_fila_mov(r, nombre, sb_keys=False))
    return salida


def _fila_mov(r: dict, nombre: str, *, sb_keys: bool) -> FilaMovimiento:
    g = (lambda k: r.get(k.lower())) if sb_keys else (lambda k: r.get(k.upper()) or r.get(k))
    clase = str(g("CLASE") or "").strip()
    return FilaMovimiento(
        numero=str(g("NUMERO") or "").strip(),
        empleado=str(g("EMPLEADO") or "").strip(),
        nombre=nombre,
        secuencia=int(g("SECUENCIA") or 1),
        clase=clase,
        tipo_clase=NOMBRE_CLASE.get(clase, clase),
        fecha_ven=str(g("FECHA_VEN") or "")[:10],
        valor=round(a_float(g("VALOR")), 2),
        concepto=str(g("CONCEPTO") or "").strip(),
        observ=str(g("OBSERV") or "").strip(),
        asentado=bool(g("ASENTADO")),
    )


def editar_valor_fila(
    numero: str, empleado: str, clase: str, secuencia: int, fecha_ven: str, nuevo_valor: float,
    *, usuario: str, roles: set[str],
) -> int:
    """UPDATE del VALOR de una fila NO asentada de RPINGDES (pestaña Consulta → 'Editar valor')."""
    val = round(a_float(nuevo_valor), 2)
    if val <= 0:
        raise ValueError("El valor debe ser mayor que 0.")
    flt = get_settings().sqlserver_filter
    with audit_scope(
        "registrador", "registrar_rpingdes", usuario=usuario, roles=roles,
        target_table="RPINGDES", target_key=f"{numero}/{empleado}/{clase}/{secuencia}",
        after={"valor": val},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        cur.execute(
            f"""UPDATE dbo.RPINGDES SET VALOR = ?
                WHERE {flt} AND NUMERO = ? AND EMPLEADO = ? AND CLASE = ?
                  AND SECUENCIA = ? AND ASENTADO = 0""",
            (val, numero, str(empleado), clase, secuencia),
        )
        n = cur.rowcount
        conn.commit()
    return n


def eliminar_fila(
    numero: str, empleado: str, clase: str, secuencia: int, fecha_ven: str,
    *, usuario: str, roles: set[str],
) -> int:
    """DELETE de UNA fila NO asentada de RPINGDES (pestaña Consulta → 'Eliminar fila').
    Para préstamos borra solo esa cuota."""
    flt = get_settings().sqlserver_filter
    with audit_scope(
        "registrador", "registrar_rpingdes", usuario=usuario, roles=roles,
        target_table="RPINGDES", target_key=f"{numero}/{empleado}/{clase}/{secuencia}",
        antes={"numero": numero, "clase": clase, "empleado": empleado, "secuencia": secuencia},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        cur.execute(
            f"""DELETE FROM dbo.RPINGDES
                WHERE {flt} AND NUMERO = ? AND EMPLEADO = ? AND CLASE = ?
                  AND SECUENCIA = ? AND ASENTADO = 0""",
            (numero, str(empleado), clase, secuencia),
        )
        n = cur.rowcount
        conn.commit()
    return n


def cuotas_prestamo(numero: str, empleado: str, fuente: str) -> list[dict]:
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        filas = (
            sb.table("rpingdesres").select("secuencia,fecha_ven,valor,asentado,observ")
            .eq("codemp", "10").eq("numero", int(numero)).eq("empleado", str(empleado)).eq("clase", 205)
            .order("secuencia").execute().data or []
        )
        return [
            {"secuencia": int(r.get("secuencia") or 0), "fecha_ven": str(r.get("fecha_ven") or "")[:10],
             "valor": a_float(r.get("valor")), "asentado": bool(r.get("asentado")),
             "observ": (r.get("observ") or "").strip()}
            for r in filas
        ]
    flt = get_settings().sqlserver_filter
    filas = sqlserver.filas(
        f"""SELECT SECUENCIA, FECHA_VEN, VALOR, ASENTADO, OBSERV FROM dbo.RPINGDES
            WHERE {flt} AND NUMERO = ? AND EMPLEADO = ? AND CLASE = '205' ORDER BY SECUENCIA""",
        (numero, str(empleado)),
    )
    return [
        {"secuencia": int(r.get("SECUENCIA") or 0), "fecha_ven": str(r.get("FECHA_VEN") or "")[:10],
         "valor": a_float(r.get("VALOR")), "asentado": bool(r.get("ASENTADO")),
         "observ": (r.get("OBSERV") or "").strip()}
        for r in filas
    ]


# ── Escritura ────────────────────────────────────────────────────────────────


def _depto_seccion(cur, empleado: str) -> tuple[str, str]:
    cur.execute("SELECT DEPTO, SECCION FROM dbo.RPEMPLEA WHERE EMPLEADO = ?", (str(empleado),))
    r = cur.fetchone()
    if not r:
        raise LookupError(f"Empleado {empleado} no existe en RPEMPLEA")
    return (str(r[0] or "").strip(), str(r[1] or "").strip())


def _proximo_numero(cur, tipo: str) -> int:
    col = "ULT_ING" if tipo == "ING" else "ULT_EGR"
    cur.execute(f"SELECT {col} FROM dbo.RPCONTRL WITH (UPDLOCK, HOLDLOCK)")
    r = cur.fetchone()
    if not r or r[0] is None:
        raise RuntimeError(f"RPCONTRL sin {col}")
    return int(r[0]) + 1


def _fijar_numero(cur, tipo: str, numero: int) -> None:
    col = "ULT_ING" if tipo == "ING" else "ULT_EGR"
    cur.execute(f"UPDATE dbo.RPCONTRL SET {col} = ?", (numero,))


_INSERT_RPINGDES = """INSERT INTO dbo.RPINGDES (
    NUMERO, EMPLEADO, SECUENCIA, CLASE, FECHA, FECHA_VEN, VALOR, OBSERV,
    CODSUC, CODEMP, DEPTO, SECCION, ASENTADO, ACTUALIZA, APORTA, TIPO_PGO, TIPO_TRA, CODIGO,
    CONCEPTO, MONTO, DIVIDENDO
) VALUES (?, ?, ?, '{clase}', ?, ?, ?, ?, '10', '10', ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?)"""


@dataclass
class ResultadoRegistro:
    ok: bool
    numero: int = 0
    detalle: str = ""
    cuotas: list[Cuota] = field(default_factory=list)


def registrar_prestamo(
    empleado: str, valor_total: float, fecha_emision: str, observacion: str, cuotas: list[Cuota],
    *, usuario: str, roles: set[str], dry_run: bool = True,
) -> ResultadoRegistro:
    """Inserta un préstamo CLASE 205 (una fila por cuota) en RPINGDES."""
    if not cuotas:
        return ResultadoRegistro(False, detalle="Sin cuotas")
    total_cuotas = round(sum(c.valor for c in cuotas), 2)
    if abs(total_cuotas - round(valor_total, 2)) > 0.05:
        return ResultadoRegistro(False, detalle=f"Las cuotas suman {total_cuotas}, no {valor_total}")
    obs = (observacion or "")[:700]
    if dry_run:
        return ResultadoRegistro(True, detalle=f"{len(cuotas)} cuotas por {total_cuotas:.2f}", cuotas=cuotas)
    with audit_scope(
        "registrador", "registrar_rpingdes", usuario=usuario, roles=roles,
        target_table="RPINGDES", target_key=str(empleado),
        after={"clase": "205", "total": total_cuotas, "cuotas": len(cuotas)},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        depto, seccion = _depto_seccion(cur, empleado)
        numero = _proximo_numero(cur, "EGR")
        for c in cuotas:
            cur.execute(
                _INSERT_RPINGDES.format(clase="205"),
                (numero, str(empleado), c.secuencia, fecha_emision, c.fecha_vencimiento,
                 c.valor, obs, depto, seccion, _APORTA_FIJO, _TIPO_PGO_FIJO, _TIPO_TRA_FIJO,
                 _CODIGO_PRESTAMO, _CONCEPTO_PRESTAMO, round(valor_total, 2), len(cuotas)),
            )
        _fijar_numero(cur, "EGR", numero)
        conn.commit()
    return ResultadoRegistro(
        True, numero=numero,
        detalle=f"Préstamo N° {numero:05d} · {len(cuotas)} cuotas", cuotas=cuotas,
    )


def registrar_movimiento(
    empleado: str, clase: str, valor: float, fecha: str, observacion: str,
    *, usuario: str, roles: set[str], dry_run: bool = True,
) -> ResultadoRegistro:
    """Inserta un movimiento simple (multa, anticipo, bonificación, …) en RPINGDES."""
    if clase not in CLASES_SIMPLIFICADAS:
        return ResultadoRegistro(False, detalle=f"Clase {clase} no soportada")
    cfg = CLASES_SIMPLIFICADAS[clase]
    valor = round(a_float(valor), 2)
    if valor <= 0:
        return ResultadoRegistro(False, detalle="El valor debe ser mayor que 0")
    obs = (observacion or "")[:700]
    if dry_run:
        return ResultadoRegistro(True, detalle=f"{NOMBRE_CLASE.get(clase, clase)} · {valor:.2f} · {cfg['tipo']}")
    with audit_scope(
        "registrador", "registrar_rpingdes", usuario=usuario, roles=roles,
        target_table="RPINGDES", target_key=str(empleado),
        after={"clase": clase, "valor": valor},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        depto, seccion = _depto_seccion(cur, empleado)
        numero = _proximo_numero(cur, cfg["tipo"])
        cur.execute(
            _INSERT_RPINGDES.format(clase=clase),
            (numero, str(empleado), 1, fecha, fecha, valor, obs, depto, seccion,
             cfg["aporta"], 3, 1, cfg["codigo"], cfg["concepto"], valor, 1),
        )
        _fijar_numero(cur, cfg["tipo"], numero)
        conn.commit()
    return ResultadoRegistro(True, numero=numero, detalle=f"N° {numero:05d} · {NOMBRE_CLASE.get(clase, clase)}")


def eliminar_movimiento(numero: str, empleado: str, clase: str, *, usuario: str, roles: set[str]) -> int:
    """Borra todas las filas (cuotas) NO asentadas de un movimiento. Devuelve cuántas borró."""
    flt = get_settings().sqlserver_filter
    with audit_scope(
        "registrador", "registrar_rpingdes", usuario=usuario, roles=roles,
        target_table="RPINGDES", target_key=f"{numero}/{empleado}",
        antes={"numero": numero, "clase": clase, "empleado": empleado},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        cur.execute(
            f"""DELETE FROM dbo.RPINGDES
                WHERE {flt} AND NUMERO = ? AND EMPLEADO = ? AND CLASE = ? AND ASENTADO = 0""",
            (numero, str(empleado), clase),
        )
        n = cur.rowcount
        conn.commit()
    return n


def mover_cuotas_pendientes(
    numero: str, empleado: str, nueva_fecha_inicio: str, *, usuario: str, roles: set[str],
) -> int:
    """Reprograma TODAS las cuotas NO asentadas de un préstamo para que empiecen en
    `nueva_fecha_inicio` (último día de ese mes) y sigan mes a mes, conservando los
    valores. Diálogo 'mover cuotas pendientes' del legado. Devuelve cuántas movió.
    """
    flt = get_settings().sqlserver_filter
    inicio = dt.date.fromisoformat(nueva_fecha_inicio)
    with audit_scope(
        "registrador", "registrar_rpingdes", usuario=usuario, roles=roles,
        target_table="RPINGDES", target_key=f"{numero}/{empleado}",
        after={"nueva_fecha_inicio": nueva_fecha_inicio},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT SECUENCIA FROM dbo.RPINGDES
                WHERE {flt} AND NUMERO = ? AND EMPLEADO = ? AND CLASE = '205' AND ASENTADO = 0
                ORDER BY SECUENCIA""",
            (numero, str(empleado)),
        )
        secs = [int(r[0]) for r in cur.fetchall()]
        anio, mes = inicio.year, inicio.month
        for sec in secs:
            venc = _ultimo_dia(anio, mes).isoformat()
            cur.execute(
                f"""UPDATE dbo.RPINGDES SET FECHA_VEN = ?
                    WHERE {flt} AND NUMERO = ? AND EMPLEADO = ? AND CLASE = '205'
                      AND SECUENCIA = ? AND ASENTADO = 0""",
                (venc, numero, str(empleado), sec),
            )
            anio, mes = _mes_siguiente(anio, mes)
        conn.commit()
    return len(secs)


def editar_cuota(
    numero: str, empleado: str, secuencia: int, nuevo_valor: float, nueva_fecha: str,
    *, usuario: str, roles: set[str],
) -> None:
    """Cambia el valor y/o fecha de vencimiento de una cuota NO asentada de un préstamo."""
    flt = get_settings().sqlserver_filter
    with audit_scope(
        "registrador", "registrar_rpingdes", usuario=usuario, roles=roles,
        target_table="RPINGDES", target_key=f"{numero}/{empleado}/{secuencia}",
        after={"valor": nuevo_valor, "fecha_ven": nueva_fecha},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        cur.execute(
            f"""UPDATE dbo.RPINGDES SET VALOR = ?, FECHA_VEN = ?
                WHERE {flt} AND NUMERO = ? AND EMPLEADO = ? AND CLASE = '205'
                  AND SECUENCIA = ? AND ASENTADO = 0""",
            (round(a_float(nuevo_valor), 2), nueva_fecha, numero, str(empleado), secuencia),
        )
        conn.commit()


# ── BIESS quirografarios / hipotecarios (pestaña 5) ─────────────────────────

_MESES_ES = (
    "", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO",
    "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
)


@dataclass
class Movimiento:
    empleado: str
    clase: int
    valor: float
    concepto: str
    periodo: str
    estado_biess: str = ""
    cedula: str = ""
    nombre: str = ""


def observacion_biess(clase: int | str, fecha: str) -> str:
    """'PRESTAMOS QUIROGRAFARIOS MES: JULIO 2026' (o HIPOTECARIOS para 207).
    Igual que `_biess_actualizar_obs` del legado."""
    try:
        d = dt.date.fromisoformat(str(fecha)[:10])
    except ValueError:
        d = dt.date.today()
    tipo = "HIPOTECARIOS" if str(clase) == "207" else "QUIROGRAFARIOS"
    return f"PRESTAMOS {tipo} MES: {_MESES_ES[d.month]} {d.year}"


def _empleado_por_cedula(cedula: str) -> dict | None:
    flt = get_settings().sqlserver_filter
    filas = sqlserver.filas(
        f"""SELECT [EMPLEADO],[APELLIDOS],[NOMBRES],[ESTADO]
            FROM [insevig].[dbo].[RPEMPLEA]
            WHERE {flt} AND CAST([CEDULA] AS BIGINT) = ?""",
        (int(cedula),),
    )
    return filas[0] if filas else None


def _empleados_por_cedulas(cedulas: list[str]) -> dict[str, dict]:
    """{cedula10: {'EMPLEADO','APELLIDOS','NOMBRES','ESTADO'}} en una sola consulta."""
    nums = sorted({int(c) for c in cedulas if str(c).isdigit()})
    if not nums:
        return {}
    flt = get_settings().sqlserver_filter
    out: dict[str, dict] = {}
    for i in range(0, len(nums), 500):
        chunk = nums[i:i + 500]
        marcas = ",".join("?" * len(chunk))
        filas = sqlserver.filas(
            f"""SELECT [EMPLEADO],[APELLIDOS],[NOMBRES],[ESTADO],[CEDULA]
                FROM [insevig].[dbo].[RPEMPLEA]
                WHERE {flt} AND CAST([CEDULA] AS BIGINT) IN ({marcas})""",
            tuple(chunk),
        )
        for r in filas:
            out[normalizar_cedula(r.get("CEDULA"))] = r
    return out


def preparar_biess(
    filas: list[dict], periodo: str, *, clase: int | str = CLASE_QUIROGRAFARIO,
) -> tuple[list[Movimiento], list[str]]:
    """Empareja cada cédula del Excel con un empleado. `estado_biess` ∈
    activo | liquidado | no_encontrado. `clase` = 204 (quirografario) o 207 (hipotecario)."""
    clase_i = int(clase)
    concepto = CLASES_SIMPLIFICADAS.get(str(clase_i), {}).get("concepto", "BIESS")
    ced_norm = [(f, normalizar_cedula(f["cedula"])) for f in filas]
    cache = _empleados_por_cedulas([c for _f, c in ced_norm])
    movs: list[Movimiento] = []
    avisos: list[str] = []
    for f, ced in ced_norm:
        emp = cache.get(ced)
        valor = round(float(f["valor"]), 2)
        if emp is None:
            movs.append(Movimiento("", clase_i, valor, concepto, periodo, "no_encontrado", ced, "NO ENCONTRADO"))
            avisos.append(f"Cédula {ced}: sin empleado en la nómina.")
            continue
        nombre = f"{(emp.get('APELLIDOS') or '').strip()} {(emp.get('NOMBRES') or '').strip()}".strip()
        estado = "activo" if (emp.get("ESTADO") or "").strip() == "ACT" else "liquidado"
        if estado == "liquidado":
            avisos.append(f"Cédula {ced} ({nombre}): empleado liquidado, no se registra.")
        movs.append(Movimiento(
            str(emp["EMPLEADO"]).strip(), clase_i, valor, concepto, periodo, estado, ced, nombre,
        ))
    return movs, avisos


def postear_biess(
    movimientos: list[Movimiento], *, clase: int | str, fecha: str, observacion: str,
    usuario: str, roles: set[str], dry_run: bool = True,
) -> dict:
    """Registra el lote BIESS: TODOS los activos con el MISMO número de egreso
    (modo agrupado, como `_biess_subir`). INSERT completo en RPINGDES + RPCONTRL."""
    clase_i = int(clase)
    activos = [m for m in movimientos if m.estado_biess == "activo" and m.empleado]
    liquidados = sum(1 for m in movimientos if m.estado_biess == "liquidado")
    no_encontrados = sum(1 for m in movimientos if m.estado_biess == "no_encontrado")
    total = round(sum(m.valor for m in activos), 2)
    base = {
        "a_insertar": len(activos), "liquidados": liquidados,
        "no_encontrados": no_encontrados, "total": total, "insertados": 0, "numero": 0,
    }
    if dry_run or not activos:
        return base
    cfg = CLASES_SIMPLIFICADAS[str(clase_i)]
    obs = (observacion or observacion_biess(clase_i, fecha))[:700]
    with audit_scope(
        "registrador", "registrar_rpingdes", usuario=usuario, roles=roles,
        target_table="RPINGDES", target_key=f"BIESS/{clase_i}/{fecha}",
        after={"clase": clase_i, "n": len(activos), "total": total},
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        numero = _proximo_numero(cur, cfg["tipo"])
        insertados = 0
        for m in activos:
            depto, seccion = _depto_seccion(cur, m.empleado)
            cur.execute(
                _INSERT_RPINGDES.format(clase=str(clase_i)),
                (numero, m.empleado, 1, fecha, fecha, m.valor, obs, depto, seccion,
                 cfg["aporta"], 3, 1, cfg["codigo"], cfg["concepto"], m.valor, 1),
            )
            insertados += 1
        _fijar_numero(cur, cfg["tipo"], numero)
        conn.commit()
    return {**base, "insertados": insertados, "numero": numero}


def _ya_existe(cur, empleado: str, clase: int, valor: float, ini: str, fin: str) -> bool:
    flt = get_settings().sqlserver_filter
    cur.execute(
        f"""SELECT COUNT(*) FROM [insevig].[dbo].[RPINGDES]
            WHERE {flt} AND [EMPLEADO] = ? AND [CLASE] = ? AND ABS([VALOR] - ?) < 0.01
              AND [FECHA_VEN] >= ? AND [FECHA_VEN] < ?""",
        (empleado, clase, valor, ini, fin),
    )
    return cur.fetchone()[0] > 0


def postear(movimientos: list[Movimiento], *, usuario: str, roles: set[str], dry_run: bool = True) -> dict:
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
