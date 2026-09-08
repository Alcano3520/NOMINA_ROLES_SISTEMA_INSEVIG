"""Comprobante individual de vacaciones (GOCE / PAGO) en PDF.

Port fiel de `VACACIONES_SISTEMA_INSEVIG/src/pdf_generator.py`
(`generar_pago` / `generar_goce` + `_build_header_table` / `_build_sig_table`),
adaptado a este repo:
  - devuelve `bytes` (no escribe a disco),
  - el QR se dibuja con `reportlab.graphics.barcode.qr` desde el texto que
    produce `core.repos.vacaciones.qr_texto()` (no se usa la librería `qrcode`),
  - el logo sale de `assets/logo_insevig.png`,
  - la config del formato (empresa, firmante, código de documento) va inline
    en vez de `config/formato_config.yaml`.

Datos: `core.repos.vacaciones.datos_comprobante(vac_id)` (mismas claves que el
`data_extractor.py` original, para que esto sea un trasplante directo).
"""

from __future__ import annotations

import calendar
import datetime
import io
from pathlib import Path

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PAGE_W, PAGE_H = A4
pt = 1.0

# ── Config del formato (en el .pyw: config/formato_config.yaml) ───────────────
EMPRESA_NOMBRE = 'COMPAÑÍA DE SEGURIDAD INTEGRAL "INSEVIG" CIA. LTDA.'
EMPRESA_NOMBRE_GOCE = 'COMPAÑÍA DE SEGURIDAD INTEGRAL "INSEVIG" CÍA. LTDA.'
EMPRESA_CORTA = "INSEVIG CIA. LTDA."
FIRMANTE_NOMBRE = "MSC. OMAR CAMPOVERDE"
FIRMANTE_CARGO = "GERENTE GENERAL"
TITULO_PAGO = "LIQUIDACIÓN DE VACACIONES PAGADAS"
TITULO_GOCE = "GOCE DE VACACIONES"
CODIGO_DOC = "FO-GTH-03-03"
VERSION_DOC = "3"

_CFG = {
    "empresa_nombre": EMPRESA_NOMBRE,
    "empresa_nombre_goce": EMPRESA_NOMBRE_GOCE,
    "empresa_corta": EMPRESA_CORTA,
    "firmante_nombre": FIRMANTE_NOMBRE,
    "firmante_cargo": FIRMANTE_CARGO,
    "titulo_pago": TITULO_PAGO,
    "titulo_goce": TITULO_GOCE,
    "codigo_doc": CODIGO_DOC,
    "version_doc": VERSION_DOC,
}

_LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "logo_insevig.png"

BLACK = colors.black
WHITE = colors.white
GRAY_CALC = colors.HexColor("#d0d0d0")
GRAY_LABEL = colors.HexColor("#dfdfdf")
GRAY_PAGO = colors.HexColor("#f2f2f2")

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def _c(key: str) -> str:
    return _CFG.get(key, "")


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _s(val, default: str = "") -> str:
    return str(val).strip() if val is not None else default


