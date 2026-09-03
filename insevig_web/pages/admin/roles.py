from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import page_heading, scroll_x
from insevig_web.states.admin_state import AdminState
from insevig_web.states.auth_state import AuthState


@rx.page(route="/admin/roles", title="INSEVIG — Roles y permisos", on_load=AuthState.cargar_sesion)
def roles() -> rx.Component:
    return pagina(
        page_heading("Roles y permisos", "Matriz por rol × módulo. Editable en una fase posterior."),
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        *[
                            rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                            for c in ("Rol", "Módulo", "Acciones permitidas")
                        ]
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        AdminState.matriz_permisos,
                        lambda p: rx.table.row(
                            rx.table.cell(p["rol"]),
                            rx.table.cell(p["modulo"]),
                            rx.table.cell(p["acciones"]),
                        ),
                    )
                ),
                variant="surface",
                size="1",
                width="100%",
            )
        ),
        requiere=("admin", "ver"),
    )
