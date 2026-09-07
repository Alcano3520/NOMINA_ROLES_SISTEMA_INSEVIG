"""Builders de Excel del módulo Observaciones. Funciones puras: filas -> bytes."""

from __future__ import annotations

import io

import xlsxwriter


def resultados_carga_xlsx(resultados: list[dict]) -> bytes:
    """`resultados`: [{'empleado','periodo','ok':bool,'detalle'}]."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white"})
    ws = wb.add_worksheet("Resultado")
    ws.write_row(0, 0, ["EMPLEADO", "PERIODO", "ESTADO", "DETALLE"], hdr)
    for r, res in enumerate(resultados, 1):
        ws.write(r, 0, str(res.get("empleado", "")))
        ws.write(r, 1, str(res.get("periodo", "")))
        ws.write(r, 2, "OK" if res.get("ok") else "ERROR")
        ws.write(r, 3, str(res.get("detalle", "")))
    ws.set_column(0, 1, 14)
    ws.set_column(3, 3, 50)
    wb.close()
    return buf.getvalue()
