"""Parseo de Excel subido por el usuario: carga masiva de empleados y BIESS.

Devuelven `(filas_validas, errores)` — nunca lanzan por datos malos.
"""

from __future__ import annotations

import io

import openpyxl

from core.utils import normalizar_cedula


def _hoja(datos: bytes):
    wb = openpyxl.load_workbook(io.BytesIO(datos), read_only=True, data_only=True)
    return wb[wb.sheetnames[0]]


def parse_carga_masiva_empleados(datos: bytes) -> tuple[list[dict], list[str]]:
    ws = _hoja(datos)
    filas = list(ws.iter_rows(values_only=True))
    if not filas:
        return [], ["El archivo está vacío."]
    headers = [str(h).strip() if h is not None else "" for h in filas[0]]
    if "EMPLEADO" not in headers:
        return [], ["Falta la columna obligatoria 'EMPLEADO'."]
    idx_emp = headers.index("EMPLEADO")
    validas: list[dict] = []
    errores: list[str] = []
    for n, fila in enumerate(filas[1:], start=2):
        cod = fila[idx_emp]
        if cod in (None, ""):
            continue
        registro = {"EMPLEADO": str(cod).strip()}
        for i, h in enumerate(headers):
            if h and h != "EMPLEADO" and i < len(fila) and fila[i] not in (None, ""):
                registro[h] = fila[i]
        if len(registro) == 1:
            errores.append(f"Fila {n}: sin campos a actualizar para {cod}.")
            continue
        validas.append(registro)
    return validas, errores


# ── BIESS quirografarios ─────────────────────────────────────────────────────


def _es_cedula(valor: object) -> bool:
    if valor is None:
        return False
    s = str(valor).replace(".0", "").strip()
    return s.isdigit() and 8 <= len(s) <= 10


def _es_monto(valor: object) -> bool:
    try:
        return float(str(valor).replace(",", "")) > 0
    except (TypeError, ValueError):
        return False


def parse_biess_quirografarios(datos: bytes) -> tuple[list[dict], list[str]]:
    """Autodetecta columnas de cédula y valor por contenido (porta la lógica de
    `REGISTRAR_PRESTAMOS_UNIFICADO.pyw`). Devuelve [{'cedula','valor'}]."""
    ws = _hoja(datos)
    filas = [list(f) for f in ws.iter_rows(values_only=True) if any(c is not None for c in f)]
    if not filas:
        return [], ["Archivo vacío."]
    ncols = max(len(f) for f in filas)
    # elegir la columna con más cédulas y la que más montos
    col_ced = max(range(ncols), key=lambda c: sum(_es_cedula(f[c]) for f in filas if c < len(f)))
    col_val = max(
        (c for c in range(ncols) if c != col_ced),
        key=lambda c: sum(_es_monto(f[c]) for f in filas if c < len(f)),
        default=-1,
    )
    if col_val < 0:
        return [], ["No se detectó una columna de valores."]
    out: list[dict] = []
    errores: list[str] = []
    for n, f in enumerate(filas, 1):
        if col_ced >= len(f) or not _es_cedula(f[col_ced]):
            continue
        if col_val >= len(f) or not _es_monto(f[col_val]):
            errores.append(f"Fila {n}: cédula sin valor válido.")
            continue
        out.append(
            {
                "cedula": normalizar_cedula(f[col_ced]),
                "valor": round(float(str(f[col_val]).replace(",", "")), 2),
            }
        )
    return out, errores
