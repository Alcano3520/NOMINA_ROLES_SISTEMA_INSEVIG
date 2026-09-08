"""Excel de liquidaciones — hoja FORMATO. Reproduce la estructura del legado
(columnas clave; los campos administrativos manuales van en blanco)."""

from __future__ import annotations

import io

import xlsxwriter

# Columnas en el orden del formato LIQUIDACIONES_REG.
COLUMNAS = [
    ("Cod", "empleado"), ("APELLIDOS Y NOMBRES", "nombre"), ("Nomcargo", "cargo"),
    ("Sueldo", "sueldo_base"), ("PUESTO DE SERVICIO", "depto"), ("CÉDULA", "cedula"),
    ("MOTIVO DE SALIDA", "motivo_salida"), ("Seccion", "seccion"),
    ("FECHA INGRESO", "fecha_ingreso"), ("FECHA SALIDA", "fecha_salida"), ("DÍAS", "dias_trabajados"),
    ("Sueldo (mov)", "SUELDO"), ("REEMBOLSOS", "REEMBOLSOS"), ("FONDO RESERVA", "FONDO_RESERVA"),
    ("BONIFICACIÓN", "BONIFICACION"), ("MANIOBRAS", "MANIOBRAS"), ("MOVILIZACIÓN", "MOVILIZACION"),
    ("HORAS 25", "HORAS_25"), ("HORAS 50", "HORAS_50"), ("HORAS 100", "HORAS_100"),
    ("VAL. SOBT 25", "VAL_SOBT_25"), ("VAL. SOBT 50", "VAL_SOBT_50"), ("VAL. SOBT 100", "VAL_SOBT_100"),
    ("TOTAL NÓMINA PENDIENTE", "_nomina_pend"),
    ("13RA ANTERIOR", "DECIMA_TERCERA_ANTERIOR"), ("13RA ACTUAL", "DECIMA_TERCERA_ACTUAL"),
    ("14TA ANTERIOR", "DECIMA_CUARTA_ANTERIOR"), ("14TA ACTUAL", "DECIMA_CUARTA_ACTUAL"),
    ("VAC. ANTERIORES", "VACACIONES_ANTERIOR"), ("VAC. ÚLTIMO", "VACACIONES_ULTIMO"),
    ("VAC. PENDIENTES (÷24)", "VACACIONES_CALCULADAS"),
    ("BONIF. DESAHUCIO 25%", "DESAHUCIO"), ("INDEM. DESPIDO", "INDEM_DESPIDO"),
    ("OTRA INDEM. 1", "_manual1"), ("OTRA INDEM. 2", "_manual2"),
    ("TOTAL BENEFICIOS SOCIALES", "_total_beneficios"),
    ("APORT. IESS", "APORT_IESS"), ("PRÉSTAMOS COMPAÑÍA", "PRESTAMOS_COMPANIA"),
    ("PRÉSTAMOS QUIROGRAFARIOS", "PRESTAMOS_QUIROGRAFARIOS"), ("ANTICIPO SUELDO", "ANTICIPO_SUELDO"),
    ("ANTICIPOS OTROS", "ANTICIPOS_OTROS"), ("ANTICIPOS SURTIDOS", "ANTICIPOS_SURTIDOS"),
    ("MULTAS", "MULTAS"), ("PENSIÓN ALIMENTICIA", "PENSION_ALIMENTICIA"),
    ("APORTE IESS CÓNYUGE", "APORT_IESS_CONYUGE"), ("PRÉSTAMO HIPOTECARIO", "PRESTAMO_HIPOTECARIO"),
    ("IMPUESTO RENTA", "IMPUESTO_RENTA"),
    ("ANTICIPOS OTROS L", "ANTICIPOS_OTROS_L"), ("ANTICIPO L DESAHUCIO", "ANTICIPO_L_DESAHUCIO"),
    ("TOTAL EGRESOS - DESCUENTOS", "TOTAL_DESCUENTOS"),
    ("TOTAL VALORES A LIQUIDAR", "TOTAL_A_RECIBIR"),
    ("FIRMA", "_firma"), ("OBSERVACIONES", "_obs"), ("FECHA ACERCAMIENTO", "_f1"),
    ("FECHA COBRO", "_f2"), ("FORMA PAGO", "_fp"), ("CHEQUE #", "_ch"), ("BANCO", "_bco"),
    ("ESTADO", "_est"), ("TOTAL VALORES NÓMINA", "_total_nomina"),
]


