"""Plantillas de Excel para las cargas masivas -- encabezados + una fila de
ejemplo, para que la persona sepa exactamente qué columnas llenar sin tener
que adivinar (pedido 2026-09-13: "las cargas masivas deben tener [opción]
para descargar formato y más detalle de qué cargan")."""

from __future__ import annotations

import io

import xlsxwriter


def _plantilla(hoja: str, columnas: list[str], ejemplo: list) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white"})
    nota = wb.add_format({"italic": True, "font_color": "#888888"})
    ws = wb.add_worksheet(hoja)
    ws.write_row(0, 0, columnas, hdr)
    ws.write_row(1, 0, ejemplo)
    ws.write(2, 0, "↑ fila de ejemplo -- borrala antes de subir el archivo", nota)
    ws.set_column(0, max(len(columnas) - 1, 0), 20)
    wb.close()
    return buf.getvalue()


def plantilla_carga_empleados() -> bytes:
    """`EMPLEADO` es la única columna obligatoria -- `parse_carga_masiva_empleados`
    acepta cualquier otra columna presente y actualiza solo esas (ver su
    docstring); acá se ilustra con las más comunes."""
    return _plantilla(
        "Carga masiva",
        ["EMPLEADO", "CARGO", "SECCION", "SUELDO"],
        ["1234", "GUARDIA", "OPERACIONES", "460"],
    )


def plantilla_carga_observaciones() -> bytes:
    """Columnas obligatorias de `parse_carga_masiva_observaciones`: EMPLEADO,
    PERIODO (AAAA-MM), TEXTO."""
    return _plantilla(
        "Carga masiva",
        ["EMPLEADO", "PERIODO", "TEXTO"],
        ["1234", "2026-09", "Ejemplo de observación"],
    )
