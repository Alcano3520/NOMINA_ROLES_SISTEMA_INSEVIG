"""Filtro por categoría de tipo_sancion (bandeja/historial), pedido del
usuario 2026-09-12 replicando F&P/H&F/RST del sidebar de `main.py`."""

from __future__ import annotations

from insevig_web.states.sanciones_state import CATEGORIA_OPCIONES, _en_categoria


def test_categoria_opciones_incluye_todos_y_las_tres_del_original():
    assert CATEGORIA_OPCIONES[0] == "TODOS"
    assert set(CATEGORIA_OPCIONES[1:]) == {"Faltas y Permisos", "Horas y Franco", "Resto"}


def test_en_categoria_todos_no_filtra():
    assert _en_categoria({"tipo_sancion": "ATRASO"}, "TODOS") is True


def test_en_categoria_faltas_y_permisos():
    assert _en_categoria({"tipo_sancion": "FALTA"}, "Faltas y Permisos") is True
    assert _en_categoria({"tipo_sancion": "PERMISO"}, "Faltas y Permisos") is True
    assert _en_categoria({"tipo_sancion": "ATRASO"}, "Faltas y Permisos") is False


def test_en_categoria_resto():
    assert _en_categoria({"tipo_sancion": "DORMIDO"}, "Resto") is True
    assert _en_categoria({"tipo_sancion": "FALTA"}, "Resto") is False


def test_en_categoria_sin_tipo_sancion():
    assert _en_categoria({}, "Resto") is False


def test_en_categoria_tipo_individual():
    """Pedido 2026-09-14: poder filtrar/aprobar SOLO un tipo puntual (ej.
    solo FALTA, sin PERMISO) -- antes FALTA y PERMISO solo se filtraban
    juntos como el grupo "Faltas y Permisos"."""
    assert _en_categoria({"tipo_sancion": "FALTA"}, "FALTA") is True
    assert _en_categoria({"tipo_sancion": "PERMISO"}, "FALTA") is False
    assert _en_categoria({"tipo_sancion": "PERMISO"}, "PERMISO") is True
