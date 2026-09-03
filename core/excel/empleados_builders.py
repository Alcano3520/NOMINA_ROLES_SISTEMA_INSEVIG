"""Plantilla de edición masiva de empleados + reporte de resultados."""

from __future__ import annotations

import io

import xlsxwriter

from core.repos.empleados import CAMPOS_EDITABLES


def plantilla_carga_masiva(empleados: list[dict], campos: list[str] | None = None) -> bytes:
    """Genera un xlsx con una fila por empleado y las columnas elegidas.

    `empleados`: dicts con al menos 'EMPLEADO' y los campos a incluir.
    """
    campos = campos or list(CAMPOS_EDITABLES)
    cols = ["EMPLEADO", *[c for c in campos if c != "EMPLEADO"]]
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white"})
    ws = wb.add_worksheet("EMPLEADOS")
    ws.write_row(0, 0, cols, hdr)
    for r, emp in enumerate(empleados, 1):
        for c, col in enumerate(cols):
            v = emp.get(col, "")
            ws.write(r, c, "" if v is None else str(v))
    ws.freeze_panes(1, 1)
    wb.close()
    return buf.getvalue()


def reporte_resultados(resultados: list[dict]) -> bytes:
    """`resultados`: [{'empleado','ok':bool,'detalle'}]."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white"})
    ws = wb.add_worksheet("Resultado")
    ws.write_row(0, 0, ["EMPLEADO", "ESTADO", "DETALLE"], hdr)
    for r, res in enumerate(resultados, 1):
        ws.write(r, 0, res["empleado"])
        ws.write(r, 1, "OK" if res["ok"] else "ERROR")
        ws.write(r, 2, res.get("detalle", ""))
    wb.close()
    return buf.getvalue()
