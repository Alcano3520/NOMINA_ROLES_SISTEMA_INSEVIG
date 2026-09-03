"""Documentos del empleado en PDF: hoja de vida, certificado de trabajo,
contrato y carta de renuncia. Se rellenan con los datos de la ficha.

El texto legal es una plantilla base de INSEVIG; RRHH puede ajustarla luego.
"""

from __future__ import annotations

import datetime as dt
import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.repos.empleados import ETIQUETAS, GRUPOS

_EMPRESA = "INSEVIG CIA. LTDA."
_RUC = "0992339411001"


def _doc(buf: io.BytesIO) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm, topMargin=22 * mm, bottomMargin=22 * mm,
    )


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("Cuerpo", parent=s["Normal"], fontSize=10.5, leading=16, alignment=TA_JUSTIFY, spaceAfter=10))
    s.add(ParagraphStyle("Firma", parent=s["Normal"], fontSize=10, alignment=1, spaceBefore=30))
    return s


def _nombre(c: dict) -> str:
    return f"{c.get('NOMBRES', '')} {c.get('APELLIDOS', '')}".strip()


def _hoy_largo() -> str:
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    d = dt.date.today()
    return f"{d.day} de {meses[d.month - 1]} de {d.year}"


# ── Hoja de vida ─────────────────────────────────────────────────────────────