def _f(val) -> float:
    try:
        return float(str(val).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _fmt_fecha_mes(mes_data: dict) -> str:
    mes = mes_data.get("mes")
    anio = mes_data.get("anio")
    if mes and anio:
        try:
            last = calendar.monthrange(int(anio), int(mes))[1]
            return f"{last} de {MESES_ES[int(mes)]} de {anio}"
        except (KeyError, ValueError):
            pass
    return _s(mes_data.get("fecha", ""))


def _fmt_date(val: str) -> str:
    """YYYY-MM-DD -> DD-MM-YYYY. Lo demás pasa tal cual."""
    if val and len(val) == 10 and val[4] == "-":
        try:
            y, m, d = val.split("-")
            return f"{d}-{m}-{y}"
        except ValueError:
            pass
    return _s(val)


def _ps(font: str = "Courier", size: float = 8.5, bold: bool = False,
        align: int = TA_LEFT, color=BLACK, leading_mult: float = 1.2) -> ParagraphStyle:
    fname = f"{font}-Bold" if bold else font
    return ParagraphStyle(
        name=f"_ps_{fname}_{size}_{align}",
        fontName=fname, fontSize=size, leading=size * leading_mult,
        textColor=color, alignment=align,
    )


def _qr_drawing(texto: str, lado_mm: float = 22) -> Drawing:
    w = QrCodeWidget(texto or " ", barLevel="M")
    b = w.getBounds()
    bw, bh = b[2] - b[0], b[3] - b[1]
    lado = lado_mm * mm
    d = Drawing(lado, lado, transform=[lado / bw, 0, 0, lado / bh, 0, 0])
    d.add(w)
    return d


# ── SHARED HEADER TABLE ──────────────────────────────────────────────────────
def _build_header_table(data: dict, qr_text: str | None, usable_w: float,
                        font: str, doc_title: str, qr_size: float = 28 * mm) -> Table:
    logo_w = 32 * mm
    info_w = 53 * mm
    title_w = usable_w - logo_w - info_w
    year = datetime.datetime.now().year

    qr_cell = _qr_drawing(qr_text or "", qr_size / mm) if qr_text is not None else Paragraph("", _ps(font, 7))
    info_rows = [
        [qr_cell],
        [Paragraph(f"Fecha: {year}", _ps(font, 7))],
        [Paragraph(f'Versión: {_c("version_doc")}', _ps(font, 7))],
        [Paragraph(f'Código: {_c("codigo_doc")}', _ps(font, 7))],
        [Paragraph("PAGINA: 1-1", _ps(font, 7))],
    ]
    info_inner = Table(info_rows, colWidths=[info_w - 6])
    info_inner.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("LINEBELOW", (0, 0), (0, 3), 0.5, BLACK),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    empresa = _c("empresa_nombre")
    split_idx = empresa.find('"INSEVIG"')
    if split_idx < 0:
        split_idx = empresa.upper().find("INSEVIG")
    if split_idx > 0:
        linea1_emp = empresa[:split_idx].strip().rstrip(",").strip()
        linea2_emp = empresa[split_idx:].strip()
    else:
        linea1_emp, linea2_emp = empresa, ""

    title_content: list = [Paragraph(f"<b>{linea1_emp}</b>", _ps(font, 13, align=TA_CENTER))]
    if linea2_emp:
        title_content.append(Paragraph(f"<b>{linea2_emp}</b>", _ps(font, 13, align=TA_CENTER)))
    title_content += [Spacer(1, 2), Paragraph(f"<b>{doc_title}</b>", _ps(font, 12, align=TA_CENTER))]

    logo_cell: object = ""
    if _LOGO_PATH.exists():
        logo_cell = Image(str(_LOGO_PATH), width=logo_w - 4 * mm, height=logo_w - 4 * mm)

    header_table = Table([[logo_cell, title_content, info_inner]], colWidths=[logo_w, title_w, info_w])
    header_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.5, BLACK),
        ("INNERGRID", (0, 0), (-1, -1), 1.0, BLACK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return header_table


# ── SHARED SIGNATURE TABLE ───────────────────────────────────────────────────
def _build_sig_table(nombre: str, cedula: str, usable_w: float, font: str,
                     rrhh_label: str = "T. HUMANO") -> Table:
    sig_h = 95 * pt
    sig_w1 = usable_w * 0.25
    sig_w2 = usable_w * 0.25
    sig_w3 = usable_w * 0.50

    huella_w = 70 * pt
    huella_h = 88 * pt
    huella_box = Table([[Paragraph("", _ps(font, 7, align=TA_CENTER))]],
                       colWidths=[huella_w], rowHeights=[huella_h])
    huella_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, BLACK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))

    emp_text_w = sig_w3 - huella_w - 8 * mm
    emp_sig = Table(
        [[HRFlowable(width=emp_text_w * 0.88, thickness=1, color=BLACK)],
         [Paragraph(f"<b>{nombre}</b>", _ps(font, 7.5, bold=True, align=TA_CENTER))],
         [Paragraph("Firma Conforme", _ps(font, 7, align=TA_CENTER))]],
        colWidths=[emp_text_w],
    )
    emp_sig.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    emp_cell = Table([[huella_box, emp_sig]], colWidths=[huella_w + 4 * mm, emp_text_w])
    emp_cell.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))

    def _sig_label(title: str, name: str = "", subtitle: str = "") -> list:
        return [
            HRFlowable(width=(sig_w1 - 8 * mm) * 0.88, thickness=1, color=BLACK),
            Paragraph(f"<b>{title}</b>", _ps(font, 8, bold=True, align=TA_CENTER)),
            Paragraph(name if name else " ", _ps(font, 7, align=TA_CENTER)),
            Paragraph(subtitle if subtitle else " ", _ps(font, 7, align=TA_CENTER)),
        ]

    sig_data = [[
        _sig_label("EMPLEADOR", _c("firmante_nombre"), _c("empresa_corta")),
        _sig_label(rrhh_label),
        emp_cell,
    ]]
    sig_table = Table(sig_data, colWidths=[sig_w1, sig_w2, sig_w3], rowHeights=[sig_h])
    sig_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.0, BLACK),
        ("INNERGRID", (0, 0), (-1, -1), 1.0, BLACK),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return sig_table


