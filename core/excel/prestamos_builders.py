"""Builders de Excel del módulo Préstamos."""

from __future__ import annotations

import datetime as dt
import io

import xlsxwriter


def saldos_xlsx(saldos: list) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white"})
    money = wb.add_format({"num_format": "#,##0.00"})
    ws = wb.add_worksheet("Saldos CLASE 205")
    ws.write_row(0, 0, ["EMPLEADO", "APELLIDOS Y NOMBRES", "CEDULA", "SALDO"], hdr)
    for r, s in enumerate(saldos, 1):
        ws.write(r, 0, s.empleado)
        ws.write(r, 1, s.apellidos_nombres)
        ws.write(r, 2, s.cedula)
        ws.write_number(r, 3, s.saldo, money)
    total = round(sum(s.saldo for s in saldos), 2)
    ws.write(len(saldos) + 1, 2, "TOTAL", hdr)
    ws.write_number(len(saldos) + 1, 3, total, money)
    ws.freeze_panes(1, 0)
    wb.close()
    return buf.getvalue()


def historial_xlsx(empleado: str, nombre: str, movimientos: list) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    banner = wb.add_format({
        "bold": True, "font_size": 13, "bg_color": "#0D1B2A", "font_color": "white",
        "align": "center", "valign": "vcenter",
    })
    sub = wb.add_format({"italic": True, "font_color": "#555555", "align": "center"})
    hdr = wb.add_format({
        "bold": True, "bg_color": "#1a4d8f", "font_color": "white", "border": 1,
    })
    cell = wb.add_format({"border": 1})
    money = wb.add_format({"num_format": "#,##0.00", "border": 1})
    total_lbl = wb.add_format({"bold": True, "border": 1, "bg_color": "#e8eef7"})
    total_num = wb.add_format({"bold": True, "num_format": "#,##0.00", "border": 1, "bg_color": "#e8eef7"})
    generado = dt.datetime.now().strftime("%d/%m/%Y %H:%M")

    ws = wb.add_worksheet("Historial")
    ws.set_column(0, 0, 12)
    ws.set_column(1, 1, 34)
    ws.set_column(2, 2, 13)
    ws.set_column(3, 5, 11)
    ws.merge_range(0, 0, 0, 5, "INSEVIG — HISTORIAL DE PRÉSTAMOS", banner)
    ws.merge_range(1, 0, 1, 5, f"{empleado} — {nombre}   ·   Generado: {generado}", sub)
    ws.set_row(0, 24)
    ws.write_row(3, 0, ["FECHA", "CONCEPTO", "VALOR", "ORIGEN", "NUMERO", "CUADRE"], hdr)
    fila = 4
    for m in movimientos:
        ws.write(fila, 0, m.fecha, cell)
        ws.write(fila, 1, m.concepto, cell)
        ws.write_number(fila, 2, m.valor, money)
        ws.write(fila, 3, m.origen, cell)
        ws.write(fila, 4, m.numero, cell)
        ws.write(fila, 5, "SÍ" if m.es_cuadre else "", cell)
        fila += 1
    total = round(sum(m.valor for m in movimientos), 2)
    ws.write(fila, 1, "TOTAL", total_lbl)
    ws.write_number(fila, 2, total, total_num)
    ws.freeze_panes(4, 0)

    from core.repos.prestamos import agrupar_por_numero

    ws2 = wb.add_worksheet("Resumen por préstamo")
    ws2.set_column(0, 0, 10)
    ws2.set_column(1, 2, 12)
    ws2.set_column(3, 6, 12)
    ws2.merge_range(0, 0, 0, 6, "RESUMEN POR NÚMERO DE PRÉSTAMO", banner)
    ws2.write_row(1, 0, ["NUMERO", "DESDE", "HASTA", "PRESTADO", "ABONADO", "SALDO", "CUOTAS"], hdr)
    resumen = agrupar_por_numero(list(movimientos))
    for r, g in enumerate(resumen, 2):
        ws2.write(r, 0, g.numero, cell)
        ws2.write(r, 1, g.desde, cell)
        ws2.write(r, 2, g.hasta, cell)
        ws2.write_number(r, 3, g.prestado, money)
        ws2.write_number(r, 4, g.abonado, money)
        ws2.write_number(r, 5, g.saldo, money)
        ws2.write_number(r, 6, g.cuotas, cell)
    ws2.freeze_panes(2, 0)
    wb.close()
    return buf.getvalue()
