"""PDF individual de liquidación (finiquito), 1 sola hoja.

Porta `generar_pdf_individual` de `LIQUIDACIONES_SISTEMA_INSEVIG/nucleo_modular/
generacion_pdf.py` (a su vez, extracción fiel de `_generar_reporte_individual`
en `Generador_Liquidaciones_INSEVIG.pyw`). El original recibe el dict `fila`
crudo del cálculo; aquí `_a_fila` arma ese mismo dict desde nuestro
`core.repos.liquidaciones.Liquidacion`, y `liquidacion_pdf` es la construcción
del documento, verbatim.

Campos que el `.pyw` original sí tiene y esta migración no calcula todavía
(desglose mensual de vacaciones/décimos, ajuste de cuadre, otras
indemnizaciones): se pasan en 0 / vacíos — el PDF los omite igual que el
original cuando no hay valor, no se inventa nada.
"""

from __future__ import annotations

import datetime as dt
import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.repos.liquidaciones import Liquidacion

_CONCEPTOS_DESCUENTO_PDF = (
    ("APORT_IESS", "Aporte IESS Personal"),
    ("APORT_IESS_CONYUGE", "Aporte IESS Cónyuge"),
    ("PRESTAMOS_QUIROGRAFARIOS", "Préstamo Quirografario"),
    ("PRESTAMOS_COMPANIA", "Préstamo Compañía"),
    ("PRESTAMO_HIPOTECARIO", "Préstamo Hipotecario"),
    ("ANTICIPO_SUELDO", "Anticipo de Sueldo"),
    ("ANTICIPOS_OTROS", "Anticipos Otros"),
    ("ANTICIPOS_SURTIDOS", "Anticipos Surtidos"),
    ("MULTAS", "Multas"),
    ("PENSION_ALIMENTICIA", "Pensión Alimenticia"),
    ("IMPUESTO_RENTA", "Impuesto a la Renta"),
    ("ANTICIPOS_OTROS_L", "Anticipo Otros (liquidado)"),
    ("ANTICIPO_L_DESAHUCIO", "Anticipo Desahucio (liquidado)"),
)

_ESTADO_LABEL_VAC = {
    "PAGADO": "Ya pagado", "GOZADO_COMPLETO": "Ya gozado (≥15d)",
    "GOZADO_PARCIAL": "Gozado parcial", "PENDIENTE": "Pendiente",
    "SIN_SALDO": "Sin saldo", "SIN_VERIFICAR": "Sin verificar",
}


def _tiempo_trabajado_texto(fecha_ingreso: str | None, fecha_salida: str | None) -> str:
    from dateutil.relativedelta import relativedelta

    try:
        d_ing = dt.date.fromisoformat(str(fecha_ingreso))
        d_sal = dt.date.fromisoformat(str(fecha_salida))
    except (ValueError, TypeError):
        return "—"
    diff = relativedelta(d_sal, d_ing)
    partes = []
    if diff.years:
        partes.append(f"{diff.years} año{'s' if diff.years != 1 else ''}")
    if diff.months:
        partes.append(f"{diff.months} mes{'es' if diff.months != 1 else ''}")
    if diff.days or not partes:
        partes.append(f"{diff.days} día{'s' if diff.days != 1 else ''}")
    return ", ".join(partes)


