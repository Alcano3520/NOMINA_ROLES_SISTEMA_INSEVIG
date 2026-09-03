"""Builders de Excel del módulo Préstamos."""

from __future__ import annotations

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
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white"})
    money = wb.add_format({"num_format": "#,##0.00"})
    ws = wb.add_worksheet("Historial")
    ws.write(0, 0, f"{empleado} — {nombre}", hdr)
    ws.write_row(2, 0, ["FECHA", "CONCEPTO", "VALOR", "ORIGEN", "NUMERO", "CUADRE"], hdr)
    for r, m in enumerate(movimientos, 3):
        ws.write(r, 0, m.fecha)
        ws.write(r, 1, m.concepto)
        ws.write_number(r, 2, m.valor, money)
        ws.write(r, 3, m.origen)
        ws.write(r, 4, m.numero)
        ws.write(r, 5, "SÍ" if m.es_cuadre else "")
    ws.freeze_panes(3, 0)

    from core.repos.prestamos import agrupar_por_numero

    ws2 = wb.add_worksheet("Resumen por préstamo")
    ws2.write_row(0, 0, ["NUMERO", "DESDE", "HASTA", "PRESTADO", "ABONADO", "SALDO", "CUOTAS"], hdr)
    resumen = agrupar_por_numero(list(movimientos))
    for r, g in enumerate(resumen, 1):
        ws2.write(r, 0, g.numero)
        ws2.write(r, 1, g.desde)
        ws2.write(r, 2, g.hasta)
        ws2.write_number(r, 3, g.prestado, money)
        ws2.write_number(r, 4, g.abonado, money)
        ws2.write_number(r, 5, g.saldo, money)
        ws2.write_number(r, 6, g.cuotas)
    ws2.freeze_panes(1, 0)
    wb.close()
    return buf.getvalue()
