"""Piezas compartidas de las páginas de empleados."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.ui import native_select

ETIQUETAS_ESTADO = {"ACT": "Activo", "LIQ": "Liquidado", "SUS": "Suspendido"}

_COLOR_ESTADO = {"ACT": "green", "LIQ": "red", "SUS": "orange"}


def badge_estado(valor: rx.Var, **props) -> rx.Component:
    """Badge de estado del empleado (ACT/LIQ/SUS -> texto legible + semáforo)."""
    return rx.badge(
        rx.match(valor, *[(k, v) for k, v in ETIQUETAS_ESTADO.items()], "Sin estado"),
        color_scheme=rx.match(valor, *[(k, v) for k, v in _COLOR_ESTADO.items()], "gray"),
        variant="soft",
        **props,
    )


def select_estado_lista(value: rx.Var, on_change, **props) -> rx.Component:
    """Selector Activos/Inactivos/Todos de la lista de empleados."""
    return native_select(
        rx.el.option("Activos", value="ACTIVOS"),
        rx.el.option("Inactivos", value="INACTIVOS"),
        rx.el.option("Todos", value="TODOS"),
        value=value, on_change=on_change, size="1",
        **props,
    )