def _a_fila(liq: Liquidacion) -> dict:
    """`Liquidacion` -> dict `fila` (mismas claves que el motor legado)."""
    c = liq.campos
    detalle_vac = [
        {
            "periodo": d.periodo, "estado": d.estado,
            "dias_gozados": d.dias_gozados, "monto_bruto": d.monto_bruto,
            "incluido": d.incluido,
        }
        for d in liq.detalle_vacaciones
    ]
    verificado = not any(d.estado == "SIN_VERIFICAR" for d in liq.detalle_vacaciones)
    return {
        "COD": liq.empleado, "CEDULA": liq.cedula,
        "NOMBRES": liq.nombre, "NOMCARGO": liq.cargo, "NOMDEP": liq.depto,
        "SECCION": liq.seccion, "REMUNERACION": liq.sueldo_base,
        "FECHA_INGRESO": liq.fecha_ingreso, "FECHA_SALIDA": liq.fecha_salida,
        "MOTIVO_SALIDA": liq.motivo_salida,
        "SUELDO": c.get("SUELDO", 0), "HORAS_25": c.get("HORAS_25", 0),
        "HORAS_50": c.get("HORAS_50", 0), "HORAS_100": c.get("HORAS_100", 0),
        "VAL_SOBT_25": c.get("VAL_SOBT_25", 0), "VAL_SOBT_50": c.get("VAL_SOBT_50", 0),
        "VAL_SOBT_100": c.get("VAL_SOBT_100", 0), "FONDO_RESERVA": c.get("FONDO_RESERVA", 0),
        "MANIOBRAS": c.get("MANIOBRAS", 0), "MOVILIZACION": c.get("MOVILIZACION", 0),
        "REEMBOLSOS": c.get("REEMBOLSOS", 0), "BONIFICACION": c.get("BONIFICACION", 0),
        "VACACIONES_PERIODO_ANTERIOR": c.get("VACACIONES_ANTERIOR", 0),
        "VACACIONES_ULTIMO_PERIODO": c.get("VACACIONES_ULTIMO", 0),
        "DECIMA_TERCERA_ANTERIOR": c.get("DECIMA_TERCERA_ANTERIOR", 0),
        "DECIMA_TERCERA_ACTUAL": c.get("DECIMA_TERCERA_ACTUAL", 0),
        "DECIMA_TERCERA_ANTERIOR_MESES": [], "DECIMA_TERCERA_ACTUAL_MESES": [],
        "DECIMA_CUARTA_ANTERIOR": c.get("DECIMA_CUARTA_ANTERIOR", 0),
        "DECIMA_CUARTA_ACTUAL": c.get("DECIMA_CUARTA_ACTUAL", 0),
        "DECIMA_CUARTA_ANTERIOR_DIAS": 0, "DECIMA_CUARTA_ACTUAL_DIAS": 0,
        "_INCLUIR_DEC13_ANTERIOR": True, "_INCLUIR_DEC14_ANTERIOR": True,
        "VACACIONES_CALCULADAS": c.get("VACACIONES_CALCULADAS", 0),
        "DESAHUCIO": c.get("DESAHUCIO", 0), "DESAHUCIO_SOBRE_INGRESOS_REALES": False,
        "INDEMNIZACION_DESPIDO": c.get("INDEM_DESPIDO", 0),
        "OTRAS_INDEMNIZACIONES": 0, "OTROS_VALORES": 0, "AJUSTE_CUADRE": 0,
        "APORT_IESS": c.get("APORT_IESS", 0),
        "PRESTAMOS_QUIROGRAFARIOS": c.get("PRESTAMOS_QUIROGRAFARIOS", 0),
        "PRESTAMOS_COMPANIA": c.get("PRESTAMOS_COMPANIA", 0),
        "ANTICIPO_SUELDO": c.get("ANTICIPO_SUELDO", 0),
        "ANTICIPOS_OTROS": c.get("ANTICIPOS_OTROS", 0),
        "ANTICIPOS_SURTIDOS": c.get("ANTICIPOS_SURTIDOS", 0),
        "APORT_IESS_CONYUGE": c.get("APORT_IESS_CONYUGE", 0),
        "IMPUESTO_RENTA": c.get("IMPUESTO_RENTA", 0), "MULTAS": c.get("MULTAS", 0),
        "PENSION_ALIMENTICIA": c.get("PENSION_ALIMENTICIA", 0),
        "PRESTAMO_HIPOTECARIO": c.get("PRESTAMO_HIPOTECARIO", 0),
        "ANTICIPOS_OTROS_L": c.get("ANTICIPOS_OTROS_L", 0),
        "ANTICIPO_L_DESAHUCIO": c.get("ANTICIPO_L_DESAHUCIO", 0),
        "TOTAL_INGRESOS": c.get("TOTAL_INGRESOS", 0),
        "TOTAL_DESCUENTOS": c.get("TOTAL_DESCUENTOS", 0),
        "TOTAL_A_RECIBIR": c.get("TOTAL_A_RECIBIR", 0),
        "VACACIONES_VERIFICADO_SUPABASE": verificado,
        "VACACIONES_DETALLE_PERIODOS": detalle_vac,
    }


