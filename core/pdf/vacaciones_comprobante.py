"""Comprobante individual de vacaciones (GOCE / PAGO) en PDF.

Porta la estructura de `VACACIONES_SISTEMA_INSEVIG/src/pdf_generator.py`
(`generar_pago` / `generar_goce`). **No es 1:1 pixel** con el formato HTML del
`.pyw` — es una versión funcional de una hoja con todos los datos, el QR y el
bloque de firmas. Si hace falta paridad exacta del layout, es una pasada aparte.

Datos: `core.repos.vacaciones.datos_comprobante(vac_id)`.
QR: `core.repos.vacaciones.qr_texto(data)` (formato exacto, no reimplementar).
"""

from __future__ import annotations

import io

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Config del formato (en el `.pyw` viene de config/formato_config.yaml; acá
# inline — mover a `vac_config` si se quiere editable).
EMPRESA = 'COMPAÑÍA DE SEGURIDAD INTEGRAL "INSEVIG" CIA. LTDA.'
EMPRESA_CORTA = "INSEVIG CIA. LTDA."
FIRMANTE_NOMBRE = "MSC. OMAR CAMPOVERDE"
CODIGO_DOC = "FO-GTH-03-03"
VERSION_DOC = "3"
TITULO_PAGO = "LIQUIDACIÓN DE VACACIONES PAGADAS"
TITULO_GOCE = "GOCE DE VACACIONES"

_MESES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}
_BLACK = colors.black
_GRAY = colors.HexColor("#dfdfdf")


def _st(size: float = 8.5, *, bold: bool = False, align: int = TA_LEFT) -> ParagraphStyle:
    return ParagraphStyle(
        "x", fontName="Courier-Bold" if bold else "Courier", fontSize=size,
        leading=size + 2, alignment=align,
    )


def _p(txt, size: float = 8.5, *, bold: bool = False, align: int = TA_LEFT) -> Paragraph:
    return Paragraph("" if txt is None else str(txt), _st(size, bold=bold, align=align))


def _fecha(v: object) -> str:
    s = str(v or "").strip()[:10]
    if len(s) == 10 and s[4] == "-":
        y, m, d = s.split("-")
        return f"{d}/{m}/{y}"
    return s


def _fmt_mes(m: dict) -> str:
    try:
        return f"{_MESES[int(m['mes'])].capitalize()} {int(m['anio'])}"
    except (KeyError, ValueError, TypeError):
        return ""


def _qr_drawing(texto: str, lado_mm: float = 22) -> Drawing:
    w = QrCodeWidget(texto, barLevel="M")
    b = w.getBounds()
    bw, bh = b[2] - b[0], b[3] - b[1]
    lado = lado_mm * mm
    d = Drawing(lado, lado, transform=[lado / bw, 0, 0, lado / bh, 0, 0])
    d.add(w)
    return d


def _header(data: dict, qr: str, titulo: str, usable_w: float) -> Table:
    info = Table(
        [
            [_qr_drawing(qr, 20)],
            [_p(f"Código: {CODIGO_DOC}", 7)],
            [_p(f"Versión: {VERSION_DOC}", 7)],
            [_p(f"Período: {data.get('periodo', '')}", 7)],
        ],
        colWidths=[38 * mm],
    )
    info.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                              ("TOPPADDING", (0, 0), (-1, -1), 1),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    centro = Table(
        [[_p(f"<b>{EMPRESA}</b>", 10, align=TA_CENTER)],
         [_p(f"<b>{titulo}</b>", 12, align=TA_CENTER)]],
        colWidths=[usable_w - 38 * mm],
    )
    centro.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    h = Table([[centro, info]], colWidths=[usable_w - 38 * mm, 38 * mm])
    h.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.5, _BLACK),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return h


