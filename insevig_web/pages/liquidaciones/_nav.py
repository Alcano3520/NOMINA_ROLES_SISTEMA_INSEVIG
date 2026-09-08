"""Sub-navegación del módulo Liquidaciones — las 4 pantallas del sidebar del
`.pyw` (Generar / Editor / Gestión / Descuentos). El sidebar global solo
muestra un enlace por módulo, así que estas 4 se navegan desde acá."""

from __future__ import annotations

import reflex as rx

_PANTALLAS = [
    ("Generar finiquitos", "/liquidaciones"),
    ("Editor de liquidaciones", "/liquidaciones/editor"),
    ("Gestión de liquidaciones", "/liquidaciones/guardadas"),
    ("Descuentos pendientes", "/liquidaciones/descuentos-pendientes"),
]


def subnav(activa: str) -> rx.Component:
    """`activa` = la ruta de la pantalla actual (para resaltarla)."""
    return rx.hstack(
        *[
            rx.link(
                rx.button(
                    etq,
                    variant=("solid" if ruta == activa else "soft"),
                    size="2",
                    color_scheme=("blue" if ruta == activa else "gray"),
                ),
                href=ruta,
            )
            for etq, ruta in _PANTALLAS
        ],
        spacing="2",
        wrap="wrap",
        margin_bottom="0.5rem",
    )
