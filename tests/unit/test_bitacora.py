import pytest

from core.repos import bitacora
from core.utils import cedula_valida


def test_limpiar_deja_solo_campos_conocidos_no_vacios():
    d = bitacora._limpiar(
        {"apellidos_nombres": "PEREIRA JUAN", "cedula": "", "banco": "PICHINCHA", "xxx": 1}
    )
    assert d == {"apellidos_nombres": "PEREIRA JUAN", "banco": "PICHINCHA"}


def test_limpiar_normaliza_cedula_y_fecha_y_qap():
    d = bitacora._limpiar(
        {"cedula": "926815564", "fecha_cobro": "05/02/2026", "qap": "1", "horas_suspension": "3,5"}
    )
    assert d["cedula"] == "0926815564"
    assert d["fecha_cobro"] == "2026-02-05"
    assert d["qap"] is True
    assert d["horas_suspension"] == 3.5


def test_estados_validos():
    assert bitacora.ESTADOS == ("PENDIENTE", "AGENDADO", "PAGADO", "CANCELADO")


def test_cambiar_estado_rechaza_invalido():
    with pytest.raises(ValueError, match="Estado inválido"):
        bitacora.cambiar_estado(1, "inexistente", usuario="t", roles=set())


def test_texto_en_sistema_formato_legado():
    txt = bitacora.texto_en_sistema("KRISTEL", "2026-08-18", "RENUNCIA VOLUNTARIA")
    assert "KRISTEL Hoy " in txt
    assert "ACUERDO ENTRE LAS PARTES" in txt
    assert "18-agosto-2026-RENUNCIA VOLUNTARIA" in txt


def test_periodos_recientes_orden_desc():
    p = bitacora.periodos_recientes(3)
    assert len(p) == 3 and p == sorted(p, reverse=True)


def test_cedula_valida_ecuatoriana():
    assert cedula_valida("0926815564")
    assert not cedula_valida("1234567890")
    assert not cedula_valida("092681556")  # 9 dígitos sin cero -> se completa y falla dígito


def test_reporte_agenda_xlsx_valido():
    import io

    import openpyxl

    from core.excel.bitacora_builders import reporte_agenda_xlsx

    data = reporte_agenda_xlsx(
        [{"id": 1, "apellidos_nombres": "PEREIRA JUAN", "cedula": "926815564.0",
          "fecha_salida": "2026-02-01", "estado": "PAGADO", "qap": True,
          "horas_suspension": 4}]
    )
    wb = openpyxl.load_workbook(io.BytesIO(data))
    ws = wb["AGENDA"]
    valores = [c.value for row in ws.iter_rows() for c in row]
    assert "0926815564" in valores
    assert "01-febrero-2026" in valores
    assert "SÍ" in valores