# ═══════════════════════════════════════════════════════════════════════════════
# PAGO
# ═══════════════════════════════════════════════════════════════════════════════

def _build_pago(data: dict, qr_text: str) -> bytes:
    margin = 10 * mm
    usable_w = PAGE_W - 2 * margin
    font = "Courier"

    def p(text, size=8.5, bold=False, align=TA_LEFT, color=BLACK):
        return Paragraph(_s(text), _ps(font, size, bold, align, color))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=margin)
    story: list = []

    story.append(_build_header_table(data, qr_text, usable_w, font, _c("titulo_pago"), qr_size=22 * mm))
    story.append(Spacer(1, 1 * mm))

    # ── INFO ──
    lbl_w = 24 * mm
    val_w1 = (usable_w - 2 * lbl_w) * 0.48
    val_w2 = (usable_w - 2 * lbl_w) * 0.52

    def lbl(t):
        return Paragraph(f"<b><u>{t}</u></b>", _ps(font, 8.5))

    def val(t):
        return Paragraph(_s(t), _ps(font, 8.5))

    info_data = [
        [lbl("NOMBRES:"), val(data.get("nombre")), lbl("CÉDULA:"), val(data.get("cedula"))],
        [lbl("CARGO:"), val(data.get("cargo")), lbl("PUESTO:"), val(data.get("area"))],
        [lbl("INGRESO:"), val(_fmt_date(_s(data.get("fecha_ingreso")))), "", ""],
        [lbl("PERIODO:"), val(_s(data.get("periodo"))), "", ""],
        [lbl("DESDE EL:"), val(_fmt_date(_s(data.get("fecha_desde")))),
         lbl("HASTA EL:"), val(_fmt_date(_s(data.get("fecha_hasta"))))],
    ]
    info_table = Table(info_data, colWidths=[lbl_w, val_w1, lbl_w, val_w2])
    info_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.5, BLACK),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#cccccc")),
        ("SPAN", (1, 2), (3, 2)),
        ("SPAN", (1, 3), (3, 3)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 1 * mm))

    # ── CALCULO ──
    cw = [usable_w * 0.10, usable_w * 0.45, usable_w * 0.22, usable_w * 0.23]
    calc_rows = [[
        p("CD.", 8.5, bold=True, align=TA_CENTER, color=WHITE),
        p("FECHA DE CORTE", 8.5, bold=True, align=TA_CENTER, color=WHITE),
        p("VALORES GANADOS", 8.5, bold=True, align=TA_CENTER, color=WHITE),
        p("", 8.5, color=WHITE),
    ]]
    meses = data.get("meses_detalle", []) or []
    subtotal = 0.0
    for i in range(12):
        if i < len(meses):
            fecha_str = _fmt_fecha_mes(meses[i])
            valor = _f(meses[i].get("valor", 0))
            subtotal += valor
            val_str = f"{valor:,.2f}"
        else:
            fecha_str, val_str = "", ""
        calc_rows.append([
            p(str(i + 1), 8.5, align=TA_CENTER),
            p(fecha_str, 8.0, align=TA_LEFT),
            p(val_str, 8.5, align=TA_RIGHT),
            p("", 8.5),
        ])
    if subtotal == 0:
        subtotal = _f(data.get("subtotal", 0))
    div24 = _f(data.get("valor_15_dias")) or (subtotal / 24 if subtotal else 0.0)

    calc_rows.append([
        p("1. TOTAL (SUMA DE VALORES GANADOS):", 8.5, bold=True, align=TA_RIGHT),
        "",
        p(f"{subtotal:,.2f}", 8.5, bold=True, align=TA_RIGHT),
        p(f"/ 24 = {div24:,.2f}", 8.5, bold=True, align=TA_CENTER),
    ])
    R_TOTAL = 13

    dias_gozados_pago = int(data.get("dias_gozados") or 0)
    gozo = _f(data.get("valor_gozados"))
    dias_adic = int(data.get("dias_adicionales") or 0)
    val_adic = _f(data.get("valor_adicionales"))
    anticipo = _f(data.get("anticipo"))

    cur = R_TOTAL + 1
    R_GOZO = R_ADIC = R_ANTIC = None
    if dias_gozados_pago > 0:
        calc_rows.append([
            p(f"TOMÓ {dias_gozados_pago} DÍAS COMO GOZO DE VACACIONES:", 8.5, bold=True, align=TA_RIGHT),
            "", p("(-)", 8.5, bold=True, align=TA_CENTER), p(f"{gozo:,.2f}", 8.5, bold=True, align=TA_CENTER),
        ])
        R_GOZO = cur
        cur += 1
    if dias_adic > 0:
        calc_rows.append([
            p(f"{dias_adic} DÍAS ADICIONALES (Art. 69):", 8.5, bold=True, align=TA_RIGHT),
            "", p("(+)", 8.5, bold=True, align=TA_CENTER), p(f"{val_adic:,.2f}", 8.5, bold=True, align=TA_CENTER),
        ])
        R_ADIC = cur
        cur += 1
    if anticipo > 0:
        calc_rows.append([
            p("Anticipo de Vacaciones:", 8.5, bold=True, align=TA_RIGHT),
            "", p("(-)", 8.5, bold=True, align=TA_CENTER), p(f"{anticipo:,.2f}", 8.5, bold=True, align=TA_CENTER),
        ])
        R_ANTIC = cur
        cur += 1
    R_NETO = cur

    total_neto = div24 - gozo + val_adic - anticipo
    calc_rows.append([
        p("TOTAL NETO A RECIBIR POR VACACIONES:", 10, bold=True, align=TA_RIGHT),
        "", p(f"$ {total_neto:,.2f}", 11, bold=True, align=TA_CENTER), "",
    ])

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), BLACK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("BOX", (0, 0), (-1, -1), 1.5, BLACK),
        ("INNERGRID", (0, 1), (-1, 12), 0.4, colors.HexColor("#dddddd")),
        ("SPAN", (0, R_TOTAL), (1, R_TOTAL)),
        ("BOX", (0, R_TOTAL), (-1, R_TOTAL), 1.5, BLACK),
        ("INNERGRID", (2, R_TOTAL), (-1, R_TOTAL), 1.0, BLACK),
        ("BACKGROUND", (0, R_NETO), (-1, R_NETO), GRAY_CALC),
        ("SPAN", (0, R_NETO), (1, R_NETO)),
        ("SPAN", (2, R_NETO), (3, R_NETO)),
        ("BOX", (0, R_NETO), (-1, R_NETO), 1.5, BLACK),
        ("INNERGRID", (2, R_NETO), (-1, R_NETO), 1.5, BLACK),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for R in (R_GOZO, R_ADIC, R_ANTIC):
        if R is not None:
            style_cmds += [
                ("SPAN", (0, R), (1, R)),
                ("BOX", (0, R), (-1, R), 1.0, BLACK),
                ("INNERGRID", (2, R), (-1, R), 1.0, BLACK),
            ]
    calc_table = Table(calc_rows, colWidths=cw)
    calc_table.setStyle(TableStyle(style_cmds))
    story.append(calc_table)
    story.append(Spacer(1, 1 * mm))

    # ── PAGO ──
    lbl2_w = usable_w * 0.18
    rem = usable_w - 2 * lbl2_w
    val2_w = rem * 0.40
    val3_w = rem * 0.60
    fecha_pago = _fmt_date(_s(data.get("fecha_pago") or datetime.datetime.now().strftime("%Y-%m-%d")))

    def plbl(t):
        return Paragraph(f"<b>{t}</b>", _ps(font, 8.5))

    def pval(t):
        return Paragraph(_s(t), _ps(font, 8.5))

    pago_data = [
        [plbl("FECHA DE PAGO:"), pval(fecha_pago),
         plbl("FORMA DE PAGO:"), pval(_s(data.get("forma_pago")).upper())],
        [plbl("CTA.CTE.NO.:"), pval(data.get("cta_cte_no")),
         plbl("CHEQUE NO.:"), pval(data.get("cheque_no"))],
        [plbl("BANCO:"), pval(data.get("banco")), "", ""],
        [plbl("OBSERVACIONES:"), pval(data.get("observaciones")), "", ""],
    ]
    pago_table = Table(pago_data, colWidths=[lbl2_w, val2_w, lbl2_w, val3_w])
    pago_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.5, BLACK),
        ("INNERGRID", (0, 0), (-1, -1), 1.0, BLACK),
        ("BACKGROUND", (0, 0), (0, -1), GRAY_PAGO),
        ("BACKGROUND", (2, 0), (2, -1), GRAY_PAGO),
        ("SPAN", (1, 2), (3, 2)),
        ("SPAN", (1, 3), (3, 3)),
        ("BACKGROUND", (2, 2), (3, 2), WHITE),
        ("BACKGROUND", (2, 3), (3, 3), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("MINROWHEIGHT", (0, 3), (-1, 3), 8 * mm),
    ]))
    story.append(pago_table)
    story.append(Spacer(1, 1 * mm))

    story.append(_build_sig_table(_s(data.get("nombre")), _s(data.get("cedula")),
                                  usable_w, font, rrhh_label="T. HUMANO"))
    doc.build(story)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# GOCE
