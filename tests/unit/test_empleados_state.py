"""`_limpiar_valor` del estado de empleados (limpieza de valores para la ficha)."""

from __future__ import annotations

from insevig_web.states.empleados_state import _limpiar_valor


def test_cedula_normaliza_float_a_10_digitos():
    assert _limpiar_valor("CEDULA", 920116811.0) == "0920116811"


def test_cedula_vacia():
    assert _limpiar_valor("CEDULA", None) == ""


def test_fecha_supabase_formato_t_medianoche():
    assert _limpiar_valor("FECHA_ING", "2019-04-24T00:00:00") == "2019-04-24"


def test_fecha_sqlserver_formato_espacio():
    """BUG REAL corregido 2026-09-12: pyodbc devuelve un `datetime`, que al
    convertir a texto queda con espacio en vez de 'T' -- el NAS (SQL Server
    como fuente por defecto) mostraba fecha de ingreso/nacimiento con hora."""
    assert _limpiar_valor("FECHA_NAC", "1985-09-11 00:00:00") == "1985-09-11"


def test_fecha_con_hora_no_medianoche_tambien_se_corta():
    """Ninguna fecha de RPEMPLEA usa la hora -- se corta siempre, no solo si
    es exactamente medianoche."""
    assert _limpiar_valor("FECHA_SAL", "2026-06-30 08:15:42") == "2026-06-30"


def test_valor_numerico_sin_decimal_sobrante():
    assert _limpiar_valor("SUELDO", "487.3") == "487.3"
    assert _limpiar_valor("CARGAS", "2.0") == "2"


def test_valor_sin_fecha_pasa_intacto():
    assert _limpiar_valor("NOMBRES", "JUAN CARLOS") == "JUAN CARLOS"
