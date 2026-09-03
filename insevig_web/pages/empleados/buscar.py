from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.data_source_selector import data_source_selector
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.empleados_state import EmpleadosState


@rx.page(route="/empleados/buscar", title="INSEVIG — Empleados", on_load=AuthState.cargar_sesion)
def buscar() -> rx.Component:
    return pagina(
        page_heading("Gestión de empleados", "Busca, edita o crea empleados (RPEMPLEA)."),
        rx.vstack(
            card(
                rx.vstack(
                    rx.hstack(
                        rx.text("Fuente:", weight="bold", size="2"),
                        data_source_selector("empleados"),
                        spacing="2",
                    ),
                    rx.hstack(
                        rx.input(
                            value=EmpleadosState.grid_texto,
                            on_change=EmpleadosState.set_grid_texto,
                            placeholder="Código o nombre…",
                            width="100%",
                        ),
                        rx.button("Buscar", on_click=EmpleadosState.buscar_grid),
                        rx.cond(
                            AuthState.permisos_flat.contains("empleados:crear"),
                            primary_button("Nuevo", on_click=EmpleadosState.nuevo),
                        ),
                        width="100%",
                        spacing="2",
                    ),
                    rx.checkbox(
                        "Solo activos",
                        checked=EmpleadosState.grid_solo_activos,
                        on_change=EmpleadosState.toggle_solo_activos,
                    ),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                EmpleadosState.grid_cargando,
                rx.spinner(),
                scroll_x(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                *[
                                    rx.table.column_header_cell(
                                        c, style={"background": theme.PRIMARY, "color": "white"}
                                    )
                                    for c in ("Código", "Apellidos y nombres", "Cédula", "Cargo", "Estado", "")
                                ]
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                EmpleadosState.grid,
                                lambda e: rx.table.row(
                                    rx.table.cell(e["empleado"]),
                                    rx.table.cell(e["apellidos_nombres"]),
                                    rx.table.cell(e["cedula"]),
                                    rx.table.cell(e["cargo"]),
                                    rx.table.cell(e["estado"]),
                                    rx.table.cell(
                                        rx.button(
                                            "Editar",
                                            on_click=lambda: EmpleadosState.abrir_editor(e["empleado"]),
                                            size="1",
                                            variant="soft",
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
        requiere=("empleados", "ver"),
    )