# ═══════════════════════════════════════════════════════════════════════════════

def _build_goce(data: dict, qr_text: str) -> bytes:
    margin = 8 * mm
    usable_w = PAGE_W - 2 * margin
    font = "Helvetica"
    inner_pad = 10 * mm

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=margin)
    story: list = []

    story.append(_build_header_table(data, qr_text, usable_w, font, _c("titulo_goce")))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("<b><u>GOCE DE VACACIONES</u></b>", _ps(font, 11, bold=True, align=TA_CENTER)))
    story.append(Spacer(1, 4 * mm))

    lbl_w = 115 * pt
    val_w = usable_w - 2 * inner_pad - lbl_w

    def p(text, size=8.2, bold=False, align=TA_LEFT, color=BLACK):
        return Paragraph(_s(text), _ps(font, size, bold, align, color))

    worker_rows = [
        [p("APELLIDOS Y NOMBRES:", bold=True), p(_s(data.get("nombre")))],
        [p("CÉDULA DE CIUDADANÍA:", bold=True), p(_s(data.get("cedula")))],
        [p("FECHA DE INGRESO:", bold=True), p(_fmt_date(_s(data.get("fecha_ingreso"))))],
    ]
    worker_table = Table(worker_rows, colWidths=[lbl_w, val_w])
    worker_table.setStyle(TableStyle([
        ("LINEBELOW", (1, 0), (1, -1), 1.0, BLACK),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    padded_worker = Table([[worker_table]], colWidths=[usable_w])
    padded_worker.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), inner_pad),
        ("RIGHTPADDING", (0, 0), (-1, -1), inner_pad),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(padded_worker)
    story.append(Spacer(1, 3 * mm))

    legal_text = (
        "Mediante el presente documento, confirmo mi goce de días de Vacaciones, "
        "que me concede la compañía denominada "
        f'<b>{_c("empresa_nombre_goce")}</b>, '
        f'a través de su representante legal <b>{_c("firmante_nombre")}</b>, '
        "Segun Art. 69 GOCE DE VACACIONES ANUALES del Codigo de Trabajo, "
        "se detalla en el siguiente bloque los dias en que tome mis vacaciones, "
        "de conformidad con la ley."
    )
    legal_para = Paragraph(legal_text, _ps(font, 8.2, align=TA_JUSTIFY, leading_mult=1.25))
    legal_table = Table([[legal_para]], colWidths=[usable_w])
    legal_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, BLACK),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, BLACK),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), inner_pad),
        ("RIGHTPADDING", (0, 0), (-1, -1), inner_pad),
    ]))
    story.append(legal_table)
    story.append(Spacer(1, 4 * mm))

    g_lbl_w = 80 * pt
    inner_w = usable_w - 2 * inner_pad
    val_dw = (inner_w - 2 * g_lbl_w) / 2

    def dlbl(t):
        return Paragraph(f"<b>{t}</b>", _ps(font, 8.2))

    def dval(t, bold=False):
        return Paragraph(f"<b>{_s(t)}</b>" if bold else _s(t), _ps(font, 8.2))

    dias_goce = int(data.get("dias_goce") or data.get("dias_tomados") or 0)
    dias_gozados = int(data.get("dias_gozados_periodo") or data.get("dias_gozados") or 0)
    dias_pendient = int(data.get("dias_pendientes") or 0)
    periodo_str = _s(data.get("periodo"))
    fi_str = _fmt_date(_s(data.get("fecha_ingreso")))

    details_data = [
        [dlbl("CARGO:"), dval(data.get("cargo")), dlbl("PUESTO:"), dval(data.get("area"))],
        [dlbl("F. INGRESO:"), dval(fi_str), dlbl("PERIODO:"), dval(periodo_str)],
        [dlbl("DESDE EL:"), dval(_s(data.get("fecha_desde"))),
         dlbl("HASTA EL:"), dval(_s(data.get("fecha_hasta")))],
        [dlbl("DÍAS DE VACACIONES:"), dval(dias_goce, bold=True),
         dlbl("DÍAS GOZADOS:"), dval(dias_gozados, bold=True)],
        [dlbl("DÍAS PENDIENTES:"), dval(dias_pendient, bold=True), "", ""],
    ]
    details_inner = Table(details_data, colWidths=[g_lbl_w, val_dw, g_lbl_w, val_dw])
    details_inner.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.5, BLACK),
        ("INNERGRID", (0, 0), (-1, -1), 1.0, BLACK),
        ("BACKGROUND", (0, 0), (0, -1), GRAY_LABEL),
        ("BACKGROUND", (2, 0), (2, -1), GRAY_LABEL),
        ("SPAN", (1, 4), (3, 4)),
        ("BACKGROUND", (2, 4), (3, 4), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    padded_details = Table([[details_inner]], colWidths=[usable_w])
    padded_details.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), inner_pad),
        ("RIGHTPADDING", (0, 0), (-1, -1), inner_pad),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(padded_details)
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph(
        "<b>ESTOY CONFORME CON LOS DIAS QUE HE TOMADO, POR GOCE DE VACACIONES</b>",
        _ps(font, 8.5, bold=True, align=TA_CENTER),
    ))
    story.append(Spacer(1, 5 * mm))

    obs = _s(data.get("observaciones"))
    obs_line = f"<b>OBSERVACIONES:</b>  {obs}" if obs else "<b>OBSERVACIONES:</b>"
    obs_table = Table([[Paragraph(obs_line, _ps(font, 8.2))]], colWidths=[usable_w])
    obs_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, BLACK),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, BLACK),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), inner_pad),
        ("RIGHTPADDING", (0, 0), (-1, -1), inner_pad),
    ]))
    story.append(obs_table)
    story.append(Spacer(1, 8 * mm))

    story.append(_build_sig_table(_s(data.get("nombre")), _s(data.get("cedula")),
                                  usable_w, font, rrhh_label="RECURSOS HUMANOS"))
    doc.build(story)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# API
