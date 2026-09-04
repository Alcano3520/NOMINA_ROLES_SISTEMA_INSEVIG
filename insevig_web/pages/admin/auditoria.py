from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, scroll_x
from insevig_web.registry import MODULES
from insevig_web.states.admin_state import AdminState
from insevig_web.states.auth_state import AuthState


@rx.page(
    route="/admin/auditoria",
    title="INSEVIG — Auditoría",
    on_load=[AuthState.cargar_sesion, AdminState.cargar_auditoria],
)
def auditoria() -> rx.Component:
    return pagina(
        page_heading("Auditoría", "Acciones registradas en el sistema (máx. 200)."),
        card(
            rx.hstack(
                rx.input(value=AdminState.aud_usuario, on_change=lambda v: AdminState.set_aud("usuario", v),
                         placeholder="Usuario…", size="2"),
                rx.el.select(
                    rx.el.option("Todos los módulos", value=""),
                    *[rx.el.option(m.titulo, value=m.nombre) for m in MODULES],
                    value=AdminState.aud_modulo,
                    on_change=lambda v: AdminState.set_aud("modulo", v),
                    style={"padding": "6px", "borderRadius": "6px", "border": "1px solid var(--gray-6)",
                           "background": "#fff"},
                ),
                rx.button("Filtrar", on_click=AdminState.cargar_auditoria, size="2"),
                spacing="2", wrap="wrap",
            ),
            width="100%", margin_bottom="0.75rem",
        ),
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        *[
                            rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                            for c in ("Fecha", "Usuario", "Módulo", "Acción", "Objetivo", "Estado")
                        ]
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        AdminState.auditoria,
                        lambda a: rx.table.row(
                            rx.table.cell(a["ts"]),
                            rx.table.cell(a["usuario"]),
                            rx.table.cell(a["modulo"]),
                            rx.table.cell(a["accion"]),
                            rx.table.cell(a["objetivo"]),
                            rx.table.cell(a["status"]),
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
