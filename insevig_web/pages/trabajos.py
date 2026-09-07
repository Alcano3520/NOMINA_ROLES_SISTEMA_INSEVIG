from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import page_heading, scroll_x
from insevig_web.states.admin_state import AdminState
from insevig_web.states.auth_state import AuthState

_S = AdminState


def _color_estado(estado) -> rx.Var:
    return rx.match(
        estado,
        ("ok", "green"),
        ("error", "red"),
        ("corriendo", "blue"),
        ("pendiente", "amber"),
        "gray",
    )


@rx.page(
    route="/trabajos",
    title="INSEVIG — Trabajos y descargas",
    on_load=[AuthState.cargar_sesion, AdminState.cargar_trabajos],
)
def trabajos() -> rx.Component:
    return pagina(
        page_heading(
            "Trabajos y descargas",
            "Exports, lotes y cargas masivas recientes. Un admin ve los de todos; el resto, los suyos.",
        ),
        rx.hstack(
            rx.button(rx.icon("refresh-cw", size=15), "Actualizar",
                      on_click=AdminState.cargar_trabajos, size="2", variant="soft"),
            margin_bottom="0.5rem",
        ),
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        *[
                            rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                            for c in ("Fecha", "Tipo", "Estado", "Avance", "Mensaje", "Usuario", "")
                        ]
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        _S.trabajos,
                        lambda t: rx.table.row(
                            rx.table.cell(t["creado"]),
                            rx.table.cell(t["tipo"]),
                            rx.table.cell(
                                rx.badge(t["estado"], color_scheme=_color_estado(t["estado"]))
                            ),
                            rx.table.cell(t["avance"]),
                            rx.table.cell(rx.text(t["mensaje"], size="1")),
                            rx.table.cell(t["creado_por"]),
                            rx.table.cell(
                                rx.cond(
                                    t["archivo"] != "",
                                    rx.button(
                                        rx.icon("download", size=14),
                                        on_click=lambda: _S.descargar_trabajo(t["id"]),
                                        size="1",
                                        variant="soft",
                                    ),
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
        rx.cond(_S.trabajos.length() == 0, rx.text("Sin trabajos recientes.", size="2", color_scheme="gray")),
    )
