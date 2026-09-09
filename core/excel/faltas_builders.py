"""Builders de Excel del módulo Faltas. Funciones puras: datos -> bytes.

Mismas columnas y contenido que `gestion_faltas.py` (`_exportar_log_excel` /
`_exportar_excel`), portados desde
`sistema_sanciones_RRHH/nucleo_modular/faltas_reportes.py`. El medio cambia
(openpyxl → xlsxwriter, para alinear con el resto de `core/excel/`), el reporte no.
El respaldo JSON en `respaldos/` del legado se reemplaza por `core.audit`.
"""

from __future__ import annotations

import io
from datetime import datetime

import xlsxwriter

_HDR_AZUL = {"bold": True, "bg_color": "#17375E", "font_color": "white", "border": 1}


def log_registro_xlsx(
    anio: int, mes: int,
    exitosos: list[tuple], fallidos: list[tuple],
    num_exitos: int, num_errores: int,
) -> bytes:
    """Log de un registro masivo/individual. 3 hojas: Exitosos, Errores, Resumen.

    `exitosos`: [(codigo, nombre, tipo, horas, accion)]  accion ∈ INSERTADO/ACTUALIZADO
    `fallidos`: [(codigo, nombre, error)]
    """
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format(_HDR_AZUL)
    ok_fmt = wb.add_format({"bg_color": "#D4EDDA", "border": 1})
    err_fmt = wb.add_format({"bg_color": "#F8D7DA", "border": 1, "text_wrap": True, "valign": "top"})
    titulo_ok = wb.add_format({"bold": True, "font_size": 12, "font_color": "white",
                               "bg_color": "#27AE60", "align": "center"})
    titulo_err = wb.add_format({"bold": True, "font_size": 12, "font_color": "white",
                               "bg_color": "#C0392B", "align": "center"})
    neg = wb.add_format({"bold": True, "font_color": "#27AE60"})
    rojo = wb.add_format({"bold": True, "font_color": "#C0392B"})

    if exitosos:
        ws = wb.add_worksheet("Exitosos")
        ws.merge_range(0, 0, 0, 4, f"REGISTRADOS EXITOSAMENTE - {anio}-{mes:02d}", titulo_ok)
        ws.write_row(2, 0, ["Código", "Nombre", "Tipo", "Horas", "Acción"], hdr)
        for i, (cod, nom, tipo, hrs, accion) in enumerate(exitosos, start=3):
            ws.write_row(i, 0, [cod, nom, tipo, f"{hrs}h", accion], ok_fmt)
        ws.set_column(0, 0, 12)
        ws.set_column(1, 1, 30)
        ws.set_column(2, 4, 13)

    if fallidos:
        ws = wb.add_worksheet("Errores")
        ws.merge_range(0, 0, 0, 2, f"ERRORES EN EL REGISTRO - {anio}-{mes:02d}", titulo_err)
        ws.write_row(2, 0, ["Código", "Nombre", "Descripción del Error"], hdr)
        for i, (cod, nom, error) in enumerate(fallidos, start=3):
            ws.write_row(i, 0, [cod, nom, str(error)], err_fmt)
        ws.set_column(0, 0, 12)
        ws.set_column(1, 1, 30)
        ws.set_column(2, 2, 60)

    ws = wb.add_worksheet("Resumen")
    ws.merge_range(0, 0, 0, 1, f"RESUMEN - {anio}-{mes:02d}",
                   wb.add_format({"bold": True, "font_size": 12, "align": "center"}))
    ws.write(2, 0, "Fecha:")
    ws.write(2, 1, datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    ws.write(4, 0, "Exitosos:")
    ws.write(4, 1, num_exitos, neg)
    ws.write(5, 0, "Errores:")
    ws.write(5, 1, num_errores, rojo)
    ws.write(7, 0, "TOTAL:")
    ws.write(7, 1, num_exitos + num_errores, wb.add_format({"bold": True, "font_size": 12}))
    ws.set_column(0, 0, 20)
    ws.set_column(1, 1, 30)

    wb.close()
    return buf.getvalue()


def periodo_xlsx(datos_periodo: list[dict], anio: int, mes: int) -> bytes:
    """Detalle de un período (una hoja). Cada fila = dict con claves
    empleado / nombre / cedula / totaus / observ / fecha_ven (salida de
    `repo.listar_periodo` pasada por `dataclasses.asdict`, o equivalente).
    """
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#17375e", "font_color": "white", "align": "center"})
    texto = wb.add_format({"num_format": "@"})
    ws = wb.add_worksheet(f"Faltas {anio}-{mes:02d}")
    ws.write_row(0, 0, ["Codigo", "Nombre", "Cedula", "Horas", "Dias", "Observaciones", "Fecha Venc."], hdr)
    for i, row in enumerate(datos_periodo, start=1):
        totaus = float(row.get("totaus", 0) or 0)
        ws.write(i, 0, str(row.get("empleado", "")))
        ws.write(i, 1, str(row.get("nombre", "")))
        ws.write(i, 2, str(row.get("cedula", "")), texto)
        ws.write(i, 3, totaus)
        ws.write(i, 4, totaus // 8)
        ws.write(i, 5, str(row.get("observ", "")))
        ws.write(i, 6, str(row.get("fecha_ven", "")))
    ws.set_column(1, 1, 30)
    ws.set_column(5, 5, 60)
    wb.close()
    return buf.getvalue()