def liquidacion_pdf(liq: Liquidacion, *, mostrar_insumos: bool = False, es_simulacion: bool = True) -> bytes:
    """PDF de 1 hoja de la liquidación (ReportLab). `es_simulacion=True`
    agrega el aviso de "SIMULACIÓN / NO VÁLIDO PARA PAGO"."""
    fila = _a_fila(liq)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        rightMargin=0.45 * inch, leftMargin=0.45 * inch,
        topMargin=0.35 * inch, bottomMargin=0.35 * inch,
    )
    elements: list = []
    styles = getSampleStyleSheet()

    pad_estrecho = [
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]

    if es_simulacion:
        aviso_style = ParagraphStyle(
            "Aviso", parent=styles["Heading2"], fontSize=11,
            textColor=colors.white, alignment=TA_CENTER,
            backColor=colors.HexColor("#c0392b"),
            spaceBefore=2, spaceAfter=2, fontName="Helvetica-Bold")
        elements.append(Paragraph(
            "⚠ SIMULACIÓN / LIQUIDACIÓN DE PRUEBA — NO VÁLIDO PARA PAGO", aviso_style))
        elements.append(Spacer(1, 0.06 * inch))

    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=14,
                                  textColor=colors.HexColor("#1a4d8f"), alignment=TA_CENTER,
                                  spaceAfter=0)
    elements.append(Paragraph("LIQUIDACIÓN DE BENEFICIOS SOCIALES", title_style))
    elements.append(Paragraph("INSEVIG CIA. LTDA.",
                     ParagraphStyle("Sub", parent=styles["Normal"], fontSize=9,
                                    alignment=TA_CENTER)))
    elements.append(Spacer(1, 0.08 * inch))

    celda_wrap_style = ParagraphStyle("CeldaWrap", parent=styles["Normal"], fontSize=8, leading=9.5)

    def _celda(texto):
        return Paragraph(str(texto), celda_wrap_style)

    emp_data = [
        ["Código:", str(fila["COD"]), "Cargo:", _celda(fila.get("NOMCARGO", ""))],
        ["Cédula:", str(fila["CEDULA"]), "Depto.:", _celda(fila.get("NOMDEP", ""))],
        ["Nombre:", _celda(fila["NOMBRES"]), "Sección:", _celda(fila.get("SECCION", ""))],
        ["Sueldo Base:", f"${float(fila.get('REMUNERACION', fila.get('SUELDO', 0)) or 0):.2f}",
         "Tiempo trabajado:", _tiempo_trabajado_texto(
             fila.get("FECHA_INGRESO"), fila.get("FECHA_SALIDA"))],
        ["Fecha Ingreso:", fila["FECHA_INGRESO"], "Fecha Salida:", fila["FECHA_SALIDA"]],
    ]
    if fila.get("MOTIVO_SALIDA"):
        emp_data.append(["Tipo Salida:", _celda(fila["MOTIVO_SALIDA"]), "", ""])
    emp_table = Table(emp_data, colWidths=[1.1 * inch, 2.15 * inch, 1.1 * inch, 2.15 * inch])
    emp_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ] + pad_estrecho))
    elements.append(emp_table)
    elements.append(Spacer(1, 0.1 * inch))

    filas_remun_pdf = [("Sueldo (proporcional días trabajados)",
                         float(fila.get("SUELDO", 0) or 0), True)]
    for codigo_horas, codigo_valor, etiqueta in (
            ("HORAS_25", "VAL_SOBT_25", "Horas 25% (recargo nocturno)"),
            ("HORAS_50", "VAL_SOBT_50", "Horas 50% (suplementarias)"),
            ("HORAS_100", "VAL_SOBT_100", "Horas 100% (extraordinarias)")):
        etiqueta_fila = (f"{etiqueta} — {fila.get(codigo_horas, 0)} horas"
                          if mostrar_insumos else etiqueta)
        filas_remun_pdf.append((etiqueta_fila, float(fila.get(codigo_valor, 0) or 0), False))
    filas_remun_pdf.append(("Fondo de Reserva 8,33%", float(fila.get("FONDO_RESERVA", 0) or 0), False))
    filas_remun_pdf.append(("Maniobras", float(fila.get("MANIOBRAS", 0) or 0), False))
    filas_remun_pdf.append(("Movilización", float(fila.get("MOVILIZACION", 0) or 0), False))
    filas_remun_pdf.append(("Reembolsos", float(fila.get("REEMBOLSOS", 0) or 0), False))
    filas_remun_pdf.append(("Bonificación", float(fila.get("BONIFICACION", 0) or 0), False))
    total_remun = sum(valor for _et, valor, _s in filas_remun_pdf)
    remun_data = [["REMUNERACIÓN DEL MES DE SALIDA", "VALOR"]]
    remun_data += [[etiqueta, f"${valor:.2f}"] for etiqueta, valor, siempre in filas_remun_pdf
                   if siempre or valor]
    remun_data.append(["TOTAL REMUNERACIÓN DEL MES", f"${total_remun:.2f}"])
    remun_table = Table(remun_data, colWidths=[4.5 * inch, 2 * inch])
    remun_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#1a4d8f")),
        ("TEXTCOLOR", (0, 0), (1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, -1), (1, -1), colors.HexColor("#e6f2ff")),
        ("FONTNAME", (0, -1), (1, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f5f5f5")]),
    ] + pad_estrecho))
    elements.append(remun_table)
    elements.append(Spacer(1, 0.1 * inch))

    def _anios_completos(fecha_ing: str | None, fecha_sal: str | None) -> int:
        from dateutil.relativedelta import relativedelta

        try:
            d_ing = dt.date.fromisoformat(str(fecha_ing))
            d_sal = dt.date.fromisoformat(str(fecha_sal))
        except (ValueError, TypeError):
            return 0
        diff = relativedelta(d_sal, d_ing)
        frac = diff.years + diff.months / 12.0 + diff.days / 365.25 + 0.00278
        return max(int(frac), 0)

    anios_desahucio = _anios_completos(fila.get("FECHA_INGRESO"), fila.get("FECHA_SALIDA"))
    desahucio_nota = (
        (" (sobre ingresos reales)" if fila.get("DESAHUCIO_SOBRE_INGRESOS_REALES")
         else " (sobre sueldo básico)") + f" · {anios_desahucio} años")
    dec13_ant_incl = (float(fila.get("DECIMA_TERCERA_ANTERIOR", 0) or 0)
                      if fila.get("_INCLUIR_DEC13_ANTERIOR") else 0.0)
    dec14_ant_incl = (float(fila.get("DECIMA_CUARTA_ANTERIOR", 0) or 0)
                      if fila.get("_INCLUIR_DEC14_ANTERIOR") else 0.0)
    total_beneficios_real = round(
        dec13_ant_incl + float(fila.get("DECIMA_TERCERA_ACTUAL", 0) or 0) +
        dec14_ant_incl + float(fila.get("DECIMA_CUARTA_ACTUAL", 0) or 0) +
        float(fila.get("VACACIONES_CALCULADAS", 0) or 0) +
        float(fila.get("DESAHUCIO", 0) or 0) +
        float(fila.get("INDEMNIZACION_DESPIDO", 0) or 0) +
        float(fila.get("OTRAS_INDEMNIZACIONES", 0) or 0) +
        float(fila.get("OTROS_VALORES", 0) or 0) +
        float(fila.get("AJUSTE_CUADRE", 0) or 0), 2)
    filas_benef_pdf = [
        ("Vacaciones pendientes", float(fila.get("VACACIONES_CALCULADAS", 0) or 0)),
        ("Décima Tercera", dec13_ant_incl + float(fila.get("DECIMA_TERCERA_ACTUAL", 0) or 0)),
        ("Décima Cuarta", dec14_ant_incl + float(fila.get("DECIMA_CUARTA_ACTUAL", 0) or 0)),
        (f"Bonificación Desahucio (25%){desahucio_nota}", float(fila.get("DESAHUCIO", 0) or 0)),
    ]
    benef_data = [["LIQUIDACIÓN", "VALOR"]]
    benef_data += [[et, f"${v:.2f}"] for et, v in filas_benef_pdf if v]
    benef_data.append(["TOTAL LIQUIDACIÓN", f"${total_beneficios_real:.2f}"])
    benef_table = Table(benef_data, colWidths=[4.5 * inch, 2 * inch])
    benef_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#1a4d8f")),
        ("TEXTCOLOR", (0, 0), (1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, -1), (1, -1), colors.HexColor("#e6f2ff")),
        ("FONTNAME", (0, -1), (1, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f5f5f5")]),
    ] + pad_estrecho))
    elements.append(benef_table)

    total_ingresos_pdf = total_remun + total_beneficios_real
    total_ingresos_table = Table(
        [["TOTAL DE INGRESOS", f"${total_ingresos_pdf:.2f}"]],
        colWidths=[4.5 * inch, 2 * inch])
    total_ingresos_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#28a745")),
        ("TEXTCOLOR", (0, 0), (1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ] + pad_estrecho))
    elements.append(total_ingresos_table)

    if fila.get("VACACIONES_VERIFICADO_SUPABASE", True):
        verif_texto = "✅ Verificado en Supabase: vacaciones no incluyen períodos ya pagados."
        verif_color = colors.HexColor("#28a745")
    else:
        verif_texto = ("⚠ NO se pudo verificar en Supabase si ya se pagaron vacaciones. "
                        "Revisar manualmente antes de liquidar.")
        verif_color = colors.HexColor("#c0392b")
    elements.append(Paragraph(
        verif_texto,
        ParagraphStyle("Verif", parent=styles["Normal"], fontSize=7.5,
                       textColor=verif_color, spaceBefore=2, spaceAfter=0)))
    elements.append(Spacer(1, 0.06 * inch))

    detalle_vac = fila.get("VACACIONES_DETALLE_PERIODOS") or []
    if detalle_vac:
        detalle_vac_data = [["Período", "Estado", "Días\nGozados", "Valor (÷24)", "Incluido"]]
        for d in detalle_vac:
            valor = (d.get("monto_bruto") or 0) / 24
            detalle_vac_data.append([
                d.get("periodo", ""),
                _ESTADO_LABEL_VAC.get(d.get("estado"), d.get("estado", "")),
                str(d.get("dias_gozados") or 0) if d.get("dias_gozados") else "—",
                f"${valor:.2f}",
                "Sí" if d.get("incluido") else "No",
            ])
        detalle_vac_table = Table(detalle_vac_data,
                                   colWidths=[0.9 * inch, 1.6 * inch, 0.8 * inch, 1 * inch, 0.7 * inch])
        detalle_vac_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6c757d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ] + pad_estrecho))
        elements.append(Paragraph(
            "Desglose de vacaciones por período",
            ParagraphStyle("SubBenef", parent=styles["Normal"], fontSize=8,
                           fontName="Helvetica-Bold", textColor=colors.HexColor("#1a4d8f"),
                           spaceBefore=2, spaceAfter=2)))
        elements.append(detalle_vac_table)
    elements.append(Spacer(1, 0.1 * inch))

    filas_descuento = [(nombre, fila.get(codigo, 0) or 0)
                        for codigo, nombre in _CONCEPTOS_DESCUENTO_PDF
                        if (fila.get(codigo, 0) or 0)]
    if filas_descuento:
        desc_data = [["DESCUENTOS APLICADOS", "VALOR"]]
        desc_data += [[nombre, f"-${valor:.2f}"] for nombre, valor in filas_descuento]
        desc_data.append(["TOTAL DE EGRESOS", f"-${fila.get('TOTAL_DESCUENTOS', 0):.2f}"])
        desc_table = Table(desc_data, colWidths=[4.5 * inch, 2 * inch])
        desc_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#8f1a1a")),
            ("TEXTCOLOR", (0, 0), (1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, -1), (1, -1), colors.HexColor("#fde8e8")),
            ("FONTNAME", (0, -1), (1, -1), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f5f5f5")]),
        ] + pad_estrecho))
        elements.append(desc_table)
        elements.append(Spacer(1, 0.1 * inch))

    resumen_data = [
        ["RESUMEN", "VALOR"],
        ["Total nómina del mes", f"${fila.get('TOTAL_INGRESOS', 0):.2f}"],
        ["Total liquidación", f"${total_beneficios_real:.2f}"],
        ["Total de egresos", f"-${fila.get('TOTAL_DESCUENTOS', 0):.2f}"],
        ["TOTAL ESTIMADO A RECIBIR", f"${fila.get('TOTAL_A_RECIBIR', 0):.2f}"],
    ]
    resumen_table = Table(resumen_data, colWidths=[4.5 * inch, 2 * inch])
    resumen_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#1a4d8f")),
        ("TEXTCOLOR", (0, 0), (1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -2), 8.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, -1), (1, -1), colors.HexColor("#fff3cd")),
        ("FONTNAME", (0, -1), (1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (1, -1), 11),
    ] + pad_estrecho))
    elements.append(resumen_table)
    elements.append(Spacer(1, 0.12 * inch))

    nota_style = ParagraphStyle("Nota", parent=styles["Normal"], fontSize=7,
                                 textColor=colors.grey, leading=9)
    if es_simulacion:
        texto_nota = (
            "Documento de SIMULACIÓN generado con fines de referencia. Los valores se calculan "
            "con el mismo motor que la liquidación definitiva, pero pueden variar si cambian los "
            "movimientos de nómina antes del cierre del mes. No constituye comprobante de pago. "
            f"Generado: {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    else:
        texto_nota = (
            "Documento generado desde Gestión de Liquidaciones, con los valores ya guardados "
            f"en el sistema. Generado: {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    elements.append(Paragraph(texto_nota, nota_style))

    doc.build(elements)
    return buf.getvalue()
