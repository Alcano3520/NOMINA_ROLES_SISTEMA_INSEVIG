"""Agenda para Cobro de Liquidación de Haberes (módulo BITACORAS).

Porta `BITACORAS_AGENDA_EGRESOS_FORMATOS/Agenda_Liquidacion_Haberes.pyw`.
Datos en **Supabase** (tabla `agenda_cobro_registros`) — este módulo escribe a
Supabase, no a SQL Server (agenda propia de RRHH, no toca nómina).
Auditoría propia en `agenda_cobro_historial` + `core.audit`.
"""

from __future__ import annotations

import contextlib
import datetime as dt

from core.audit.writer import registrar_evento
from core.db import supabase_client

TABLA = "agenda_cobro_registros"
TABLA_HIST = "agenda_cobro_historial"

CAMPOS = (
    "fecha_firma_acuerdo", "apellidos_nombres", "cedula", "telefono_celular",
    "fecha_ingreso", "fecha_salida", "fecha_cobro", "hora", "observacion",
    "en_sistema", "finiquito", "liq_lista_cobro", "fecha_acercamiento",
    "lugar_firma", "forma_pago", "cheque_num", "banco", "periodo", "estado",
    "qap", "horas_suspension",
)
ESTADOS = ("pendiente", "agendado", "cobrado", "no_asistio", "anulado")


def listar(estado: str = "", texto: str = "") -> list[dict]:
    sb = supabase_client.get_client()
    q = sb.table(TABLA).select("*")
    if estado:
        q = q.eq("estado", estado)
    if texto.strip():
        t = texto.strip()
        q = q.or_(f"apellidos_nombres.ilike.%{t}%,cedula.ilike.%{t}%")
    return q.order("fecha_cobro", desc=False).limit(500).execute().data or []


def obtener(reg_id: int) -> dict | None:
    sb = supabase_client.get_client()
    r = sb.table(TABLA).select("*").eq("id", reg_id).limit(1).execute()
    return r.data[0] if r.data else None


def _limpiar(campos: dict) -> dict:
    return {k: campos[k] for k in CAMPOS if k in campos and campos[k] not in (None, "")}


def _historial(reg_id: int, accion: str, usuario: str, detalle: str = "") -> None:
    # el historial no debe romper la operación principal
    with contextlib.suppress(Exception):
        supabase_client.get_client().table(TABLA_HIST).insert(
            {
                "agenda_id": reg_id,
                "accion": accion,
                "usuario": usuario,
                "detalle": detalle,
                "fecha": dt.datetime.now(dt.UTC).isoformat(),
            }
        ).execute()


def crear(campos: dict, *, usuario: str, roles: set[str]) -> int:
    datos = _limpiar(campos)
    datos.setdefault("estado", "pendiente")
    datos["registrado_por"] = usuario
    datos["fecha_registro"] = dt.datetime.now(dt.UTC).isoformat()
    r = supabase_client.get_client().table(TABLA).insert(datos).execute()
    reg_id = r.data[0]["id"] if r.data else 0
    _historial(reg_id, "crear", usuario, f"{datos.get('apellidos_nombres', '')}")
    registrar_evento("bitacora", "crear", usuario=usuario, roles=roles, fuente="supabase",
                     target_table=TABLA, target_key=str(reg_id))
    return reg_id


def actualizar(reg_id: int, campos: dict, *, usuario: str, roles: set[str]) -> None:
    datos = _limpiar(campos)
    datos["editado_por"] = usuario
    datos["fecha_edicion"] = dt.datetime.now(dt.UTC).isoformat()
    supabase_client.get_client().table(TABLA).update(datos).eq("id", reg_id).execute()
    _historial(reg_id, "editar", usuario, ", ".join(datos.keys()))
    registrar_evento("bitacora", "editar", usuario=usuario, roles=roles, fuente="supabase",
                     target_table=TABLA, target_key=str(reg_id))


def cambiar_estado(reg_id: int, estado: str, *, usuario: str, roles: set[str]) -> None:
    if estado not in ESTADOS:
        raise ValueError(f"Estado inválido: {estado}")
    supabase_client.get_client().table(TABLA).update(
        {"estado": estado, "editado_por": usuario, "fecha_edicion": dt.datetime.now(dt.UTC).isoformat()}
    ).eq("id", reg_id).execute()
    _historial(reg_id, "estado", usuario, estado)
    registrar_evento("bitacora", "editar", usuario=usuario, roles=roles, fuente="supabase",
                     target_table=TABLA, target_key=str(reg_id))


def eliminar(reg_id: int, *, usuario: str, roles: set[str]) -> None:
    supabase_client.get_client().table(TABLA).delete().eq("id", reg_id).execute()
    _historial(reg_id, "eliminar", usuario)
    registrar_evento("bitacora", "eliminar", usuario=usuario, roles=roles, fuente="supabase",
                     target_table=TABLA, target_key=str(reg_id))