def _info_empleado(data: dict, usable_w: float) -> Table:
    lw, vw = 24 * mm, (usable_w - 48 * mm) / 2

    def lbl(t):
        return Paragraph(f"<b><u>{t}</u></b>", _st(8.5))

    filas = [
        [lbl("NOMBRES:"), _p(data.get("nombre")), lbl("CÉDULA:"), _p(data.get("cedula"))],
        [lbl("CARGO:"), _p(data.get("cargo")), lbl("PUESTO:"), _p(data.get("area"))],
        [lbl("INGRESO:"), _p(_fecha(data.get("fecha_ingreso"))), lbl("PERÍODO:"), _p(data.get("periodo"))],
        [lbl("DESDE EL:"), _p(_fecha(data.get("fecha_desde"))),
         lbl("HASTA EL:"), _p(_fecha(data.get("fecha_hasta")))],
    ]
    t = Table(filas, colWidths=[lw, vw, lw, vw])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.2, _BLACK),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _tabla_meses(data: dict, usable_w: float) -> Table:
    meses = data.get("meses_detalle") or []
    cw = [usable_w * 0.10, usable_w * 0.55, usable_w * 0.35]
    filas = [[_p("CD.", bold=True, align=TA_CENTER), _p("FECHA DE CORTE", bold=True, align=TA_CENTER),
              _p("VALORES GANADOS", bold=True, align=TA_CENTER)]]
    subtotal = 0.0
    for i in range(12):
        if i < len(meses):
            v = float(meses[i].get("valor", 0) or 0)
            subtotal += v
            filas.append([_p(i + 1, align=TA_CENTER), _p(_fmt_mes(meses[i])),
                          _p(f"{v:,.2f}", align=TA_RIGHT)])
        else:
            filas.append([_p(i + 1, align=TA_CENTER), _p(""), _p("")])
    if subtotal == 0:
        subtotal = float(data.get("subtotal", 0) or 0)
    div24 = float(data.get("valor_15_dias") or (subtotal / 24 if subtotal else 0))
    filas.append([_p("TOTAL / 24 =", bold=True, align=TA_RIGHT),
                  _p(f"{subtotal:,.2f}", bold=True, align=TA_RIGHT),
                  _p(f"{div24:,.2f}", bold=True, align=TA_RIGHT)])
    t = Table(filas, colWidths=cw)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, _BLACK),
        ("BACKGROUND", (0, 0), (-1, 0), _BLACK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#d0d0d0")),
        ("SPAN", (0, -1), (0, -1)),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


def _resumen_pago(data: dict, usable_w: float) -> Table:
    def r(k, v):
        return [_p(k, bold=True), _p(v, align=TA_RIGHT)]

    filas = [
        r("Valor 15 días (total / 24)", f"{float(data.get('valor_15_dias', 0)):,.2f}"),
        r("Valor día", f"{float(data.get('valor_dia', 0)):,.4f}"),
        r("Días básicos", data.get("dias_basicos", 15)),
        r("Días adicionales", data.get("dias_adicionales", 0)),
        r("Días ya gozados en el período", data.get("dias_gozados_periodo", 0)),
        r("Días a pagar", data.get("dias_a_pagar", 0)),
        r("Valor días adicionales", f"{float(data.get('valor_adicionales', 0)):,.2f}"),
        r("(-) Anticipo", f"{float(data.get('anticipo', 0)):,.2f}"),
        r("TOTAL A PAGAR", f"{float(data.get('total_pagar', 0)):,.2f}"),
    ]
    if data.get("forma_pago"):
        filas.append(r("Forma de pago", data.get("forma_pago")))
    if data.get("banco"):
        filas.append(r("Banco / Cta.", f"{data.get('banco')}  {data.get('cta_cte_no', '')}"))
    if data.get("cheque_no"):
        filas.append(r("Cheque N°", data.get("cheque_no")))
    if data.get("fecha_pago"):
        filas.append(r("Fecha de pago", _fecha(data.get("fecha_pago"))))
    t = Table(filas, colWidths=[usable_w * 0.6, usable_w * 0.4])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.0, _BLACK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, len(filas) - 1 - _extra(data)), (-1, len(filas) - 1 - _extra(data)), _GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _extra(data: dict) -> int:
    return sum(1 for k in ("forma_pago", "banco", "cheque_no", "fecha_pago") if data.get(k))