# ═══════════════════════════════════════════════════════════════════════════════

def comprobante_pdf(data: dict, qr: str) -> bytes:
    """`data` de `vacaciones.datos_comprobante`, `qr` de `vacaciones.qr_texto`.

    PAGO -> `LIQUIDACIÓN DE VACACIONES PAGADAS` (Courier, márgen 10 mm, sin QR
    en el cuerpo por el Copy-Protect de las impresoras).
    GOCE -> `GOCE DE VACACIONES` (Helvetica, márgen 8 mm, con QR).
    """
    es_pago = str(data.get("tipo") or "").lower().startswith("pag")
    return _build_pago(data, qr) if es_pago else _build_goce(data, qr)


# ── Comprobante de anticipo (recibo puntual, sin QR ni desglose) ──────────────

def _st(size: float = 8.5, *, bold: bool = False, align: int = TA_LEFT) -> ParagraphStyle:
    return _ps("Courier", size, bold, align)


def _p(txt, size: float = 8.5, *, bold: bool = False, align: int = TA_LEFT) -> Paragraph:
    return Paragraph("" if txt is None else str(txt), _st(size, bold=bold, align=align))


def _tabla_anticipo(data: dict, usable_w: float) -> Table:
    filas = [
        [_p("Empleado:", bold=True), _p(data.get("nombre"))],
        [_p("Cédula:", bold=True), _p(data.get("cedula"))],
        [_p("Cargo:", bold=True), _p(data.get("cargo"))],
        [_p("Período:", bold=True), _p(data.get("periodo"))],
        [_p("Concepto:", bold=True), _p("ANTICIPO A CUENTA DE VACACIONES")],
        [_p("Valor:", bold=True), _p(f"${_f(data.get('valor', 0)):,.2f}")],
        [_p("En letras:", bold=True), _p(data.get("en_letras"))],
    ]
    t = Table(filas, colWidths=[usable_w * 0.22, usable_w * 0.78])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, BLACK),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _firmas_anticipo(usable_w: float) -> Table:
    def celda(titulo: str) -> list:
        return [_p("_______________________________", align=TA_CENTER),
                _p(f"<b>{titulo}</b>", align=TA_CENTER)]

    filas = [[
        Table([[x] for x in celda("RECIBÍ CONFORME")], colWidths=[usable_w * 0.4]),
        Table([[x] for x in celda("AUTORIZADO POR")], colWidths=[usable_w * 0.4]),
    ]]
    t = Table(filas, colWidths=[usable_w * 0.4, usable_w * 0.4])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 14)]))
    return t


def anticipo_pdf(data: dict) -> bytes:
    """Comprobante simple de anticipo de vacaciones. Porta
    `app.py::_generar_pdf_anticipo` — sin QR ni desglose mensual.

    `data`: `nombre`, `cedula`, `cargo`, `periodo`, `valor`, `en_letras`
    (`core.repos.vacaciones.valor_en_letras(valor)`), `fecha`, `referencia`.
    """
    margin = 20 * mm
    usable_w = A4[0] - margin
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=margin / 2, rightMargin=margin / 2,
                            topMargin=margin / 2, bottomMargin=margin / 2)
    story: list = [
        _p("INSEVIG CIA. LTDA.", 14, bold=True, align=TA_CENTER),
        _p("COMPROBANTE DE ANTICIPO DE VACACIONES", 14, bold=True, align=TA_CENTER),
        Spacer(1, 4 * mm),
        _p(f"Referencia: {data.get('referencia', '')}   |   Fecha: {data.get('fecha', '')}", 10, align=TA_CENTER),
        Spacer(1, 6 * mm),
        _tabla_anticipo(data, usable_w),
        Spacer(1, 15 * mm),
        _firmas_anticipo(usable_w),
    ]
    doc.build(story)
    return buf.getvalue()
