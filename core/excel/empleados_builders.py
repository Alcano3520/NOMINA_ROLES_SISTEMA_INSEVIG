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


_COLS_BUSQUEDA = [
    ("empleado", "CÓDIGO"), ("apellidos", "APELLIDOS"), ("nombres", "NOMBRES"),
    ("cedula", "CÉDULA"), ("cargo", "CGO"), ("cargo_nombre", "NOMBRE CARGO"),
    ("depto", "DPT"), ("depto_nombre", "NOMBRE DEPTO"), ("sueldo", "SUELDO"),
    ("telefono", "TELÉFONO"), ("email", "EMAIL"), ("estado", "ESTADO"),
]


def busqueda_avanzada_xlsx(filas: list[dict], titulo: str = "EMPLEADOS") -> bytes:
    """Exporta el resultado de la Búsqueda Avanzada / Vista Completa."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white"})
    money = wb.add_format({"num_format": "#,##0.00"})
    ws = wb.add_worksheet(titulo[:31])
    ws.write_row(0, 0, [c[1] for c in _COLS_BUSQUEDA], hdr)
    for r, f in enumerate(filas, 1):
        for c, (k, _) in enumerate(_COLS_BUSQUEDA):
            v = f.get(k, "")
            if k == "sueldo":
                ws.write_number(r, c, float(v or 0), money)
            else:
                ws.write(r, c, "" if v is None else str(v))
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, len(filas), len(_COLS_BUSQUEDA) - 1)
    wb.close()
    return buf.getvalue()


def catalogos_xlsx(catalogos: dict[str, list[dict]]) -> bytes:
    """Vuelca los catálogos de DBTABLAS a un Excel (una hoja por tipo)."""
    nombres = {"FNC": "Cargos", "SEC": "Secciones", "DPT": "Departamentos", "BAN": "Bancos"}
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white"})
    for tipo, filas in catalogos.items():
        ws = wb.add_worksheet(nombres.get(tipo, tipo)[:31])
        ws.write_row(0, 0, ["CÓDIGO", "NOMBRE"], hdr)
        for r, x in enumerate(sorted(filas, key=lambda z: z.get("nombre", "")), 1):
            ws.write(r, 0, str(x.get("codigo", "")))
            ws.write(r, 1, str(x.get("nombre", "")))
        ws.freeze_panes(1, 0)
    if not catalogos:
        wb.add_worksheet("vacío")
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
