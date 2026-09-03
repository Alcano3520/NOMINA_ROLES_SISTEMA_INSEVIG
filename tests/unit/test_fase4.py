"""Fase 4: PDF de rol de pago + formateadores de nombre."""

import io

import pypdf
import pytest

from core.datos.port import EmpleadoNomina
from core.pdf.layout import FORMATOS, formatear_nombre_archivo
from core.pdf.rol_pago import OpcionesRol, rol_pago_pdf


def _emp() -> EmpleadoNomina:
    return EmpleadoNomina(
        empleado="1012",
        apellidos_nombres="PEREIRA JUAN",
        cedula="0920116811",
        cargo="GUARDIA",
        depto="OPERACIONES",
        dias=30.0,
        total_ingresos=983.31,
        total_egresos=225.60,
        total_recibir=757.71,
        conceptos={"SUELDO": 800.0, "APORT_IESS": 75.6, "PRESTAMOS_COMPANIA": 150.0},
    )


def test_rol_pago_pdf_parseable_y_con_datos():
    pytest.importorskip("pypdf")
    data = rol_pago_pdf(_emp(), OpcionesRol(fecha_desde="01/06/2026", fecha_hasta="30/06/2026"))
    assert data[:4] == b"%PDF"
    r = pypdf.PdfReader(io.BytesIO(data))
    assert len(r.pages) == 1
    texto = r.pages[0].extract_text()
    assert "SOBRES DE PAGOS" in texto
    assert "0920116811" in texto
    assert "PEREIRA JUAN" in texto
    assert "APORT.IESS" in texto


def test_fondo_reserva_calculado_aparece_como_ingreso_y_descuento():
    # Sin FONDO_RESERVA en BD -> el legado lo calcula 8.33% sobre SUELDO+BONIF+MANIOBRAS+ST
    # y lo muestra como ingreso y como "... EN IESS" en descuentos (neto igual).
    emp = _emp()
    emp.conceptos = {"SUELDO": 800.0, "BONIFICACION": 100.0}
    data = rol_pago_pdf(emp, OpcionesRol())
    texto = pypdf.PdfReader(io.BytesIO(data)).pages[0].extract_text()
    assert "FONDOS DE RESERVA 8.33%" in texto
    assert "EN IESS" in texto  # 900 * 0.0833 = 74.97


def test_dos_por_hoja_dibuja_dos():
    data = rol_pago_pdf(_emp(), OpcionesRol(dos_por_hoja=True))
    r = pypdf.PdfReader(io.BytesIO(data))
    assert r.pages[0].extract_text().count("SOBRES DE PAGOS") == 2


def test_formatos_nombre_archivo():
    kw = dict(empleado="1012", nombre="PEREIRA JUAN", cedula=920116811.0, cargo="GUARDIA", depto="OPS", periodo="2026-06")
    assert formatear_nombre_archivo("cedula-nombre", **kw) == "0920116811-PEREIRA_JUAN_2026-06.pdf"
    assert formatear_nombre_archivo("nombre-cedula", **kw).startswith("PEREIRA_JUAN-0920116811")
    for f in FORMATOS:
        assert formatear_nombre_archivo(f, **kw).endswith("_2026-06.pdf")
