"""Ficha del empleado en PDF (todas las secciones). Sustituye el 'Imprimir'
del sistema anterior, que estaba sin implementar.
"""

from __future__ import annotations

import datetime as dt
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.repos.empleados import ETIQUETAS, GRUPOS


def _etq(k: str) -> str:
    return ETIQUETAS.get(k, k.replace("_", " ").capitalize())


def ficha_empleado_pdf(codigo: str, campos: dict) -> bytes:
    """`campos`: {NOMBRE_COLUMNA: valor} ya limpio (como en el editor web)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    h = styles["Heading2"]
    small = styles["Normal"]
    small.fontSize = 8

    nombre = f"{campos.get('APELLIDOS', '')} {campos.get('NOMBRES', '')}".strip()
    elems = [
        Paragraph("INSEVIG CIA. LTDA. — Ficha de empleado", styles["Title"]),
        Paragraph(
            f"<b>{codigo}</b> — {nombre} &nbsp;|&nbsp; C.I. {campos.get('CEDULA', '')} "
            f"&nbsp;|&nbsp; generado {dt.datetime.now():%d/%m/%Y %H:%M}",
            small,
        ),
        Spacer(1, 6 * mm),
    ]

    for grupo, claves in GRUPOS.items():
        filas = [
            [_etq(k), str(campos.get(k, "") or "")]
            for k in claves
        ]
        if not any(v for _, v in filas):
            continue
        elems.append(Paragraph(grupo, h))
        t = Table(filas, colWidths=[55 * mm, 110 * mm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1a4d8f")),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 4 * mm))

    doc.build(elems)
    return buf.getvalue()
