"""Rol de pago (payslip) en PDF A4. Porta `dibujar_rol_en_posicion` de
`roles/Roles_Principal.pyw`.

Entrada: `EmpleadoNomina` (de `core.datos.service`). Salida: bytes PDF.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from core.datos.port import EmpleadoNomina
from core.utils import a_float, normalizar_cedula

_INGRESOS_EXTRA = [
    ("REEMBOLSOS", "REEMBOLSOS"),
    ("DECIMO_TERCERA", "DECIMO TERCER SUELDO"),
    ("DECIMO_CUARTA", "DECIMO CUARTO SUELDO"),
    ("BONIFICACION", "BONIFICACION"),
    ("MANIOBRAS", "MANIOBRAS"),
    ("MOVILIZACION", "MOVILIZACION"),
]
_DESCUENTOS = [
    ("APORT_IESS", "APORT.IESS"),
    ("PRESTAMOS_QUIROGRAFARIOS", "PRESTAMOS QUIROGRAFARIOS"),
    ("PRESTAMOS_COMPANIA", "PRESTAMOS COMPAÑIA"),
    ("ANTICIPO_SUELDO", "ANTICIPO DE SUELDO"),
    ("ANTICIPOS_OTROS", "ANTICIPOS OTROS"),
    ("ANTICIPOS_SURTIDOS", "ANTICIPOS SURTIDOS"),
    ("APORT_IESS_CONYUGE", "APORTE IESS CONYUGE"),
    ("IMPUESTO_RENTA", "IMPUESTO A LA RENTA"),
    ("MULTAS", "MULTAS"),
    ("PENSION_ALIMENTICIA", "PENSION ALIMENTICIA"),
    ("PRESTAMO_HIPOTECARIO", "PRESTAMO HIPOTECARIO"),
]


@dataclass
class OpcionesRol:
    fecha_desde: str = ""
    fecha_hasta: str = ""
    dos_por_hoja: bool = False
    logo_bytes: bytes | None = None


def _dibujar(c, d: dict, opt: OpcionesRol, width, height, y_offset: float) -> None:
    margin = 40
    base_y = y_offset

    def g(k: str) -> float:
        return a_float(d.get(k))

    c.rect(margin - 10, base_y + height / 2 - 350, width - 2 * (margin - 10), 310)

    if opt.logo_bytes:
        try:
            from reportlab.lib.utils import ImageReader

            img = ImageReader(io.BytesIO(opt.logo_bytes))
            lw = lh = 60
            c.drawImage(
                img,
                width - (margin - 10) - lw - 10,
                base_y + height / 2 - 350 + 310 - lh - 5,
                width=lw, height=lh, preserveAspectRatio=True, mask="auto",
            )
        except Exception:  # noqa: BLE001
            pass

    c.setFont("Times-Bold", 14)
    ty = base_y + height / 2 - 60
    c.drawCentredString(width / 2, ty, "SOBRES DE PAGOS")
    c.drawCentredString(width / 2, ty - 15, "INSEVIG CIA.LTDA.")

    c.setFont("Times-Roman", 11)
    y = base_y + height / 2 - 95
    c.drawString(margin, y, f"Cedula empleado: {normalizar_cedula(d.get('CEDULA'))}")
    c.drawString(margin, y - 12, f"Nombre del Empleado: {d.get('APELLIDOS_NOMBRES', '')}     ({d.get('EMPLEADO', '')})")
    c.drawString(margin, y - 24, f"Periodo de pago: Desde {opt.fecha_desde} Hasta {opt.fecha_hasta}")
    c.drawString(margin, y - 36, f"Departamento: {d.get('DEPTO', '')}     Cargo: {d.get('CARGO', '')}")

    table_top = y - 50
    table_bottom = table_top - 200
    tw = width - 2 * margin
    c.rect(margin, table_bottom, tw, table_top - table_bottom)
    col_concept, col_deduct, col_net = margin + 5, margin + 310, margin + 415

    c.setFont("Times-Italic", 10)
    hy = table_top - 12
    c.drawString(col_concept, hy, "Concepto")
    c.drawString(margin + 205, hy, "Ingresos")
    c.drawString(col_deduct, hy, "Descuentos")
    c.drawString(col_net, hy, "Neto a Recibir")
    for x in (200, 305, 410):
        c.line(margin + x, table_bottom, margin + x, table_top)
    c.line(margin, hy - 5, margin + tw, hy - 5)

    c.setFont("Times-Roman", 12)
    y = hy - 15
    lh = 12
    ingresos = 0.0
    egresos = 0.0

    sueldo, dias = g("SUELDO"), g("DIAS")
    if sueldo > 0:
        c.drawString(col_concept, y, f"SUELDO                     {int(dias)} Dias")
        c.drawRightString(col_deduct - 10, y, f"{sueldo:.2f}")
        ingresos += sueldo
        y -= lh

    overtime = g("SOBRETIEMPO_25") + g("SOBRETIEMPO_50") + g("SOBRETIEMPO_100")
    if overtime > 0:
        c.drawString(col_concept, y, "HORAS EXTRAS(noct-suplem-extraor)")
        c.drawRightString(col_deduct - 10, y, f"{overtime:.2f}")
        ingresos += overtime
        y -= lh

    # Fondo de reserva: si RPEMPLEA no lo trae (0), el legado lo calcula sobre
    # SUELDO+BONIF+MANIOBRAS+SOBRETIEMPOS y lo muestra como ingreso Y como
    # descuento ("...EN IESS"), dejando el neto igual (fondo depositado al IESS).
    fr_bd = g("FONDO_RESERVA")
    fr_en_iess = False
    if fr_bd == 0:
        base_fr = (
            g("SUELDO") + g("BONIFICACION") + g("MANIOBRAS")
            + g("SOBRETIEMPO_25") + g("SOBRETIEMPO_50") + g("SOBRETIEMPO_100")
        )
        fr = round(base_fr * 0.0833, 2)
        fr_en_iess = fr > 0
    else:
        fr = fr_bd
    if fr > 0:
        c.drawString(col_concept, y, "FONDOS DE RESERVA 8.33%")
        c.drawRightString(col_deduct - 10, y, f"{fr:.2f}")
        ingresos += fr
        y -= lh

    for col, label in _INGRESOS_EXTRA:
        v = g(col)
        if v > 0:
            c.drawString(col_concept, y, label)
            c.drawRightString(col_deduct - 10, y, f"{v:.2f}")
            ingresos += v
            y -= lh

    if fr_en_iess:
        c.drawString(col_concept, y, "FONDOS DE RESERVA 8.33% EN IESS")
        c.drawRightString(col_net - 10, y, f"{fr:.2f}")
        egresos += fr
        y -= lh

    for col, label in _DESCUENTOS:
        v = g(col)
        if v > 0:
            c.drawString(col_concept, y, label)
            c.drawRightString(col_net - 10, y, f"{v:.2f}")
            egresos += v
            y -= lh

    total_y = table_bottom + 25
    c.line(margin, total_y, margin + tw, total_y)
    c.setFont("Times-Roman", 14)
    c.drawString(col_concept, total_y - 15, "Total a Pagar ===========>")
    c.drawRightString(col_deduct - 10, total_y - 15, f"{ingresos:.2f}")
    c.drawRightString(col_net - 10, total_y - 15, f"{egresos:.2f}")
    c.drawRightString(margin + tw - 10, total_y - 15, f"{ingresos - egresos:.2f}")

    fy = base_y + height / 2 - 410
    c.drawCentredString(width / 2, fy, "F I R M A")
    c.line(width / 2 - 80, fy + 10, width / 2 + 80, fy + 10)


def rol_pago_pdf(empleado: EmpleadoNomina, opciones: OpcionesRol | None = None) -> bytes:
    opt = opciones or OpcionesRol()
    d = empleado.to_dict()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    if opt.dos_por_hoja:
        _dibujar(c, d, opt, width, height, y_offset=height / 2)
        _dibujar(c, d, opt, width, height, y_offset=0)
    else:
        _dibujar(c, d, opt, width, height, y_offset=0)
    c.showPage()
    c.save()
    return buf.getvalue()
