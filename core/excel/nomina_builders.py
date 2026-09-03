"""Builders de Excel del módulo Reportes. Funciones puras: filas -> bytes."""

from __future__ import annotations

import io

import xlsxwriter

_ORDEN_FIJO = ["EMPLEADO", "APELLIDOS_NOMBRES", "CEDULA", "CARGO", "DEPTO", "SECCION", "SUELDO_BASE"]
_ORDEN_FINAL = ["TOTAL_INGRESOS", "TOTAL_EGRESOS", "TOTAL_RECIBIR"]


def _columnas(filas: list[dict]) -> list[str]:
    conceptos = sorted({k for f in filas for k in f} - set(_ORDEN_FIJO) - set(_ORDEN_FINAL))
    return _ORDEN_FIJO + conceptos + _ORDEN_FINAL


def consolidado_xlsx(filas: list[dict], *, hoja: str = "Consolidado") -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "constant_memory": True})
    ws = wb.add_worksheet(hoja[:31])
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white", "border": 1})
    money = wb.add_format({"num_format": "#,##0.00"})

    cols = _columnas(filas)
    for c, nombre in enumerate(cols):
        ws.write(0, c, nombre, hdr)
    for r, fila in enumerate(filas, 1):
        for c, nombre in enumerate(cols):
            v = fila.get(nombre, "")
            if isinstance(v, (int, float)) and nombre not in ("EMPLEADO",):
                ws.write_number(r, c, float(v), money)
            else:
                ws.write(r, c, "" if v is None else str(v))
    ws.freeze_panes(1, 3)
    wb.close()
    return buf.getvalue()


def comparador_xlsx(discrepancias: list, sql_rows: list[dict], sup_rows: list[dict]) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white"})

    ws = wb.add_worksheet("Diferencias")
    ws.write_row(0, 0, ["TIPO", "DETALLE"], hdr)
    if not discrepancias:
        ws.write(1, 0, "SIN DIFERENCIAS - SINCRONIZACION VERIFICADA")
    for r, d in enumerate(discrepancias, 1):
        ws.write(r, 0, d.tipo)
        ws.write(r, 1, d.detalle)

    for nombre, rows in (("SQL_Server", sql_rows), ("Supabase", sup_rows)):
        if not rows:
            continue
        w = wb.add_worksheet(nombre)
        cols = _columnas(rows)
        w.write_row(0, 0, cols, hdr)
        for r, fila in enumerate(rows, 1):
            w.write_row(r, 0, [fila.get(c, "") for c in cols])
    wb.close()
    return buf.getvalue()
