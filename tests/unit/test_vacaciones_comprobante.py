"""PDF del comprobante de vacaciones (GOCE / PAGO). Port de
`VACACIONES_SISTEMA_INSEVIG/src/pdf_generator.py`."""

from __future__ import annotations

import io

import pypdf
import pytest

from core.pdf.vacaciones_comprobante import anticipo_pdf, comprobante_pdf

_DATA_PAGO = {
    "tipo": "pagada", "nombre": "PEREZ JUAN", "cedula": "0920116811", "cargo": "GUARDIA",
    "area": "OPERACIONES", "fecha_ingreso": "2020-03-15", "periodo": "2024-2025",
    "fecha_desde": "2024-01-01", "fecha_hasta": "2024-12-31",
    "meses_detalle": [{"mes": m, "anio": 2024, "valor": 480.0} for m in range(1, 13)],
    "subtotal": 5760.0, "valor_15_dias": 240.0, "valor_dia": 16.0, "dias_basicos": 15,
    "dias_adicionales": 1, "dias_gozados": 0, "dias_gozados_periodo": 0, "dias_a_pagar": 16,
    "valor_adicionales": 16.0, "valor_gozados": 0.0, "anticipo": 0.0, "total_pagar": 256.0,
    "forma_pago": "CHEQUE", "banco": "PICHINCHA", "cta_cte_no": "2100", "cheque_no": "00123",
    "fecha_pago": "2025-02-10", "observaciones": "Pago completo",
}


def _txt(data, qr="x"):
    pdf = comprobante_pdf(data, qr)
    assert pdf[:4] == b"%PDF"
    return pypdf.PdfReader(io.BytesIO(pdf)).pages[0].extract_text()


def test_comprobante_pago_es_pdf_con_datos():
    pytest.importorskip("pypdf")
    txt = _txt(_DATA_PAGO, "ID:1035|CED:0920116811|PEREZ JUAN|PER:2024-2025|VAL:256.00")
    assert "LIQUIDACIÓN DE VACACIONES PAGADAS" in txt
    assert "PEREZ JUAN" in txt and "0920116811" in txt
    assert "2024-2025" in txt
    assert "FECHA DE CORTE" in txt and "VALORES GANADOS" in txt
    assert "31 de enero de 2024" in txt          # _fmt_fecha_mes
    assert "TOTAL NETO A RECIBIR POR VACACIONES" in txt
    assert "PICHINCHA" in txt and "00123" in txt


def test_comprobante_pago_filas_condicionales():
    # sin días adicionales / gozo / anticipo -> esas filas no salen
    d = dict(_DATA_PAGO, dias_adicionales=0, valor_adicionales=0.0)
    txt = _txt(d)
    assert "DÍAS ADICIONALES (Art. 69)" not in txt
    # con gozo y anticipo -> sí salen
    d2 = dict(_DATA_PAGO, dias_gozados=5, valor_gozados=80.0, anticipo=50.0)
    txt2 = _txt(d2)
    assert "TOMÓ 5 DÍAS COMO GOZO DE VACACIONES" in txt2
    assert "Anticipo de Vacaciones" in txt2


def test_comprobante_goce_usa_otro_titulo_y_bloque_legal():
    data_goce = dict(_DATA_PAGO, tipo="gozada", dias_goce=16, dias_gozados_periodo=1, dias_pendientes=1)
    txt = _txt(data_goce)
    assert "GOCE DE VACACIONES" in txt
    assert "LIQUIDACIÓN DE VACACIONES PAGADAS" not in txt
    assert "APELLIDOS Y NOMBRES" in txt
    assert "Art. 69" in txt and "Codigo de Trabajo" in txt
    assert "ESTOY CONFORME CON LOS DIAS QUE HE TOMADO" in txt


def test_comprobante_firma_empleador_rrhh_empleado():
    txt_pago = _txt(_DATA_PAGO)
    assert "EMPLEADOR" in txt_pago and "T. HUMANO" in txt_pago
    assert "MSC. OMAR CAMPOVERDE" in txt_pago and "Firma Conforme" in txt_pago
    txt_goce = _txt(dict(_DATA_PAGO, tipo="gozada"))
    assert "RECURSOS HUMANOS" in txt_goce


def test_comprobante_sin_meses_usa_subtotal():
    d = dict(_DATA_PAGO, meses_detalle=[])
    txt = _txt(d)
    assert "5,760.00" in txt  # cae a data['subtotal']


def test_anticipo_pdf_es_recibo_simple():
    data = {"nombre": "PEREZ JUAN", "cedula": "0920116811", "cargo": "GUARDIA",
            "periodo": "2024-2025", "valor": 120.0, "en_letras": "CIENTO VEINTE CON 00/100",
            "fecha": "2025-01-10", "referencia": "ANT-001"}
    pdf = anticipo_pdf(data)
    txt = pypdf.PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    assert "COMPROBANTE DE ANTICIPO DE VACACIONES" in txt
    assert "ANTICIPO A CUENTA DE VACACIONES" in txt
    assert "$120.00" in txt and "CIENTO VEINTE" in txt
