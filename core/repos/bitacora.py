"""Agenda para Cobro de Liquidación de Haberes + Bitácora de Atención Personal.

Porta `BITACORAS_AGENDA_EGRESOS_FORMATOS/Agenda_Liquidacion_Haberes.pyw`.
Datos en **Supabase** (este módulo escribe a Supabase, no a SQL Server: es agenda
propia de RRHH, no toca nómina). Tres tablas:
- `agenda_cobro_registros`  — la agenda de cobro.
- `agenda_cobro_historial`  — trazabilidad (FK `registro_id`).
- `bitacora_atencion_personal` — registro append-only de cada atención a un empleado.
- `bitacora_motivos` — catálogo de motivos de atención (editable).
"""

from __future__ import annotations

import contextlib
import datetime as dt

from core.audit.writer import registrar_evento
from core.db import supabase_client
from core.utils import cedula_valida, normalizar_cedula

TABLA = "agenda_cobro_registros"
TABLA_HIST = "agenda_cobro_historial"
TABLA_ATENCION = "bitacora_atencion_personal"
TABLA_MOTIVOS = "bitacora_motivos"

# Estados tal como los usa el sistema anterior (NO cambiar: la tabla es
# compartida con la app de escritorio que RRHH sigue usando).
ESTADOS = ("PENDIENTE", "AGENDADO", "PAGADO", "CANCELADO")
FORMAS_PAGO = ("EFECTIVO", "CHEQUE", "TRANSFERENCIA")

MOTIVOS_ATENCION = (
    "COBRO DE LIQUIDACIÓN", "CONSULTA GENERAL", "ENTREGA DE DOCUMENTOS",
    "SOLICITUD DE CERTIFICADO LABORAL", "RECLAMO / QUEJA", "TRÁMITE DE PRÉSTAMO",
    "CAMBIO DE DATOS PERSONALES", "OTRO",
)

# Campos editables de agenda_cobro_registros (los de horas-extra los mantiene la
# app de escritorio; aquí no se tocan).
CAMPOS = (
    "apellidos_nombres", "cedula", "empleado_cod", "telefono_celular", "cargo",
    "fecha_ingreso", "fecha_salida", "fecha_firma_acuerdo", "fecha_cobro", "hora",
    "observacion", "en_sistema", "finiquito", "liq_lista_cobro", "fecha_acercamiento",
    "lugar_firma", "forma_pago", "cheque_num", "banco", "periodo", "estado",
    "qap", "horas_suspension",
)

ETIQUETAS = {
    "apellidos_nombres": "Apellidos y nombres",
    "cedula": "Cédula",
    "empleado_cod": "Código de empleado",
    "telefono_celular": "Teléfono celular",
    "cargo": "Puesto / cargo",
    "fecha_ingreso": "Fecha de ingreso",
    "fecha_salida": "Fecha de salida",
    "fecha_firma_acuerdo": "Firma del acuerdo entre partes",
    "fecha_cobro": "Fecha de cobro",
    "hora": "Hora",
    "observacion": "Observación",
    "en_sistema": "Texto para el sistema",
    "finiquito": "Finiquito",
    "liq_lista_cobro": "Liquidación lista para cobro (desde)",
    "fecha_acercamiento": "Cuándo se acercó / consignó",
    "lugar_firma": "Lugar donde firma la liquidación",
    "forma_pago": "Forma de pago",
    "cheque_num": "Cheque N.º",
    "banco": "Banco",
    "periodo": "Período",
    "estado": "Estado",
    "qap": "Empleado con estatus / reporte Q.A.P.",
    "horas_suspension": "Horas de suspensión",
}
CAMPOS_FECHA = frozenset({
    "fecha_ingreso", "fecha_salida", "fecha_firma_acuerdo", "fecha_cobro",
    "liq_lista_cobro", "fecha_acercamiento",
})

