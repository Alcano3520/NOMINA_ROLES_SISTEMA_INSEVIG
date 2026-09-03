from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.registrador_state import RegistradorState


@rx.page(
    route="/registrador/manual",
    title="INSEVIG — Registro manual",
    on_load=[AuthState.cargar_sesion, RegistradorState.on_load],
)
def manual() -> rx.Component:
    return pagina(
        page_heading("Registro manual", "Alta puntual de un ingreso o egreso para un empleado."),
        rx.vstack(
            card(
                rx.vstack(
                    rx.grid(
                        rx.vstack(rx.text("Período (YYYY-MM)", size="1", weight="bold"),
                                  rx.input(value=RegistradorState.periodo, on_change=RegistradorState.set_periodo)),
                        rx.vstack(rx.text("Empleado", size="1", weight="bold"),
                                  rx.input(value=RegistradorState.m_empleado, on_change=lambda v: RegistradorState.set_m("empleado", v))),
                        rx.vstack(rx.text("CLASE", size="1", weight="bold"),
                                  rx.input(value=RegistradorState.m_clase, on_change=lambda v: RegistradorState.set_m("clase", v))),
                        rx.vstack(rx.text("Valor", size="1", weight="bold"),
                                  rx.input(value=RegistradorState.m_valor, on_change=lambda v: RegistradorState.set_m("valor", v))),
                        rx.vstack(rx.text("Concepto", size="1", weight="bold"),
                                  rx.input(value=RegistradorState.m_concepto, on_change=lambda v: RegistradorState.set_m("concepto", v))),
                        columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                        spacing="3",
                        width="100%",
                    ),
                    rx.cond(
                        AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                        primary_button("Registrar", on_click=RegistradorState.registrar_manual),
                    ),
                    rx.cond(RegistradorState.error != "", rx.callout(RegistradorState.error, color_scheme="red", size="1")),
                    rx.cond(RegistradorState.resultado != "", rx.callout(RegistradorState.resultado, color_scheme="green", size="1")),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("registrador", "registrar_rpingdes"),
    )
