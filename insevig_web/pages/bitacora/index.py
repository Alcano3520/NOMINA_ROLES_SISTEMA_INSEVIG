from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.bitacora_state import CAMPOS, ESTADOS, BitacoraState

_COLS = ["apellidos_nombres", "cedula", "fecha_salida", "fecha_cobro", "hora", "estado", "periodo"]


def _form() -> rx.Component:
    return card(
        rx.vstack(
            rx.heading(rx.cond(BitacoraState.editando_id > 0, "Editar registro", "Nuevo registro"), size="3"),
            rx.grid(
                *[
                    rx.cond(
                        c == "estado",
                        rx.vstack(
                            rx.text("estado", size="1", weight="bold"),
                            rx.select(ESTADOS, value=BitacoraState.form["estado"],
                                      on_change=lambda v: BitacoraState.set_campo("estado", v)),
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text(c, size="1", weight="bold"),
                            rx.input(value=BitacoraState.form[c],
                                     on_change=lambda v, c=c: BitacoraState.set_campo(c, v), size="2"),
                            spacing="1",
                        ),
                    )
                    for c in CAMPOS
                ],
                columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                spacing="3",
                width="100%",
            ),
            rx.hstack(
                primary_button("Guardar", on_click=BitacoraState.guardar),
                rx.button("Cancelar", on_click=BitacoraState.cerrar_form, variant="soft"),
                spacing="2",
            ),
            rx.cond(BitacoraState.msg != "", rx.callout(BitacoraState.msg, size="1")),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


@rx.page(
    route="/bitacora",
    title="INSEVIG — Agenda de liquidaciones",
    on_load=[AuthState.cargar_sesion, BitacoraState.cargar],
)
def index() -> rx.Component:
    return pagina(
        page_heading(
            "Agenda de cobro de liquidación de haberes",
            "Programación de cuándo los empleados salientes cobran su liquidación.",
        ),
        rx.vstack(
            card(
                rx.hstack(
                    rx.select(["(todos)", *ESTADOS], default_value="(todos)", on_change=BitacoraState.set_filtro_estado),
                    rx.input(value=BitacoraState.filtro_texto, on_change=BitacoraState.set_filtro_texto,
                             placeholder="nombre o cédula…", width="220px"),
                    rx.button("Buscar", on_click=BitacoraState.cargar),
                    rx.cond(
                        AuthState.permisos_flat.contains("bitacora:crear"),
                        primary_button("Nuevo", on_click=BitacoraState.nuevo),
                    ),
                    spacing="2",
                    wrap="wrap",
                ),
                width="100%",
            ),
            rx.cond(BitacoraState.error != "", rx.callout(BitacoraState.error, color_scheme="red", size="1")),
            rx.cond(BitacoraState.mostrar_form, _form()),
            rx.cond(
                BitacoraState.cargando,
                rx.spinner(),
                scroll_x(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                *[
                                    rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                                    for c in [*_COLS, ""]
                                ]
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                BitacoraState.registros,
                                lambda r: rx.table.row(
                                    *[rx.table.cell(r[c].to_string()) for c in _COLS],
                                    rx.table.cell(
                                        rx.hstack(
                                            rx.button("Editar", on_click=lambda: BitacoraState.editar(r), size="1", variant="soft"),
                                            rx.cond(
                                                AuthState.permisos_flat.contains("bitacora:editar"),
                                                rx.button("Cobrado", on_click=lambda: BitacoraState.cambiar_estado(r["id"], "cobrado"), size="1", color_scheme="green"),
                                            ),
                                            spacing="1",
                                        )
                                    ),
                                ),
                            )
                        ),
                        variant="surface",
                        size="1",
                        width="100%",
                    )
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("bitacora", "ver"),
    )
