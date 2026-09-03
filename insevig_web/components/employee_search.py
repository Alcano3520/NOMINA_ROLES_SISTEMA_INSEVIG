"""Buscador de empleado reutilizable: input + botón + lista de resultados.

Cada módulo pasa sus propios Vars/handlers (su state tiene `texto_busqueda`,
`resultados` [list[dict con empleado/apellidos_nombres/cedula]], y handlers
`set_texto`, `buscar`, `seleccionar(empleado, nombre)`).
"""

from __future__ import annotations

import reflex as rx

from insevig_web.components.ui import card


def employee_search(
    *,
    texto: rx.Var,
    resultados: rx.Var,
    on_set_texto: rx.EventHandler,
    on_buscar: rx.EventHandler,
    on_seleccionar,
) -> rx.Component:
    return card(
        rx.vstack(
            rx.hstack(
                rx.input(
                    value=texto,
                    on_change=on_set_texto,
                    placeholder="Código, cédula o nombre…",
                    width="100%",
                ),
                rx.button("Buscar", on_click=on_buscar),
                width="100%",
                spacing="2",
            ),
            rx.cond(
                resultados.length() > 0,
                rx.vstack(
                    rx.foreach(
                        resultados,
                        lambda e: rx.button(
                            rx.hstack(
                                rx.text(e["empleado"], weight="bold", size="1"),
                                rx.text(e["apellidos_nombres"], size="1"),
                                rx.text(e["cedula"], color_scheme="gray", size="1"),
                                spacing="3",
                                wrap="wrap",
                            ),
                            on_click=lambda: on_seleccionar(e["empleado"], e["apellidos_nombres"]),
                            variant="soft",
                            width="100%",
                            justify="start",
                        ),
                    ),
                    spacing="1",
                    width="100%",
                    max_height="240px",
                    overflow_y="auto",
                ),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
