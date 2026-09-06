"""Builders de Excel del módulo Administración. Funciones puras: filas -> bytes."""

from __future__ import annotations

import io

import xlsxwriter

_COLS = [
    ("ts", "FECHA/HORA"),
    ("usuario", "USUARIO"),
    ("modulo", "MÓDULO"),
    ("accion", "ACCIÓN"),
    ("objetivo", "OBJETIVO"),
    ("status", "ESTADO"),
]


def auditoria_xlsx(filas: list[dict]) -> bytes:
    """`filas` con la forma que devuelve `core.repos.admin.buscar_auditoria`."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white", "border": 1})
    ws = wb.add_worksheet("Auditoría")

    for c, (_, titulo) in enumerate(_COLS):
        ws.write(0, c, titulo, hdr)
    for r, fila in enumerate(filas, 1):
        for c, (clave, _) in enumerate(_COLS):
            ws.write(r, c, str(fila.get(clave, "")))
    ws.set_column(0, 0, 19)
    ws.set_column(1, 4, 22)
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, max(len(filas), 1), len(_COLS) - 1)
    wb.close()
    return buf.getvalue()
