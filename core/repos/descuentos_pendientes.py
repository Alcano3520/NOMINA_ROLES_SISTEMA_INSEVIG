"""Descuentos pendientes de aplicar en una liquidación (pantalla del `.pyw`).

Tabla Supabase `descuentos_pendientes`
(`empleado_cedula, empleado_nombre, monto, motivo, estado, fecha,
fecha_registro, fecha_aplicado, created_by`).

`estado`: `pendiente` → se suma automáticamente al procesar la liquidación del
empleado; pasa a `aplicado` sólo cuando la liquidación se GUARDA (nunca al
previsualizar/generar, así se puede repetir). El borrado es directo, sin
historial (a diferencia de `liquidaciones`).

Rebanada del módulo `liquidaciones` pero en archivo aparte para no chocar con
la edición concurrente del motor de cálculo. NO importa otros `core/repos/*`.
"""

from __future__ import annotations

import datetime as dt

from core.db import supabase_client
from core.utils import a_float, normalizar_cedula

TABLA = "descuentos_pendientes"


def _hoy_iso() -> str:
    return dt.date.today().isoformat()


def _fecha_iso(txt: str) -> str:
    """`dd-mm-aaaa` / `dd/mm/aaaa` / ISO → ISO; vacío → hoy."""
    t = (txt or "").strip()
    if not t:
        return _hoy_iso()
    for sep in ("-", "/"):
        parts = t.split(sep)
        if len(parts) == 3 and len(parts[0]) <= 2:
            d, m, y = parts
            with_ = f"{y}-{int(m):02d}-{int(d):02d}"
            try:
                dt.date.fromisoformat(with_)
                return with_
            except ValueError:
                pass
    try:
        return dt.date.fromisoformat(t[:10]).isoformat()
    except ValueError:
        return _hoy_iso()


def listar(estado: str = "") -> list[dict]:
    """`estado` ∈ {'', 'pendiente', 'aplicado'} — '' = todos. Más recientes primero."""
    sb = supabase_client.get_client()
    q = sb.table(TABLA).select("*")
    if estado in ("pendiente", "aplicado"):
        q = q.eq("estado", estado)
    filas = q.order("fecha_registro", desc=True).limit(1000).execute().data or []
    for f in filas:
        f["cedula_norm"] = normalizar_cedula(f.get("empleado_cedula"))
    return filas


def pendientes_de(cedula: str) -> list[dict]:
    """Descuentos en estado 'pendiente' de un empleado (para `procesar_empleado`)."""
    ced = normalizar_cedula(cedula)
    sb = supabase_client.get_client()
    return (
        sb.table(TABLA).select("id,monto,motivo")
        .eq("empleado_cedula", ced).eq("estado", "pendiente").execute().data or []
    )


def crear(
    *, cedula: str, nombre: str, motivo: str, monto: float, fecha: str = "", usuario: str,
) -> tuple[bool, str]:
    ced = normalizar_cedula(cedula)
    if not (ced.isdigit() and len(ced) == 10 and ced != "0000000000"):
        return False, "Cédula inválida."
    if not motivo.strip():
        return False, "El motivo es obligatorio."
    if a_float(monto) <= 0:
        return False, "El monto debe ser mayor a 0."
    sb = supabase_client.get_client()
    sb.table(TABLA).insert({
        "empleado_cedula": ced,
        "empleado_nombre": nombre.strip() or None,
        "motivo": motivo.strip(),
        "monto": round(a_float(monto), 2),
        "estado": "pendiente",
        "fecha": _fecha_iso(fecha),
        "fecha_registro": _hoy_iso(),
        "created_by": usuario,
    }).execute()
    return True, ""


def crear_masivo(texto: str, *, usuario: str) -> tuple[int, list[str]]:
    """Una línea por descuento: `cédula, monto, motivo`. Devuelve `(creados, errores)`."""
    creados = 0
    errores: list[str] = []
    for n, linea in enumerate(texto.splitlines(), 1):
        if not linea.strip():
            continue
        partes = [p.strip() for p in linea.replace(";", ",").split(",", 2)]
        if len(partes) < 3:
            errores.append(f"Línea {n}: se esperaba «cédula, monto, motivo».")
            continue
        ced, monto_txt, motivo = partes
        try:
            monto = float(monto_txt.replace("$", "").replace(",", "."))
        except ValueError:
            errores.append(f"Línea {n}: monto «{monto_txt}» no es un número.")
            continue
        ok, err = crear(cedula=ced, nombre="", motivo=motivo, monto=monto, usuario=usuario)
        if ok:
            creados += 1
        else:
            errores.append(f"Línea {n}: {err}")
    return creados, errores


def eliminar(ids: list[str], *, usuario: str) -> int:  # noqa: ARG001 - usuario para paridad de firma
    """Borrado directo, sin historial (igual que el `.pyw`)."""
    if not ids:
        return 0
    sb = supabase_client.get_client()
    sb.table(TABLA).delete().in_("id", list(ids)).execute()
    return len(ids)


def marcar_aplicados(ids: list[str], *, usuario: str) -> None:  # noqa: ARG001
    """Pasa a 'aplicado' los descuentos consumidos al guardar una liquidación."""
    if not ids:
        return
    sb = supabase_client.get_client()
    sb.table(TABLA).update(
        {"estado": "aplicado", "fecha_aplicado": _hoy_iso()}
    ).in_("id", list(ids)).execute()