def _resumen_goce(data: dict, usable_w: float) -> Table:
    def r(k, v):
        return [_p(k, bold=True), _p(v, align=TA_RIGHT)]

    filas = [
        r("Días de goce a los que tiene derecho", data.get("dias_goce", 15)),
        r("Días básicos", data.get("dias_basicos", 15)),
        r("Días adicionales", data.get("dias_adicionales", 0)),
        r("Días de este goce", data.get("dias_este_goce", data.get("dias_gozados", 0))),
        r("Días ya gozados en el período", data.get("dias_gozados_periodo", 0)),
        r("Días pendientes de goce", data.get("dias_pendientes", 0)),
    ]
    t = Table(filas, colWidths=[usable_w * 0.65, usable_w * 0.35])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.0, _BLACK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _firmas(data: dict, usable_w: float) -> Table:
    def celda(titulo, nombre="", sub=""):
        return [
            _p("_______________________________", align=TA_CENTER),
            _p(f"<b>{titulo}</b>", align=TA_CENTER),
            _p(nombre, 7.5, align=TA_CENTER),
            _p(sub, 7, align=TA_CENTER),
        ]

    filas = [[
        celda("EMPLEADOR", FIRMANTE_NOMBRE, EMPRESA_CORTA),
        celda("TALENTO HUMANO"),
        celda("EMPLEADO", data.get("nombre", ""), f"C.I. {data.get('cedula', '')}"),
    ]]
    # aplanar cada celda en un mini-Table
    filas = [[
        Table([[x] for x in c], colWidths=[usable_w * w])
        for c, w in zip(filas[0], (0.28, 0.28, 0.44), strict=True)
    ]]
    t = Table(filas, colWidths=[usable_w * 0.28, usable_w * 0.28, usable_w * 0.44])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 14)]))
    return t


def _tabla_anticipo(data: dict, usable_w: float) -> Table:
    filas = [
        [_p("Empleado:", bold=True), _p(data.get("nombre"))],
        [_p("Cédula:", bold=True), _p(data.get("cedula"))],
        [_p("Cargo:", bold=True), _p(data.get("cargo"))],
        [_p("Período:", bold=True), _p(data.get("periodo"))],
        [_p("Concepto:", bold=True), _p("ANTICIPO A CUENTA DE VACACIONES")],
        [_p("Valor:", bold=True), _p(f"${float(data.get('valor', 0)):,.2f}")],
        [_p("En letras:", bold=True), _p(data.get("en_letras"))],
    ]
    t = Table(filas, colWidths=[usable_w * 0.22, usable_w * 0.78])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, _BLACK),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _firmas_anticipo(usable_w: float) -> Table:
    def celda(titulo: str) -> list:
        return [_p("_______________________________", align=TA_CENTER), _p(f"<b>{titulo}</b>", align=TA_CENTER)]

    filas = [[
        Table([[x] for x in celda("RECIBÍ CONFORME")], colWidths=[usable_w * 0.4]),
        Table([[x] for x in celda("AUTORIZADO POR")], colWidths=[usable_w * 0.4]),
    ]]
    t = Table(filas, colWidths=[usable_w * 0.4, usable_w * 0.4])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 14)]))
    return t


def anticipo_pdf(data: dict) -> bytes:
    """Comprobante simple de anticipo de vacaciones. Porta
    `app.py::_generar_pdf_anticipo`/`_dialogo_anticipo` — sin QR ni desglose
    mensual, es un recibo puntual, no un registro persistido.

    `data`: `nombre`, `cedula`, `cargo`, `periodo`, `valor`, `en_letras`
    (`core.repos.vacaciones.valor_en_letras(valor)`), `fecha`, `referencia`.
    """
    margin = 2 * 10 * mm
    usable_w = A4[0] - margin
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=margin / 2, rightMargin=margin / 2,
                            topMargin=margin / 2, bottomMargin=margin / 2)
    story: list = [
        _p("INSEVIG S.A.", 14, bold=True, align=TA_CENTER),
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


def comprobante_pdf(data: dict, qr: str) -> bytes:
    """`data` de `vacaciones.datos_comprobante`, `qr` de `vacaciones.qr_texto`."""
    es_pago = str(data.get("tipo") or "").lower().startswith("pag")
    titulo = TITULO_PAGO if es_pago else TITULO_GOCE
    margin = 10 * mm
    usable_w = A4[0] - 2 * margin
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=margin)
    story: list = [
        _header(data, qr, titulo, usable_w), Spacer(1, 2 * mm),
        _info_empleado(data, usable_w), Spacer(1, 2 * mm),
    ]
    if es_pago:
        story += [_tabla_meses(data, usable_w), Spacer(1, 2 * mm),
                  _resumen_pago(data, usable_w)]
    else:
        story.append(_resumen_goce(data, usable_w))
    if data.get("observaciones"):
        story += [Spacer(1, 2 * mm),
                  _p(f"<b>Observaciones:</b> {data['observaciones']}", 8)]
    story += [Spacer(1, 10 * mm), _firmas(data, usable_w)]
    doc.build(story)
    return buf.getvalue()
