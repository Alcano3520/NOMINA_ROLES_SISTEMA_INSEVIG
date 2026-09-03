from __future__ import annotations

import reflex as rx

from insevig_web.components.data_source_selector import data_source_selector
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.roles_pdf_state import RolesState


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
                    rx.hstack(rx.text("Fuente:", weight="bold", size="2"), data_source_selector("roles"), spacing="2"),
                    rx.hstack(
                        rx.input(
                            value=RolesState.identificador,
                            on_change=RolesState.set_identificador,
                            placeholder="Código / cédula / nombre",
                            width="240px",
                        ),
                        rx.input(
                            value=RolesState.periodo,
                            on_change=RolesState.set_periodo,
                            placeholder="2026-06",
                            width="120px",
                        ),
                        spacing="2",
                        wrap="wrap",
                    ),
                    rx.checkbox("2 roles por hoja", checked=RolesState.dos_por_hoja, on_change=RolesState.toggle_doble),
                    rx.hstack(
                        primary_button("Generar PDF", on_click=RolesState.generar_individual),
                        rx.cond(
                            RolesState.pdf_listo,
                            rx.button("Descargar", on_click=RolesState.descargar_individual),
                        ),
                        spacing="2",
                    ),
                    rx.cond(RolesState.error != "", rx.callout(RolesState.error, color_scheme="red", size="1")),
                    rx.cond(RolesState.pdf_listo, rx.callout("PDF listo para descargar.", color_scheme="green", size="1")),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("roles", "generar_pdf"),
    )
