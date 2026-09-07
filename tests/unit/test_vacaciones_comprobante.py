"""PDF del comprobante de vacaciones (GOCE / PAGO)."""

from __future__ import annotations

import io

import pypdf
import pytest

from core.pdf.vacaciones_comprobante import comprobante_pdf

_DATA_PAGO = {
    "tipo": "pagada", "nombre": "PEREZ JUAN", "cedula": "0920116811", "cargo": "GUARDIA",
    "area": "OPERACIONES", "fecha_ingreso": "2020-03-15", "periodo": "2024-2025",
    "fecha_desde": "2024-01-01", "fecha_hasta": "2024-12-31",
    "meses_detalle": [{"mes": m, "anio": 2024, "valor": 480.0} for m in range(1, 13)],
    "subtotal": 5760.0, "valor_15_dias": 240.0, "valor_dia": 16.0, "dias_basicos": 15,
    "dias_adicionales": 1, "dias_gozados_periodo": 0, "dias_a_pagar": 16,
    "valor_adicionales": 16.0, "anticipo": 0.0, "total_pagar": 256.0,
    "forma_pago": "CHEQUE", "banco": "PICHINCHA", "cta_cte_no": "2100", "cheque_no": "00123",
    "fecha_pago": "2025-02-10", "observaciones": "Pago completo",
}


def test_comprobante_pago_es_pdf_con_datos():
    pytest.importorskip("pypdf")
    data = comprobante_pdf(_DATA_PAGO, "ID:1035|CED:0920116811|PEREZ JUAN|PER:2024-2025|VAL:256.00")
    assert data[:4] == b"%PDF"
    txt = pypdf.PdfReader(io.BytesIO(data)).pages[0].extract_text()
    assert "LIQUIDACIÓN DE VACACIONES PAGADAS" in txt
    assert "PEREZ JUAN" in txt and "0920116811" in txt
    assert "2024-2025" in txt
    assert "TOTAL A PAGAR" in txt
    assert "PICHINCHA" in txt and "00123" in txt


def test_comprobante_goce_usa_otro_titulo_y_resumen():
    data_goce = dict(_DATA_PAGO, tipo="gozada", dias_goce=16, dias_este_goce=15, dias_pendientes=1)
    txt = pypdf.PdfReader(io.BytesIO(comprobante_pdf(data_goce, "x"))).pages[0].extract_text()
    assert "GOCE DE VACACIONES" in txt
    assert "LIQUIDACIÓN DE VACACIONES PAGADAS" not in txt
    assert "Días pendientes de goce" in txt


def test_comprobante_sin_meses_usa_subtotal():
    d = dict(_DATA_PAGO, meses_detalle=[])
    data = comprobante_pdf(d, "x")
    assert data[:4] == b"%PDF"


def test_comprobante_firma_incluye_empleado_y_empleador():
    txt = pypdf.PdfReader(io.BytesIO(comprobante_pdf(_DATA_PAGO, "x"))).pages[0].extract_text()
    assert "EMPLEADOR" in txt and "EMPLEADO" in txt and "TALENTO HUMANO" in txt
    assert "OMAR CAMPOVERDE" in txt
