"""Helpers de scripts/validar_datos (comparación SQL Server vs Supabase)."""

from __future__ import annotations

from scripts.validar_datos import _difs_dict


def test_difs_dict_tolera_redondeo_y_detecta_montos():
    a = {"SUELDO": 800.00, "NOMBRE": "ANA", "IESS": 75.60}
    b = {"SUELDO": 800.01, "NOMBRE": "ANA", "IESS": 70.00}
    difs = _difs_dict(a, b)
    assert len(difs) == 1 and difs[0].startswith("IESS:")


def test_difs_dict_detecta_texto_y_claves_faltantes():
    a = {"CARGO": "GUARDIA", "DEPTO": "OPS"}
    b = {"CARGO": "COORDINADOR"}
    difs = _difs_dict(a, b)
    assert any(d.startswith("CARGO:") for d in difs)
    assert any(d.startswith("DEPTO:") for d in difs)


def test_difs_dict_iguales_no_reporta():
    a = {"SUELDO": 800.0, "X": None, "Y": ""}
    assert _difs_dict(a, dict(a)) == []