def _valor(liq, clave: str):
    if hasattr(liq, clave):
        return getattr(liq, clave)
    if clave.startswith("_"):
        if clave == "_nomina_pend":
            v = liq.campos
            return round(sum(v.get(k, 0) for k in (
                "SUELDO", "REEMBOLSOS", "FONDO_RESERVA", "BONIFICACION", "MANIOBRAS",
                "MOVILIZACION", "VAL_SOBT_25", "VAL_SOBT_50", "VAL_SOBT_100")), 2)
        if clave == "_total_beneficios":
            v = liq.campos
            return round(sum(v.get(k, 0) for k in (
                "DECIMA_TERCERA_ANTERIOR", "DECIMA_TERCERA_ACTUAL", "DECIMA_CUARTA_ANTERIOR",
                "DECIMA_CUARTA_ACTUAL", "VACACIONES_CALCULADAS", "DESAHUCIO", "INDEM_DESPIDO")), 2)
        return ""
    return liq.campos.get(clave, "")


def liquidaciones_xlsx(liquidaciones: list) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white", "border": 1})
    money = wb.add_format({"num_format": "#,##0.00"})
    ws = wb.add_worksheet("FORMATO")

    for c, (titulo, _) in enumerate(COLUMNAS):
        ws.write(0, c, titulo, hdr)
    r = 1
    for liq in liquidaciones:
        if liq.error:
            ws.write(r, 0, liq.cedula or "?")
            ws.write(r, 1, f"ERROR: {liq.error}")
            r += 1
            continue
        for c, (_, clave) in enumerate(COLUMNAS):
            v = _valor(liq, clave)
            if isinstance(v, (int, float)) and clave not in ("empleado",):
                ws.write_number(r, c, float(v), money)
            else:
                ws.write(r, c, "" if v is None else str(v))
        r += 1
    ws.freeze_panes(1, 2)
    wb.close()
    return buf.getvalue()


# Columnas del listado de GUARDADAS (Gestión de Liquidaciones, botón
# "⬇ Exportar a Excel") -- una fila por registro de `liquidaciones`, no
# una liquidación recién calculada (por eso las claves son columnas de la
# tabla, no de Liquidacion.campos). "responsable" no es una columna real
# de `liquidaciones` -- el .pyw lo anexa como texto libre dentro de
# `observaciones` (ver avanzar_estado en core/repos/liquidaciones.py), así
# que no se puede extraer como campo propio; se expone `observaciones`
# completa en su lugar.
COLUMNAS_LISTADO = [
    ("Código", "empleado_codigo"), ("Nombre", "nombre"), ("Cédula", "empleado_cedula"),
    ("Cargo", "cargo"), ("Fecha salida", "fecha_salida"), ("Tipo", "tipo_liquidacion"),
    ("Estado", "estado"), ("Total líquido", "total_liquido"), ("Lote", "codigo_lote"),
    ("Forma de pago", "forma_pago"), ("Cheque/comprobante", "comprobante_pago"),
    ("Fecha de pago", "fecha_pago"), ("Autorizado por", "aprobado_por_rrhh"),
    ("Observaciones", "observaciones"),
]


def listado_liquidaciones_xlsx(filas: list[dict]) -> bytes:
    """Excel del listado de liquidaciones GUARDADAS ya filtrado (Gestión de
    Liquidaciones, botón "⬇ Exportar a Excel") -- `filas` es lo que
    devuelve `listar_liquidaciones()` de `core.repos.liquidaciones`, no
    objetos `Liquidacion`."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1a4d8f", "font_color": "white", "border": 1})
    money = wb.add_format({"num_format": "#,##0.00"})
    ws = wb.add_worksheet("Liquidaciones")

    for c, (titulo, _) in enumerate(COLUMNAS_LISTADO):
        ws.write(0, c, titulo, hdr)
    for r, fila in enumerate(filas, start=1):
        for c, (_, clave) in enumerate(COLUMNAS_LISTADO):
            v = fila.get(clave)
            if isinstance(v, (int, float)):
                ws.write_number(r, c, float(v), money)
            else:
                ws.write(r, c, "" if v is None else str(v))
    ws.freeze_panes(1, 2)
    wb.close()
    return buf.getvalue()