def hoja_vida_pdf(codigo: str, campos: dict) -> bytes:
    buf = io.BytesIO()
    s = _styles()
    elems = [
        Paragraph("HOJA DE VIDA", s["Title"]),
        Paragraph(f"{_nombre(campos)} &nbsp;·&nbsp; C.I. {campos.get('CEDULA', '')}", s["Normal"]),
        Spacer(1, 6 * mm),
    ]
    for grupo, claves in GRUPOS.items():
        filas = [[ETIQUETAS.get(k, k.replace('_', ' ').capitalize()), str(campos.get(k, "") or "")] for k in claves]
        filas = [f for f in filas if f[1]]
        if not filas:
            continue
        elems.append(Paragraph(grupo, s["Heading3"]))
        t = Table(filas, colWidths=[55 * mm, 105 * mm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1a4d8f")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 4 * mm))
    _doc(buf).build(elems)
    return buf.getvalue()


# ── Certificado de trabajo ───────────────────────────────────────────────────

def certificado_trabajo_pdf(campos: dict, *, ciudad: str = "Guayaquil", incluir_sueldo: bool = True) -> bytes:
    buf = io.BytesIO()
    s = _styles()
    activo = str(campos.get("ESTADO", "")).upper().startswith("ACT") and not campos.get("FECHA_SAL")
    verbo = "presta" if activo else "prestó"
    cargo = campos.get("CARGO", "")
    ing = campos.get("FECHA_ING", "")
    sal = campos.get("FECHA_SAL", "")
    periodo = f"desde el {ing}" + ("" if activo else f" hasta el {sal}")
    sueldo_txt = ""
    if incluir_sueldo and campos.get("SUELDO"):
        sueldo_txt = f" percibiendo una remuneración mensual de USD {campos.get('SUELDO')}"
    cuerpo = (
        f"{_EMPRESA}, con RUC {_RUC}, a través del Departamento de Recursos Humanos, "
        f"<b>CERTIFICA</b> que el/la señor(a) <b>{_nombre(campos)}</b>, portador(a) de la "
        f"cédula de ciudadanía No. {campos.get('CEDULA', '')}, {verbo} sus servicios "
        f"lícitos y personales para esta compañía en el cargo de <b>{cargo}</b>, {periodo}"
        f"{sueldo_txt}."
    )
    cierre = (
        "Durante el tiempo de trabajo ha demostrado responsabilidad, honestidad y "
        "buen desempeño en las funciones asignadas."
        if activo else
        "Durante el tiempo de trabajo demostró responsabilidad y buen desempeño en las "
        "funciones asignadas."
    )
    elems = [
        Paragraph("CERTIFICADO DE TRABAJO", s["Title"]),
        Spacer(1, 8 * mm),
        Paragraph(cuerpo, s["Cuerpo"]),
        Paragraph(cierre, s["Cuerpo"]),
        Paragraph(
            f"Se expide el presente certificado a solicitud del interesado, en {ciudad}, "
            f"a {_hoy_largo()}.",
            s["Cuerpo"],
        ),
        Spacer(1, 24 * mm),
        Paragraph("_______________________________<br/>Recursos Humanos<br/>" + _EMPRESA, s["Firma"]),
    ]
    _doc(buf).build(elems)
    return buf.getvalue()


# ── Contrato de trabajo ──────────────────────────────────────────────────────

def contrato_pdf(campos: dict, *, tipo: str = "INDEFINIDO", ciudad: str = "Guayaquil",
                 jornada: str = "completa") -> bytes:
    buf = io.BytesIO()
    s = _styles()
    tipos = {
        "INDEFINIDO": "a plazo indefinido",
        "EVENTUAL": "eventual",
        "PRUEBA": "con período de prueba de noventa (90) días",
    }
    clausulas = [
        ("PRIMERA — Comparecientes",
         f"Comparecen a la celebración del presente contrato, por una parte {_EMPRESA}, "
         f"RUC {_RUC}, a quien en adelante se denominará EL EMPLEADOR; y por otra parte "
         f"el/la señor(a) {_nombre(campos)}, con cédula No. {campos.get('CEDULA', '')}, "
         f"domiciliado(a) en {campos.get('DIRECCION', '')}, a quien se denominará EL TRABAJADOR."),
        ("SEGUNDA — Objeto",
         f"EL TRABAJADOR se obliga a prestar sus servicios lícitos y personales en el cargo "
         f"de {campos.get('CARGO', '')}, en el departamento de {campos.get('DEPTO', '')}, "
         f"bajo la dependencia y subordinación de EL EMPLEADOR."),
        ("TERCERA — Jornada",
         f"La jornada de trabajo será {jornada}, conforme a los horarios que establezca "
         f"EL EMPLEADOR dentro de los límites legales."),
        ("CUARTA — Remuneración",
         f"EL EMPLEADOR pagará a EL TRABAJADOR una remuneración mensual de "
         f"USD {campos.get('SUELDO', '____')}, más los beneficios de ley."),
        ("QUINTA — Plazo",
         f"El presente contrato es {tipos.get(tipo, 'a plazo indefinido')}, con fecha de "
         f"inicio {campos.get('FECHA_ING', '____')}."),
        ("SEXTA — Legislación aplicable",
         "En todo lo no previsto en este contrato, las partes se sujetan al Código del "
         "Trabajo y demás normas vigentes en la República del Ecuador."),
    ]
    elems = [Paragraph("CONTRATO INDIVIDUAL DE TRABAJO", s["Title"]), Spacer(1, 8 * mm)]
    for tit, txt in clausulas:
        elems.append(Paragraph(f"<b>{tit}.</b> {txt}", s["Cuerpo"]))
    elems.append(Paragraph(
        f"Para constancia, las partes firman en {ciudad}, a {_hoy_largo()}, en dos ejemplares "
        f"de igual tenor y valor.", s["Cuerpo"]))
    elems.append(Spacer(1, 22 * mm))
    firmas = Table(
        [["_________________________", "_________________________"],
         ["EL EMPLEADOR", "EL TRABAJADOR"],
         [_EMPRESA, f"C.I. {campos.get('CEDULA', '')}"]],
        colWidths=[80 * mm, 80 * mm],
    )
    firmas.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    elems.append(firmas)
    _doc(buf).build(elems)
    return buf.getvalue()


# ── Carta de renuncia ────────────────────────────────────────────────────────

def carta_renuncia_pdf(campos: dict, *, ciudad: str = "Guayaquil", fecha_efectiva: str = "",
                       motivo: str = "") -> bytes:
    buf = io.BytesIO()
    s = _styles()
    efectiva = fecha_efectiva or _hoy_largo()
    motivo_txt = f" El motivo de mi decisión es {motivo}." if motivo else ""
    cuerpo = (
        f"Por medio de la presente, yo, {_nombre(campos)}, con cédula de ciudadanía "
        f"No. {campos.get('CEDULA', '')}, quien me desempeño en el cargo de "
        f"{campos.get('CARGO', '')}, comunico a ustedes mi decisión de dar por terminada "
        f"de manera voluntaria y unilateral la relación laboral que mantengo con "
        f"{_EMPRESA}, con fecha efectiva {efectiva}.{motivo_txt}"
    )
    elems = [
        Paragraph(f"{ciudad}, {_hoy_largo()}", s["Normal"]),
        Spacer(1, 8 * mm),
        Paragraph("Señores<br/>" + _EMPRESA + "<br/>Departamento de Recursos Humanos<br/>Presente.-", s["Normal"]),
        Spacer(1, 8 * mm),
        Paragraph("De mis consideraciones:", s["Cuerpo"]),
        Paragraph(cuerpo, s["Cuerpo"]),
        Paragraph(
            "Agradezco la oportunidad y la experiencia adquirida durante mi permanencia en "
            "la compañía, y quedo a disposición para la entrega-recepción de mis funciones.",
            s["Cuerpo"],
        ),
        Paragraph("Atentamente,", s["Cuerpo"]),
        Spacer(1, 22 * mm),
        Paragraph(
            "_______________________________<br/>"
            f"{_nombre(campos)}<br/>C.I. {campos.get('CEDULA', '')}",
            s["Firma"],
        ),
    ]
    _doc(buf).build(elems)
    return buf.getvalue()


DOCUMENTOS = {
    "hoja_vida": ("Hoja de vida", lambda c, campos: hoja_vida_pdf(c, campos)),
    "certificado": ("Certificado de trabajo", lambda c, campos: certificado_trabajo_pdf(campos)),
    "contrato": ("Contrato de trabajo", lambda c, campos: contrato_pdf(campos)),
    "renuncia": ("Carta de renuncia", lambda c, campos: carta_renuncia_pdf(campos)),
}
