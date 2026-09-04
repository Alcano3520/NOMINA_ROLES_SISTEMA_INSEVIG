"""Builder de Excel del módulo Bitácora (agenda de cobro de liquidación)."""

from __future__ import annotations

import datetime as dt
import io

import xlsxwriter

from core.repos.bitacora import fecha_texto_es
from core.utils import normalizar_cedula

_COLUMNAS = [
    ("id", "ID"),
    ("apellidos_nombres", "Apellidos y Nombres"),
    ("cedula", "Cédula"),
    ("cargo", "Puesto"),
    ("telefono_celular", "Teléfono"),
    ("fecha_ingreso", "Fecha Ingreso"),
    ("fecha_salida", "Fecha Salida"),
    ("fecha_firma_acuerdo", "Firma Acuerdo"),
    ("fecha_cobro", "Fecha Cobro"),
    ("hora", "Hora"),
    ("en_sistema", "Texto para el sistema"),
    ("finiquito", "Finiquito"),
    ("liq_lista_cobro", "Liq. Lista Cobro"),
    ("lugar_firma", "Lugar Firma"),
    ("forma_pago", "Forma de Pago"),
    ("cheque_num", "Cheque #"),
    ("banco", "Banco"),
    ("horas_suspension", "Hrs. Susp."),
    ("qap", "QAP"),
    ("estado", "Estado"),
    ("periodo", "Período"),
    ("registrado_por", "Registrado por"),
]


def reporte_agenda_xlsx(filas: list[dict], *, titulo: str = "AGENDA DE LIQUIDACIÓN") -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    banner = wb.add_format({
        "bold": True, "font_size": 12, "bg_color": "#0D1B2A", "font_color": "white",
        "align": "center", "valign": "vcenter",
    })
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white", "border": 1})
    cell = wb.add_format({"border": 1})
    num = wb.add_format({"border": 1, "num_format": "#,##0.00"})
    ws = wb.add_worksheet("AGENDA")

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
            elif key in ("fecha_ingreso", "fecha_salida", "fecha_firma_acuerdo",
                         "fecha_cobro", "liq_lista_cobro"):
                ws.write(i, j, fecha_texto_es(v) if v else "", cell)
            elif key == "qap":
                ws.write(i, j, "SÍ" if v else "", cell)
            elif key == "horas_suspension":
                ws.write_number(i, j, float(v or 0), num)
            else:
                ws.write(i, j, "" if v is None else str(v), cell)

    for j, (_key, label) in enumerate(_COLUMNAS):
        ws.set_column(j, j, min(max(len(label) + 2, 12), 40))
    ws.freeze_panes(4, 0)
    wb.close()
    return buf.getvalue()
