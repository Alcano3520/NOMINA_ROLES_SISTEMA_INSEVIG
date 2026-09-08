"""Builder de Excel del módulo Vacaciones — Reporte Completo (Pagos + Goces).

Porta `VACACIONES_SISTEMA_INSEVIG/src/reporte_general_pdf.py` /
`app.py::VentanaReportes._escribir_excel` en formato, adaptado al estilo de
`core/excel/bitacora_builders.py` (mismo banner/encabezado que el resto de la
app). El PDF individual (comprobante GOCE/PAGO por empleado, con QR) queda
pendiente de portar — no tiene builder equivalente en xlsxwriter/reportlab
aquí todavía; ver `docs/modulos/vacaciones.md`.
"""

from __future__ import annotations

import datetime as dt
import io

import xlsxwriter

from core.utils import normalizar_cedula

_COLUMNAS = [
    ("cedula", "Cédula"),
    ("apellidos", "Apellidos"),
    ("nombres", "Nombres"),
    ("cargo", "Cargo"),
    ("departamento", "Departamento"),
    ("periodo", "Período"),
    ("tipo", "Tipo"),
    ("estado_doc", "Estado"),
    ("desde", "Desde"),
    ("hasta", "Hasta"),
    ("dias_tomados", "Días"),
    ("dias_adicionales", "Días Adic."),
    ("total_pagar", "Total ($)"),
    ("anticipo", "Anticipo ($)"),
    ("fecha_pago", "Fecha Pago/Comprobante"),
    ("banco", "Banco"),
    ("no_cheque", "No. Cheque"),
    ("observaciones", "Observaciones"),
]

_NUM = {"total_pagar", "anticipo"}
_INT = {"dias_tomados", "dias_adicionales"}


def reporte_completo_xlsx(filas: list[dict], *, titulo: str = "REPORTE COMPLETO — PAGOS Y GOCES") -> bytes:
    """Porta el Excel de `VentanaReportes` para `core.repos.vacaciones.reporte_completo()`."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    banner = wb.add_format({
        "bold": True, "font_size": 12, "bg_color": "#0D1B2A", "font_color": "white",
        "align": "center", "valign": "vcenter",
    })
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white", "border": 1})
    cell = wb.add_format({"border": 1})
    num = wb.add_format({"border": 1, "num_format": "#,##0.00"})
    ws = wb.add_worksheet("REPORTE")

    ncols = len(_COLUMNAS)
    ws.merge_range(0, 0, 0, ncols - 1, f"INSEVIG — {titulo}", banner)
    ws.merge_range(
        1, 0, 1, ncols - 1,
        f"Generado: {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}   ·   {len(filas)} registro(s)",
        wb.add_format({"italic": True, "font_color": "#555555", "align": "center"}),
    )
    for j, (_key, label) in enumerate(_COLUMNAS):
        ws.write(3, j, label, hdr)

    for i, f in enumerate(filas, 4):
        for j, (key, _label) in enumerate(_COLUMNAS):
            v = f.get(key)
            if key == "cedula":
                ws.write(i, j, normalizar_cedula(v), cell)
            elif key in _NUM:
                ws.write_number(i, j, float(v or 0), num)
            elif key in _INT:
                ws.write_number(i, j, int(v or 0), cell)
            elif key == "tipo":
                ws.write(i, j, "GOCE" if v == "gozada" else "PAGO", cell)
            else:
                ws.write(i, j, "" if v is None else str(v), cell)

    for j, (_key, label) in enumerate(_COLUMNAS):
        ws.set_column(j, j, min(max(len(label) + 2, 10), 40))
    ws.freeze_panes(4, 0)
    wb.close()
    return buf.getvalue()


_COLUMNAS_PENDIENTES = [
    ("cedula", "Cédula"),
    ("apellidos", "Apellidos"),
    ("nombres", "Nombres"),
    ("cargo", "Cargo"),
    ("departamento", "Departamento"),
    ("fecha_ingreso", "Fecha Ingreso"),
    ("periodo", "Período"),
    ("dias_derecho", "Días Derecho"),
    ("dias_adicionales", "Días Adic."),
    ("dias_gozados", "Días Gozados"),
    ("dias_pendientes", "Días Pendientes"),
]
_INT_PENDIENTES = {"dias_derecho", "dias_adicionales", "dias_gozados", "dias_pendientes"}


def pendientes_global_xlsx(filas: list[dict]) -> bytes:
    """Excel de `core.repos.vacaciones.reporte_pendientes_global()` —
    días de vacaciones pendientes por empleado × período."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    banner = wb.add_format({
        "bold": True, "font_size": 12, "bg_color": "#0D1B2A", "font_color": "white",
        "align": "center", "valign": "vcenter",
    })
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white", "border": 1})
    cell = wb.add_format({"border": 1})
    ws = wb.add_worksheet("PENDIENTES")

    ncols = len(_COLUMNAS_PENDIENTES)
    total_dias = sum(int(f.get("dias_pendientes") or 0) for f in filas)
    ws.merge_range(0, 0, 0, ncols - 1, "INSEVIG — VACACIONES PENDIENTES (GLOBAL)", banner)
    ws.merge_range(
        1, 0, 1, ncols - 1,
        f"Generado: {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}   ·   "
        f"{len(filas)} registro(s)   ·   {total_dias} días pendientes en total",
        wb.add_format({"italic": True, "font_color": "#555555", "align": "center"}),
    )
    for j, (_key, label) in enumerate(_COLUMNAS_PENDIENTES):
        ws.write(3, j, label, hdr)

    for i, f in enumerate(filas, 4):
        for j, (key, _label) in enumerate(_COLUMNAS_PENDIENTES):
            v = f.get(key)
            if key == "cedula":
                ws.write(i, j, normalizar_cedula(v), cell)
            elif key in _INT_PENDIENTES:
                ws.write_number(i, j, int(v or 0), cell)
            else:
                ws.write(i, j, "" if v is None else str(v), cell)

    for j, (_key, label) in enumerate(_COLUMNAS_PENDIENTES):
        ws.set_column(j, j, min(max(len(label) + 2, 10), 40))
    ws.freeze_panes(4, 0)
    wb.close()
    return buf.getvalue()
