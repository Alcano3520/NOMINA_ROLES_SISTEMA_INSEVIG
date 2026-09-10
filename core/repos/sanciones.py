"""Sanciones disciplinarias — BACKEND PURO (sin UI Reflex, contrato C3).

Trasplante de `sistema_sanciones_RRHH/nucleo_modular/sanciones.py` +
`empleados.py` (enriquecimiento), adaptado del transporte `requests`/PostgREST
del legado al cliente `supabase-py` de nómina (`core.db.supabase_client`).

- El cliente Supabase se **inyecta como parámetro** (`cliente=`), o se resuelve
  con `get_client_sanciones()` en la primera llamada — NUNCA se lee la config
  global dentro de la lógica.
- Cédula normalizada en la **frontera** (`core.utils.normalizar_cedula`): al
  entrar (parámetros) y al salir (dicts que devuelve el repo).
- La auditoría SQLite local del legado (`local_db.py`) se reemplaza por
  `core.audit.registrar_evento`.
- Sin SQL Server. Sin páginas Reflex. `"sanciones"` NO va en `registry`/`MODULOS`.

Lógica de negocio (queries, filtros, orden, manejo de errores) = igual que el
legado. Los bugs del README §1-8 que tocan estas funciones van anotados
`# LEGADO:`.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from core.audit.writer import registrar_evento
from core.config import get_settings
from core.sanciones import catalogos
from core.utils import normalizar_cedula

log = logging.getLogger(__name__)

_TABLA = "sanciones"
_PAGE_SIZE = 50
_BATCH = 50


def _cli(cliente: Any | None, *, service: bool = False) -> Any:
    if cliente is not None:
        return cliente
    from core.db.supabase_client import get_client_sanciones

    return get_client_sanciones(service=service)


def _norm_salida(sancion: dict) -> dict:
    """Normaliza la cédula en la salida (frontera). `empleado_cedula` viene del
    enriquecimiento; `empleado_cod` es el código, no se toca.
    """
    ced = sancion.get("empleado_cedula")
    if ced:
        sancion["empleado_cedula"] = normalizar_cedula(ced)
    return sancion


def fmt_fecha(v: object) -> str:
    """YYYY-MM-DD / ISO -> DD/MM/YYYY (igual que `ContentArea._format_fecha` del .pyw)."""
    s = str(v or "")
    if not s or s == "None":
        return ""
    s = s.split("T")[0]
    p = s.split("-")
    return f"{p[2][:2]}/{p[1]}/{p[0]}" if len(p) == 3 else s


def _display(sancion: dict) -> dict:
    """Campos listos para mostrar en las tablas web (formato del .pyw)."""
    sancion["id_corto"] = str(sancion.get("id") or "")[:8]
    sancion["fecha_fmt"] = fmt_fecha(sancion.get("fecha"))
    creado = str(sancion.get("created_at") or "")
    sancion["hora"] = creado.split("T")[1][:5] if "T" in creado else ""
    sancion["enviado_fmt"] = fmt_fecha(sancion.get("created_at"))
    sancion["status_up"] = str(sancion.get("status") or "").upper()
    sid = str(sancion.get("supervisor_id") or "")
    sancion.setdefault("supervisor_txt", f"ID: {sid[:8]}" if sid else "Sin asignar")
    return sancion


def _resolver_supervisores(filas: list[dict], cliente_service: Any | None) -> None:
    """Best-effort: pone `supervisor_txt` = nombre real (tabla profiles) cuando la
    SERVICE key está configurada; si no, deja el fallback de `_display`.
    """
    ids = [str(f["supervisor_id"]) for f in filas if f.get("supervisor_id")]
    if not ids:
        return
    try:
        nombres = nombres_supervisores(ids, cliente_service=cliente_service)
    except Exception as e:  # noqa: BLE001
        log.info("supervisores no resueltos: %s", e)
        return
    for f in filas:
        n = nombres.get(str(f.get("supervisor_id") or ""))
        if n:
            f["supervisor_txt"] = n


def _proc_desde_comentario(sancion: dict) -> None:
    """`procesado_por` / `fecha_procesamiento` desde `comentarios_rrhh`
    ("Procesado para nomina - DD/MM/YYYY HH:MM - usuario"). Porta el fallback de
    `local_db.enriquecer_con_datos_locales` (README §item). Muta el dict.
    """
    if sancion.get("procesado_por"):
        return
    com = str(sancion.get("comentarios_rrhh") or "")
    if " - " in com:
        partes = com.split(" - ")
        if len(partes) >= 3:
            sancion["procesado_por"] = partes[-1].strip()
            sancion["fecha_procesamiento"] = partes[-2].strip()


# ── enriquecimiento con la tabla `empleados` (proyecto de nómina) ───────────


def _cliente_empleados(cliente: Any | None) -> Any:
    if cliente is not None:
        return cliente
    from core.db.supabase_client import get_client

    return get_client()


_COLS_EMP = "cod,nombres,apellidos,cedula,nombres_completos,nomcargo,nomdep,es_activo"


def _empleados_por_codigos(codigos: list, cliente_emp: Any) -> dict[int, dict]:
    cods = list({int(c) for c in codigos if c})
    if not cods:
        return {}
    out: dict[int, dict] = {}
    for i in range(0, len(cods), 100):
        chunk = cods[i:i + 100]
        res = (
            cliente_emp.table("empleados").select(_COLS_EMP)
            .in_("cod", chunk).eq("es_activo", True).execute()
        )
        filas = list(res.data or [])
        faltan = set(chunk) - {e.get("cod") for e in filas}
        if faltan:  # reintento sin es_activo (empleados retirados con sanciones)
            r2 = cliente_emp.table("empleados").select(_COLS_EMP).in_("cod", list(faltan)).execute()
            filas += list(r2.data or [])
        for e in filas:
            if e.get("cod") is not None:
                out[int(e["cod"])] = e
    return out


def _aplicar_empleado(sancion: dict, emp: dict) -> None:
    sancion["empleado_cedula"] = normalizar_cedula(emp.get("cedula", ""))
    sancion["empleado_nombre"] = (
        emp.get("nombres_completos")
        or f"{emp.get('nombres', '')} {emp.get('apellidos', '')}".strip()
    )
    sancion["empleado_cargo"] = emp.get("nomcargo", "")
    sancion["empleado_departamento"] = emp.get("nomdep", "")


def enriquecer_sanciones_lote(sanciones: list[dict], *, cliente_empleados: Any | None = None) -> list[dict]:
    """Añade empleado_cedula/nombre/cargo/departamento a una lista de sanciones,
    en una sola consulta por lote. Muta y devuelve la misma lista.
    """
    if not sanciones:
        return sanciones
    codigos = [s.get("empleado_cod") for s in sanciones if s.get("empleado_cod")]
    if codigos:
        emap = _empleados_por_codigos(codigos, _cliente_empleados(cliente_empleados))
        for s in sanciones:
            emp = emap.get(int(s["empleado_cod"])) if s.get("empleado_cod") else None
            if emp:
                _aplicar_empleado(s, emp)
    return [_display(_norm_salida(s)) for s in sanciones]


# ── lecturas de la tabla `sanciones` ───────────────────────────────────────


def obtener_sancion(sancion_id: str, *, cliente: Any | None = None) -> dict | None:
    """Ficha completa de una sanción por ID. Puerto de `obtener_sancion`."""
    try:
        res = _cli(cliente).table(_TABLA).select("*").eq("id", sancion_id).execute()
        filas = res.data or []
        return _display(_norm_salida(dict(filas[0]))) if filas else None
    except Exception as e:  # noqa: BLE001
        log.error("obtener_sancion(%s): %s", sancion_id, e)
        return None


def buscar_sanciones(
    texto_busqueda: str, limite: int = 500, tipo_sancion: str | None = None,
    solo_historial: bool = False, enriquecer: bool = True,
    *, cliente: Any | None = None, cliente_empleados: Any | None = None,
) -> list[dict]:
    """Búsqueda server-side (ilike sobre nombre/agente/tipo/observaciones/puesto,
    + código exacto si el texto es numérico). Puerto de `buscar_sanciones`.
    """
    texto = (texto_busqueda or "").strip()
    tiene_texto = len(texto) >= 2
    if not tiene_texto and not tipo_sancion:
        return []
    try:
        q = _cli(cliente).table(_TABLA).select("*").order("updated_at", desc=True).limit(limite)
        if solo_historial:
            q = q.not_.is_("comentarios_rrhh", "null")
        if tipo_sancion:
            q = q.ilike("tipo_sancion", tipo_sancion)
        if tiene_texto:
            patron = f"%{texto}%"
            campos = [
                f"empleado_nombre.ilike.{patron}", f"agente.ilike.{patron}",
                f"tipo_sancion.ilike.{patron}", f"observaciones.ilike.{patron}",
                f"puesto.ilike.{patron}",
            ]
            if texto.isdigit():
                campos.append(f"empleado_cod.eq.{texto}")
            q = q.or_(",".join(campos))
        filas = list(q.execute().data or [])
    except Exception as e:  # noqa: BLE001
        log.error("buscar_sanciones: %s", e)
        return []
    if enriquecer and filas:
        out = enriquecer_sanciones_lote(filas, cliente_empleados=cliente_empleados)
        _resolver_supervisores(out, None)
        for f in out:
            _proc_desde_comentario(f)
        return out
    return [_display(_norm_salida(f)) for f in filas]


def buscar_historial(texto_busqueda: str, limite: int = 200, tipo_sancion: str | None = None,
                     *, cliente: Any | None = None) -> list[dict]:
    return buscar_sanciones(texto_busqueda, limite=limite, tipo_sancion=tipo_sancion,
                            solo_historial=True, cliente=cliente)


def obtener_sanciones_pendientes_aprobacion(*, cliente: Any | None = None,
                                            cliente_empleados: Any | None = None,
                                            cliente_service: Any | None = None) -> list[dict]:
    """`status=enviado` (esperando gerencia). Puerto de la función homónima."""
    try:
        filas = list(
            _cli(cliente).table(_TABLA).select("*").eq("status", "enviado")
            .order("created_at", desc=True).limit(200).execute().data or []
        )
    except Exception as e:  # noqa: BLE001
        log.error("pendientes_aprobacion: %s", e)
        return []
    if not filas:
        return []
    out = enriquecer_sanciones_lote(filas, cliente_empleados=cliente_empleados)
    _resolver_supervisores(out, cliente_service)
    return out


def obtener_sanciones_pendientes(*, cliente: Any | None = None,
                                 cliente_empleados: Any | None = None,
                                 cliente_service: Any | None = None) -> list[dict]:
    """`status=aprobado` sin `comentarios_rrhh` (listas para RRHH)."""
    try:
        filas = list(
            _cli(cliente).table(_TABLA).select("*").eq("status", "aprobado")
            .is_("comentarios_rrhh", "null").order("fecha", desc=True).execute().data or []
        )
    except Exception as e:  # noqa: BLE001
        log.error("pendientes: %s", e)
        return []
    if not filas:
        return []
    out = enriquecer_sanciones_lote(filas, cliente_empleados=cliente_empleados)
    _resolver_supervisores(out, cliente_service)
    return out


def obtener_procesadas_completas(page: int = 1, page_size: int | None = None,
                                 *, cliente: Any | None = None,
                                 cliente_empleados: Any | None = None) -> dict:
    """Historial paginado (`comentarios_rrhh IS NOT NULL`, `updated_at.desc`)."""
    page_size = page_size or _PAGE_SIZE
    offset = (page - 1) * page_size
    try:
        filas = list(
            _cli(cliente).table(_TABLA).select("*").not_.is_("comentarios_rrhh", "null")
            .order("updated_at", desc=True).range(offset, offset + page_size - 1).execute().data or []
        )
    except Exception as e:  # noqa: BLE001
        log.error("procesadas page %s: %s", page, e)
        return {"data": [], "page": page, "page_size": page_size, "count": 0, "has_more": False}
    if filas:
        filas = enriquecer_sanciones_lote(filas, cliente_empleados=cliente_empleados)
        for f in filas:
            _proc_desde_comentario(f)
    return {
        "data": filas, "page": page, "page_size": page_size,
        "count": len(filas), "has_more": len(filas) == page_size,
    }


def obtener_total_historial(*, cliente: Any | None = None) -> int:
    try:
        res = (
            _cli(cliente).table(_TABLA).select("id", count="exact")
            .not_.is_("comentarios_rrhh", "null").limit(1).execute()
        )
        return int(res.count or 0)
    except Exception as e:  # noqa: BLE001
        log.error("total_historial: %s", e)
        return 0


def validar_disponibilidad_sanciones(ids_sanciones: list[str],
                                     *, cliente: Any | None = None) -> tuple[list[str], list[str]]:
    """Cuáles de estos IDs siguen sin `comentarios_rrhh`. → (disponibles, no_disponibles)."""
    if not ids_sanciones:
        return [], []
    try:
        actuales = list(
            _cli(cliente).table(_TABLA).select("id,comentarios_rrhh,updated_at")
            .in_("id", ids_sanciones).execute().data or []
        )
    except Exception as e:  # noqa: BLE001
        log.error("validar_disponibilidad: %s", e)
        return ids_sanciones, []
    por_id = {s["id"]: s for s in actuales}
    disp: list[str] = []
    no_disp: list[str] = []
    for sid in ids_sanciones:
        a = por_id.get(sid)
        (disp if a and not a.get("comentarios_rrhh") else no_disp).append(sid)
    return disp, no_disp


# ── escrituras (PATCH de status / comentarios_rrhh) ─────────────────────────


def aprobar_sancion_individual(sancion: dict, usuario_aprobador: str,
                               observaciones_aprobacion: str = "",
                               *, cliente: Any | None = None) -> tuple[bool, str]:
    """`status=aprobado` + `comentarios_gerencia` + `fecha_revision`."""
    sid = sancion["id"]
    try:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        comentario = observaciones_aprobacion or f"Aprobado por {usuario_aprobador} - {fecha}"
        _cli(cliente).table(_TABLA).update({
            "status": "aprobado", "comentarios_gerencia": comentario,
            "fecha_revision": datetime.now().isoformat(),
        }).eq("id", sid).execute()
    except Exception as e:  # noqa: BLE001
        return False, f"Error: {e}"
    registrar_evento("sanciones", "aprobar", usuario=usuario_aprobador,
                     target_table="sanciones", target_key=str(sid))
    return True, "Aprobación exitosa"


def aprobar_multiples_sanciones(sanciones: list[dict], usuario_aprobador: str,
                                observaciones: str = "", callback_progreso=None,
                                *, cliente: Any | None = None) -> tuple[int, int, list[str]]:
    """Aprueba varias, secuencial (el legado usaba hilos por la GUI Tkinter; el
    resultado exitosas/fallidas/errores es idéntico — README §7).
    """
    if not sanciones:
        return 0, 0, []
    ok = fail = 0
    errores: list[str] = []
    for s in sanciones:
        exito, msg = aprobar_sancion_individual(s, usuario_aprobador, observaciones, cliente=cliente)
        if exito:
            ok += 1
        else:
            fail += 1
            errores.append(f"{str(s['id'])[:8]}: {msg}")
        if callback_progreso:
            callback_progreso(f"Aprobadas: {ok + fail}/{len(sanciones)}")
    registrar_evento("sanciones", "aprobar_masivo", usuario=usuario_aprobador,
                     status="ok" if not fail else "error")
    return ok, fail, errores


def rechazar_sancion_individual(sancion: dict, usuario_rechazador: str, motivo_rechazo: str,
                                *, cliente: Any | None = None) -> tuple[bool, str]:
    sid = sancion["id"]
    try:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        _cli(cliente).table(_TABLA).update({
            "status": "rechazado",
            "comentarios_gerencia": (
                f"RECHAZADO por {usuario_rechazador} - {fecha} - Motivo: {motivo_rechazo}"
            ),
        }).eq("id", sid).execute()
    except Exception as e:  # noqa: BLE001
        return False, f"Error: {e}"
    registrar_evento("sanciones", "rechazar", usuario=usuario_rechazador,
                     target_table="sanciones", target_key=str(sid))
    return True, "Rechazo exitoso"


def procesar_sancion_individual(sancion: dict, usuario: str,
                                *, cliente: Any | None = None) -> tuple[bool, str]:
    """Marca `comentarios_rrhh` ("Procesado para nomina")."""
    sid = sancion["id"]
    try:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        _cli(cliente).table(_TABLA).update({
            "comentarios_rrhh": f"{catalogos.MSG_PROCESADO} - {fecha} - {usuario}",
        }).eq("id", sid).execute()
    except Exception as e:  # noqa: BLE001
        return False, f"Error: {e}"
    registrar_evento("sanciones", "procesar", usuario=usuario,
                     target_table="sanciones", target_key=str(sid))
    return True, "Éxito"


def procesar_multiples_sanciones(sanciones: list[dict], usuario: str, callback_progreso=None,
                                 *, cliente: Any | None = None) -> tuple[int, int, list[str]]:
    """Valida disponibilidad y procesa las que sigan libres. Secuencial (README §7)."""
    if not sanciones:
        return 0, 0, []
    ids = [s["id"] for s in sanciones]
    disp_ids, _ = validar_disponibilidad_sanciones(ids, cliente=cliente)
    disponibles = [s for s in sanciones if s["id"] in disp_ids]
    if not disponibles:
        return 0, len(sanciones), ["Todas las sanciones ya fueron procesadas"]
    ok = fail = 0
    errores: list[str] = []
    for s in disponibles:
        exito, msg = procesar_sancion_individual(s, usuario, cliente=cliente)
        if exito:
            ok += 1
        else:
            fail += 1
            errores.append(f"{str(s['id'])[:8]}: {msg}")
        if callback_progreso:
            callback_progreso(f"Procesadas: {ok + fail}/{len(disponibles)}")
    registrar_evento("sanciones", "procesar_masivo", usuario=usuario,
                     status="ok" if not fail else "error")
    return ok, fail, errores


def categorizar_sanciones(sanciones: list[dict]) -> dict[str, list[dict]]:
    """Agrupa por categoría de `catalogos.CATEGORIAS`. Puerto exacto."""
    out: dict[str, list[dict]] = {c: [] for c in catalogos.CATEGORIAS}
    for s in sanciones:
        tipo = (s.get("tipo_sancion") or "").upper()
        for categoria, tipos in catalogos.CATEGORIAS.items():
            if tipo in tipos:
                out[categoria].append(s)
                break
        else:
            out.setdefault("Resto", []).append(s)
    return out


# ── novedades de horario (tabla `cambios_horario`, origen Flutter) ──────────


def obtener_novedades_pendientes(limite: int = 200, *, cliente: Any | None = None) -> list[dict]:
    try:
        return list(
            _cli(cliente).table("cambios_horario").select("*")
            .eq("procesado", False).order("id", desc=True).limit(limite).execute().data or []
        )
    except Exception as e:  # noqa: BLE001
        log.error("novedades: %s", e)
        return []


def marcar_novedad_procesada(novedad_id: int, observacion: str = "",
                             *, cliente: Any | None = None) -> bool:
    try:
        _cli(cliente).table("cambios_horario").update({
            "procesado": True, "observacion_rrhh": observacion,
        }).eq("id", novedad_id).execute()
        return True
    except Exception as e:  # noqa: BLE001
        log.error("marcar_novedad: %s", e)
        return False


# ── imágenes (helper de conveniencia) ──────────────────────────────────────


def resolver_urls_evidencia(sancion: dict) -> dict[str, str | None]:
    """{'firma': url|None, 'foto': url|None} para la ficha de detalle."""
    from core.sanciones.imagenes import resolver_url_firma, resolver_url_foto

    base = get_settings().supabase_sanciones_url
    return {"firma": resolver_url_firma(sancion, base), "foto": resolver_url_foto(sancion, base)}


# ── supervisores (tabla `profiles`, requiere SERVICE key) ───────────────────


def nombres_supervisores(ids: list[str], *, cliente_service: Any | None = None) -> dict[str, str]:
    """Resuelve IDs de supervisor/revisor a nombres legibles (tabla `profiles`).
    Puerto de `empleados.obtener_nombres_supervisores`.
    """
    unicos = list({str(i) for i in ids if i})
    if not unicos:
        return {}
    cli = _cli(cliente_service, service=True)
    out: dict[str, str] = {}
    for i in range(0, len(unicos), 50):
        try:
            filas = (
                cli.table("profiles").select("id,full_name,email")
                .in_("id", unicos[i:i + 50]).execute().data or []
            )
        except Exception as e:  # noqa: BLE001
            log.error("nombres_supervisores: %s", e)
            continue
        for p in filas:
            out[str(p.get("id"))] = p.get("full_name") or p.get("email") or "Sin nombre"
    return out


# ── estadísticas (del proyecto Supabase, reemplaza el SQLite del legado) ────


def estadisticas(*, cliente: Any | None = None) -> dict:
    """Conteos sobre la tabla `sanciones`: por estado, por tipo, procesadas hoy,
    total histórico. Reemplaza `local_db.obtener_estadisticas` (que leía el
    SQLite del escritorio, inexistente en la web).
    """
    cli = _cli(cliente)
    out: dict = {"por_estado": {}, "por_tipo": {}, "procesadas_hoy": 0,
                 "total_procesadas": 0, "pendientes_aprobacion": 0, "pendientes_proceso": 0}
    try:
        filas = list(
            cli.table(_TABLA).select("status,tipo_sancion,comentarios_rrhh,updated_at")
            .limit(20000).execute().data or []
        )
    except Exception as e:  # noqa: BLE001
        log.error("estadisticas: %s", e)
        return out
    hoy = datetime.now().strftime("%Y-%m-%d")
    for f in filas:
        est = (f.get("status") or "sin estado")
        out["por_estado"][est] = out["por_estado"].get(est, 0) + 1
        if f.get("comentarios_rrhh"):
            out["total_procesadas"] += 1
            if str(f.get("updated_at") or "").startswith(hoy):
                out["procesadas_hoy"] += 1
            tipo = (f.get("tipo_sancion") or "OTRO").upper()
            out["por_tipo"][tipo] = out["por_tipo"].get(tipo, 0) + 1
        if est == "enviado":
            out["pendientes_aprobacion"] += 1
        elif est == "aprobado" and not f.get("comentarios_rrhh"):
            out["pendientes_proceso"] += 1
    out["por_tipo"] = dict(sorted(out["por_tipo"].items(), key=lambda kv: -kv[1]))
    return out


# ── reportes (Excel / PDF) ─────────────────────────────────────────────────


def exportar_excel(sanciones: list[dict], *, con_supervisores: bool = True,
                   cliente_service: Any | None = None) -> bytes | None:
    """`.xlsx` de una lista de sanciones ya enriquecidas (una hoja por categoría
    + Detalle Resumen con valor monetario + Resumen).
    """
    from core.excel.sanciones_builders import sanciones_xlsx
    from core.sanciones.valores import get_valores

    nombres = {}
    if con_supervisores:
        ids = [s.get("supervisor_id") for s in sanciones] + [s.get("reviewed_by") for s in sanciones]
        nombres = nombres_supervisores([i for i in ids if i], cliente_service=cliente_service)
    return sanciones_xlsx(sanciones, nombres, get_valores())


def ficha_pdf(sancion_id: str, *, cliente: Any | None = None,
              cliente_empleados: Any | None = None, cliente_service: Any | None = None) -> bytes | None:
    """PDF de la ficha de una sanción (la busca, enriquece y resuelve el supervisor)."""
    from core.pdf.sancion_ficha import sancion_pdf

    s = obtener_sancion(sancion_id, cliente=cliente)
    if s is None:
        return None
    s = enriquecer_sanciones_lote([s], cliente_empleados=cliente_empleados)[0]
    nom = "No asignado"
    if s.get("supervisor_id"):
        nom = nombres_supervisores([s["supervisor_id"]], cliente_service=cliente_service).get(
            s["supervisor_id"], "No asignado"
        )
    return sancion_pdf(s, nom)
