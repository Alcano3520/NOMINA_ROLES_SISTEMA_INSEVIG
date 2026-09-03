from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.empleados_state import GRUPOS, EmpleadosState


def _campo(nombre: str) -> rx.Component:
    return rx.vstack(
        rx.text(nombre, size="1", weight="bold"),
        rx.input(
            value=EmpleadosState.edit_campos[nombre],
            on_change=lambda v: EmpleadosState.set_campo(nombre, v),
            size="2",
            width="100%",
        ),
        spacing="1",
        width="100%",
    )


def _grupo(titulo: str, campos: list[str]) -> rx.Component:
    return card(
        rx.vstack(
            rx.heading(titulo, size="3"),
            rx.grid(
                *[_campo(c) for c in campos],
                columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                spacing="3",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


@rx.page(route="/empleados/editar", title="INSEVIG — Editar empleado", on_load=AuthState.cargar_sesion)
def editar() -> rx.Component:
    return pagina(
        page_heading(
            rx.cond(EmpleadosState.es_nuevo, "Nuevo empleado", "Editar empleado " + EmpleadosState.edit_empleado),
            "Los cambios se escriben en SQL Server con auditoría.",
        ),
        rx.vstack(
            rx.cond(EmpleadosState.edit_error != "", rx.callout(EmpleadosState.edit_error, color_scheme="red", size="1")),
            rx.cond(EmpleadosState.edit_ok != "", rx.callout(EmpleadosState.edit_ok, color_scheme="green", size="1")),
            rx.cond(
                EmpleadosState.es_nuevo,
                card(
                    rx.vstack(
                        rx.text("Código de empleado (EMPLEADO)", size="1", weight="bold"),
                        rx.input(
                            value=EmpleadosState.edit_campos["EMPLEADO"],
                            on_change=lambda v: EmpleadosState.set_campo("EMPLEADO", v),
                            width="200px",
                        ),
                        spacing="1",
                    ),
                    width="100%",
                ),
            ),
            *[_grupo(g, cs) for g, cs in GRUPOS.items()],
            rx.hstack(
                primary_button("Guardar", on_click=EmpleadosState.guardar),
                rx.link(rx.button("Volver", variant="soft"), href="/empleados/buscar"),
                spacing="3",
            ),
            rx.cond(
                ~EmpleadosState.es_nuevo & AuthState.permisos_flat.contains("empleados:eliminar"),
                card(
                    rx.vstack(
                        rx.heading("Eliminar empleado", size="3", color_scheme="red"),
                        rx.text(
                            "Escribe el código exacto (" + EmpleadosState.edit_empleado + ") para confirmar.",
                            size="1",
                        ),
                        rx.hstack(
                            rx.input(
                                value=EmpleadosState.confirmar_borrado,
                                on_change=EmpleadosState.set_confirmar_borrado,
                                width="160px",
                            ),
                            rx.button("Eliminar", on_click=EmpleadosState.eliminar, color_scheme="red"),
                            spacing="2",
                        ),
                        spacing="2",
                    ),
                    width="100%",
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("empleados", "ver"),
    )
