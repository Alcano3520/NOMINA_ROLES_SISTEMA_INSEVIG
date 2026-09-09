from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.roles_pdf_state import RolesState

_S = RolesState


def _campo(label: str, control: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", weight="bold", color_scheme="gray"),
        control, spacing="1", width="100%",
    )


@rx.page(
    route="/roles/generar",
    title="INSEVIG — Rol de pago",
    on_load=[AuthState.cargar_sesion, RolesState.on_load],
)
def generar() -> rx.Component:
    return pagina(
        page_heading("Rol de pago individual", "Genera el PDF de un empleado para un período."),
        rx.vstack(
            card(
                rx.vstack(
                    rx.grid(
                        _campo("Empleado", rx.input(
                            value=_S.identificador, on_change=_S.set_identificador,
                            placeholder="Código, cédula o nombre", size="2", width="100%",
                        )),
                        _campo("Período", rx.input(
                            value=_S.periodo, on_change=_S.set_periodo,
                            placeholder="2026-06", size="2", width="100%",
                        )),
                        columns=rx.breakpoints(initial="1", sm="2"),
                        spacing="4", width="100%",
                    ),
                    rx.flex(
                        rx.checkbox("2 roles por hoja", checked=_S.dos_por_hoja,
                                    on_change=_S.toggle_doble),
                        rx.checkbox("Incluir logo", checked=_S.con_logo,
                                    on_change=_S.toggle_logo),
                        gap="5", wrap="wrap", align="center",
                    ),
                    rx.divider(),
                    rx.flex(
                        primary_button("Generar PDF", on_click=_S.generar_individual),
                        rx.cond(
                            _S.pdf_listo,
                            rx.button(rx.icon("download", size=15), "Descargar",
                                      on_click=_S.descargar_individual, variant="soft", size="3"),
                        ),
                        gap="2", align="center", wrap="wrap",
                    ),
                    rx.cond(_S.error != "", rx.callout(_S.error, color_scheme="red", size="1")),
                    spacing="4", width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                _S.pdf_preview != "",
                card(
                    rx.el.iframe(
                        src=_S.pdf_preview, width="100%", height="720px",
                        style={"border": "1px solid var(--gray-6)", "borderRadius": "8px"},
                    ),
                    width="100%",
                ),
            ),
            spacing="4", width="100%",
        ),
        requiere=("roles", "generar_pdf"),
    )