_MESES_ES = (
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


# ── Utilidades de fecha / período ────────────────────────────────────────────


def _parsear_fecha(s: str) -> dt.date | None:
    s = str(s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        with contextlib.suppress(ValueError):
            return dt.datetime.strptime(s[:10], fmt).date()
    return None


def fecha_iso(s: str) -> str:
    d = _parsear_fecha(s)
    return d.strftime("%Y-%m-%d") if d else ""


def fecha_texto_es(s: str) -> str:
    """'2026-08-18' -> '18-agosto-2026' (formato que RRHH ya usa en RPEMPOBSERV)."""
    d = _parsear_fecha(s)
    return f"{d.day:02d}-{_MESES_ES[d.month]}-{d.year:04d}" if d else ""


def periodo_actual() -> str:
    return dt.date.today().strftime("%Y-%m")


def periodos_recientes(n: int = 12) -> list[str]:
    hoy = dt.date.today()
    y, m = hoy.year, hoy.month
    out = []
    for _ in range(n):
        out.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def texto_en_sistema(usuario: str, fecha_salida: str, motivo: str = "") -> str:
    """Texto que se sube a RPEMPOBSERV (mismo formato que el sistema anterior)."""
    hoy_txt = fecha_texto_es(dt.date.today().strftime("%Y-%m-%d"))
    salida_txt = fecha_texto_es(fecha_salida) or hoy_txt
    return (
        f"{usuario} Hoy {hoy_txt} se acerca la unidad a firmar el ACUERDO ENTRE LAS "
        f"PARTES. ULTIMO DIA LABORADO {salida_txt}-{motivo or ''}"
    )


# ── Lectura ─────────────────────────────────────────────────────────────────


def _todas_las_filas(query) -> list[dict]:
    """PostgREST corta a 1000 filas sin avisar: pagina con .range()."""
    filas: list[dict] = []
    paso = 1000
    desde = 0
    while True:
        lote = query.range(desde, desde + paso - 1).execute().data or []
        filas.extend(lote)
        if len(lote) < paso:
            return filas
        desde += paso


def listar(estado: str = "", texto: str = "", periodo: str = "") -> list[dict]:
    sb = supabase_client.get_client()
    q = sb.table(TABLA).select("*")
    if estado:
        q = q.eq("estado", estado)
    if periodo:
        q = q.eq("periodo", periodo)
    if texto.strip():
        t = texto.strip()
        q = q.or_(f"apellidos_nombres.ilike.%{t}%,cedula.ilike.%{t}%")
    return q.order("fecha_cobro", desc=False).limit(500).execute().data or []


def obtener(reg_id: int) -> dict | None:
    sb = supabase_client.get_client()
    r = sb.table(TABLA).select("*").eq("id", reg_id).limit(1).execute()
    return r.data[0] if r.data else None


def resumen(estado: str = "", periodo: str = "") -> dict:
    """Contadores para la pestaña de reportes."""
    sb = supabase_client.get_client()
    q = sb.table(TABLA).select("estado,horas_suspension,qap")
    if estado:
        q = q.eq("estado", estado)
    if periodo:
        q = q.eq("periodo", periodo)
    filas = _todas_las_filas(q)
    por_estado = {e: 0 for e in ESTADOS}
    for f in filas:
        e = str(f.get("estado") or "").upper()
        por_estado[e] = por_estado.get(e, 0) + 1
    return {
        "total": len(filas),
        "por_estado": por_estado,
        "horas_suspension": round(sum(float(f.get("horas_suspension") or 0) for f in filas), 2),
        "con_qap": sum(1 for f in filas if f.get("qap")),
    }


def historial_reciente(limite: int = 300) -> list[dict]:
    sb = supabase_client.get_client()
    filas = (
        sb.table(TABLA_HIST).select("*").order("id", desc=True).limit(limite).execute().data or []
    )
    return [
        {
            "id": f.get("id"),
            "registro_id": f.get("registro_id"),
            "accion": f.get("accion") or "",
            "usuario": f.get("usuario") or "",
            "detalle": f.get("detalle") or "",
            "fecha": str(f.get("fecha") or "")[:19].replace("T", " "),
        }
        for f in filas
    ]


def filas_reporte(estado: str = "", periodo: str = "") -> list[dict]:
    sb = supabase_client.get_client()
    q = sb.table(TABLA).select("*")
    if estado:
        q = q.eq("estado", estado)
    if periodo:
        q = q.eq("periodo", periodo)
    return _todas_las_filas(q.order("id"))


# ── Escritura ───────────────────────────────────────────────────────────────


def _limpiar(campos: dict) -> dict:
    out = {}
    for k in CAMPOS:
        if k not in campos:
            continue
        v = campos[k]
        if k == "cedula":
            v = normalizar_cedula(v)
        elif k == "qap":
            v = bool(v) if not isinstance(v, str) else v.strip().lower() in ("1", "true", "si", "sí")
        elif k == "horas_suspension":
            try:
                v = float(str(v).replace(",", ".") or 0)
            except ValueError:
                v = 0.0
        elif k in CAMPOS_FECHA:
            v = fecha_iso(v)
        elif isinstance(v, str):
            v = v.strip()
        if v not in (None, ""):
            out[k] = v
    return out


def _historial(reg_id: int, accion: str, usuario: str, detalle: str = "") -> None:
    with contextlib.suppress(Exception):
        supabase_client.get_client().table(TABLA_HIST).insert(
            {"registro_id": reg_id, "accion": accion, "usuario": usuario, "detalle": detalle}
        ).execute()


def cedula_es_valida(cedula: str) -> bool:
    c = normalizar_cedula(cedula)
    return bool(c) and cedula_valida(c)


def crear(campos: dict, *, usuario: str, roles: set[str]) -> int:
    datos = _limpiar(campos)
    if not datos.get("apellidos_nombres"):
        raise ValueError('El campo "Apellidos y nombres" es obligatorio.')
    datos.setdefault("estado", "PENDIENTE")
    datos.setdefault("periodo", periodo_actual())
    datos["registrado_por"] = usuario
    datos["editado_por"] = usuario
    r = supabase_client.get_client().table(TABLA).insert(datos).execute()
    reg_id = r.data[0]["id"] if r.data else 0
    detalle = (
        f"{datos.get('apellidos_nombres', '')} - Cédula: {datos.get('cedula', '')} - "
        f"Fecha de cobro: {datos.get('fecha_cobro', '')}"
    )
    _historial(reg_id, "ALTA", usuario, detalle)
    registrar_evento("bitacora", "crear", usuario=usuario, roles=roles, fuente="supabase",
                     target_table=TABLA, target_key=str(reg_id))
    return reg_id


def _diferencias(antes: dict, despues: dict) -> list[str]:
    cambios = []
    for k in CAMPOS:
        a = antes.get(k)
        d = despues.get(k)
        a = "" if a in (None, False) else a
        d = "" if d in (None, False) else d
        if str(a) != str(d):
            et = ETIQUETAS.get(k, k)
            cambios.append(f"{et}: {a or '(vacío)'} → {d or '(vacío)'}")
    return cambios


def actualizar(reg_id: int, campos: dict, *, usuario: str, roles: set[str]) -> None:
    datos = _limpiar(campos)
    original = obtener(reg_id) or {}
    datos["editado_por"] = usuario
    datos["fecha_edicion"] = dt.datetime.now(dt.UTC).isoformat()
    supabase_client.get_client().table(TABLA).update(datos).eq("id", reg_id).execute()
    cambios = _diferencias(original, datos)
    detalle = (
        f"{datos.get('apellidos_nombres') or original.get('apellidos_nombres', '')} - "
        f"Cambios: {'; '.join(cambios) if cambios else 'sin cambios en los campos'}"
    )
    _historial(reg_id, "EDICIÓN", usuario, detalle)
    registrar_evento("bitacora", "editar", usuario=usuario, roles=roles, fuente="supabase",
                     target_table=TABLA, target_key=str(reg_id))


def cambiar_estado(reg_id: int, estado: str, *, usuario: str, roles: set[str]) -> None:
    if estado not in ESTADOS:
        raise ValueError(f"Estado inválido: {estado}")
    supabase_client.get_client().table(TABLA).update(
        {"estado": estado, "editado_por": usuario,
         "fecha_edicion": dt.datetime.now(dt.UTC).isoformat()}
    ).eq("id", reg_id).execute()
    _historial(reg_id, "EDICIÓN", usuario, f"Estado → {estado}")
    registrar_evento("bitacora", "editar", usuario=usuario, roles=roles, fuente="supabase",
                     target_table=TABLA, target_key=str(reg_id))


def eliminar(reg_id: int, *, usuario: str, roles: set[str]) -> None:
    _historial(reg_id, "ELIMINACIÓN", usuario, f"Eliminado registro ID {reg_id}")
    supabase_client.get_client().table(TABLA).delete().eq("id", reg_id).execute()
    registrar_evento("bitacora", "eliminar", usuario=usuario, roles=roles, fuente="supabase",
                     target_table=TABLA, target_key=str(reg_id))


# ── Bitácora de Atención Personal ───────────────────────────────────────────


def motivos_activos() -> list[str]:
    with contextlib.suppress(Exception):
        filas = (
            supabase_client.get_client().table(TABLA_MOTIVOS)
            .select("motivo").eq("activo", True).order("orden").execute().data or []
        )
        valores = [f["motivo"] for f in filas]
        if valores:
            return valores
    return list(MOTIVOS_ATENCION)


def atenciones(texto: str = "", limite: int = 300) -> list[dict]:
    sb = supabase_client.get_client()
    q = sb.table(TABLA_ATENCION).select("*")
    if texto.strip():
        t = texto.strip()
        q = q.or_(f"apellidos_nombres.ilike.%{t}%,cedula.ilike.%{t}%")
    filas = q.order("id", desc=True).limit(limite).execute().data or []
    return [
        {
            "id": f.get("id"),
            "atendido_por": f.get("atendido_por") or "",
            "apellidos_nombres": f.get("apellidos_nombres") or "",
            "cedula": normalizar_cedula(f.get("cedula")),
            "motivo": f.get("motivo") or "",
            "observacion": f.get("observacion") or "",
            "fecha_atencion": str(f.get("fecha_atencion") or "")[:10],
            "hora": f.get("hora") or "",
        }
        for f in filas
    ]


def registrar_atencion(
    *, apellidos_nombres: str, cedula: str, motivo: str, observacion: str,
    fecha: str, hora: str, empleado_cod: str = "", usuario: str, roles: set[str],
) -> int:
    nombre = (apellidos_nombres or "").strip().upper()
    if not nombre:
        raise ValueError("Indica el empleado atendido.")
    datos = {
        "empleado_cod": empleado_cod or None,
        "apellidos_nombres": nombre,
        "cedula": normalizar_cedula(cedula),
        "motivo": (motivo or "").strip(),
        "observacion": (observacion or "").strip(),
        "fecha_atencion": fecha_iso(fecha) or dt.date.today().strftime("%Y-%m-%d"),
        "hora": (hora or "").strip(),
        "atendido_por": usuario,
    }
    r = supabase_client.get_client().table(TABLA_ATENCION).insert(datos).execute()
    aid = r.data[0]["id"] if r.data else 0
    registrar_evento("bitacora", "crear", usuario=usuario, roles=roles, fuente="supabase",
                     target_table=TABLA_ATENCION, target_key=str(aid))
    return aid


def eliminar_atencion(aid: int, *, usuario: str, roles: set[str]) -> None:
    supabase_client.get_client().table(TABLA_ATENCION).delete().eq("id", aid).execute()
    registrar_evento("bitacora", "eliminar", usuario=usuario, roles=roles, fuente="supabase",
                     target_table=TABLA_ATENCION, target_key=str(aid))
