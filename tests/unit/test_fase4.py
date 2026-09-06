"""Fase 4: PDF de rol de pago + formateadores de nombre."""

import io
from pathlib import Path

import pypdf
import pytest

from core.datos.port import EmpleadoNomina
from core.pdf.layout import FORMATOS, formatear_nombre_archivo
from core.pdf.rol_pago import OpcionesRol, rol_pago_pdf

_GOLDEN_PDF = Path(__file__).resolve().parents[2] / "docs" / "pereira_test.pdf"


def _lineas_norm(texto: str) -> list[str]:
    """Líneas sin espacios de más ni vacías, para comparar dos PDF."""
    return [" ".join(ln.split()) for ln in texto.splitlines() if ln.strip()]


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


def _emp_pereira() -> EmpleadoNomina:
    """Empleado 1012 del rol real `docs/pereira_test.pdf` (período 2026-06)."""
    return EmpleadoNomina(
        empleado="1012",
        apellidos_nombres="PEREIRA CAMPOVERDE CARLOS DANIEL",
        cedula="0704948983",
        cargo="COORDINADOR",
        depto="URBANIZACION RIVERA PLAYAS",
        dias=30.0,
        total_ingresos=1246.50,
        total_egresos=960.39,
        total_recibir=286.11,
        conceptos={
            "SUELDO": 491.35,
            "SOBRETIEMPO_50": 384.68,  # HORAS EXTRAS
            "FONDO_RESERVA": 86.13,    # viene de BD -> solo ingreso, sin "EN IESS"
            "DECIMO_TERCERA": 86.17,
            "DECIMO_CUARTA": 40.17,
            "BONIFICACION": 158.00,
            "APORT_IESS": 97.72,
            "PRESTAMOS_QUIROGRAFARIOS": 112.67,
            "PRESTAMOS_COMPANIA": 100.00,
            "ANTICIPO_SUELDO": 350.00,
            "ANTICIPOS_SURTIDOS": 300.00,
        },
    )


def test_rol_pago_golden_pereira_coincide_con_el_pdf_del_legado():
    """Regresión: el texto extraído del rol generado == el del PDF real del legado."""
    data = rol_pago_pdf(
        _emp_pereira(), OpcionesRol(fecha_desde="2026-06-01", fecha_hasta="2026-06-30")
    )
    generado = _lineas_norm(pypdf.PdfReader(io.BytesIO(data)).pages[0].extract_text())
    esperado = _lineas_norm(pypdf.PdfReader(str(_GOLDEN_PDF)).pages[0].extract_text())
    assert generado == esperado


def test_rol_pago_golden_totales_y_orden():
    data = rol_pago_pdf(_emp_pereira(), OpcionesRol())
    texto = pypdf.PdfReader(io.BytesIO(data)).pages[0].extract_text()
    # Orden de conceptos tal como en el legado
    orden = [
        "SUELDO", "HORAS EXTRAS", "FONDOS DE RESERVA 8.33%", "DECIMO TERCER SUELDO",
        "DECIMO CUARTO SUELDO", "BONIFICACION", "APORT.IESS", "PRESTAMOS QUIROGRAFARIOS",
        "PRESTAMOS COMPAÑIA", "ANTICIPO DE SUELDO", "ANTICIPOS SURTIDOS",
    ]
    posiciones = [texto.index(x) for x in orden]
    assert posiciones == sorted(posiciones)
    assert "EN IESS" not in texto  # el fondo venía de BD
    for total in ("1246.50", "960.39", "286.11"):
        assert total in texto


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
