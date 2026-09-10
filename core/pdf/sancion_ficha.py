"""PDF de la ficha de una sanción — trasplante de
`nucleo_modular/reportes.generar_pdf_sancion` (origen
`modern_viewer.ModernSancionViewer._exportar_pdf`). Devuelve bytes.
"""

from __future__ import annotations

import logging
from io import BytesIO

log = logging.getLogger(__name__)


def sancion_pdf(sancion: dict, nombre_supervisor: str = "No asignado") -> bytes | None:
    """PDF de una sanción individual. `None` si falta reportlab. `sancion` ya
    enriquecida (empleado_cargo/departamento del enriquecimiento); `nombre_supervisor`
    ya resuelto.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        log.error("reportlab no está instalado")
        return None

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    story: list = []

    titulo = ParagraphStyle("SancionTitulo", parent=styles["Heading1"], fontSize=18,
                            textColor=colors.HexColor("#2E86AB"), spaceAfter=30, alignment=1)
    story.append(Paragraph("REPORTE DE SANCIÓN", titulo))

    tstyle = TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e9ecef")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
    ])

    ced = str(sancion.get("empleado_cedula", "N/A")).strip()
    if ced != "N/A" and ced.endswith(".0"):
        ced = ced[:-2]

    story.append(Paragraph("INFORMACIÓN DEL EMPLEADO", styles["Heading2"]))
    emp = Table([
        ["Código:", str(sancion.get("empleado_cod", "N/A"))],
        ["Cédula:", ced],
        ["Nombre:", str(sancion.get("empleado_nombre", "N/A"))],
        ["Cargo:", str(sancion.get("empleado_cargo", "N/A"))],
        ["Departamento:", str(sancion.get("empleado_departamento", "N/A"))],
    ], colWidths=[2 * inch, 4 * inch])
    emp.setStyle(tstyle)
    story.append(emp)
    story.append(Spacer(1, 20))

    story.append(Paragraph("DETALLES DE LA SANCIÓN", styles["Heading2"]))
    det = Table([
        ["Tipo:", str(sancion.get("tipo_sancion", "N/A"))],
        ["Fecha:", str(sancion.get("fecha", "N/A"))],
        ["Hora:", str(sancion.get("hora", "N/A"))],
        ["Supervisor:", nombre_supervisor],
        ["Agente:", str(sancion.get("agente", "N/A"))],
        ["Estado:", str(sancion.get("status", "N/A"))],
    ], colWidths=[2 * inch, 4 * inch])
    det.setStyle(tstyle)
    story.append(det)
    story.append(Spacer(1, 20))

    for titulo_sec, clave in (
        ("OBSERVACIONES", "observaciones"),
        ("COMENTARIOS DE GERENCIA", "comentarios_gerencia"),
        ("COMENTARIOS RRHH", "comentarios_rrhh"),
    ):
        val = sancion.get(clave, "")
        if val:
            story.append(Paragraph(titulo_sec, styles["Heading2"]))
            story.append(Paragraph(str(val), styles["BodyText"]))
            story.append(Spacer(1, 12))

    doc.build(story)
    return buf.getvalue()
