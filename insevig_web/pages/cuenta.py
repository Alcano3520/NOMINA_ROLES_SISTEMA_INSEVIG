from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState


@rx.page(
    route="/mi-cuenta",
    title="INSEVIG — Mi cuenta",
    on_load=AuthState.cargar_sesion,
)
def mi_cuenta() -> rx.Component:
    return pagina(
        page_heading("Mi cuenta", "Datos de tu usuario y cambio de contraseña."),
        rx.vstack(
            card(
                rx.vstack(
                    rx.text("Usuario: " + AuthState.username, size="2"),
                    rx.text("Nombre: " + AuthState.nombre, size="2"),
                    spacing="1",
                ),
                width="100%",
            ),
            card(
                rx.form(
                    rx.vstack(
                        rx.heading("Cambiar contraseña", size="3"),
                        rx.input(name="actual", type="password", placeholder="Contraseña actual", width="100%"),
                        rx.input(name="nueva", type="password", placeholder="Nueva contraseña", width="100%"),
                        rx.input(name="confirmar", type="password", placeholder="Repetir nueva contraseña", width="100%"),
                        primary_button("Actualizar", type="submit"),
                        rx.cond(
                            AuthState.clave_msg != "",
                            rx.callout(AuthState.clave_msg, size="1"),
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    on_submit=AuthState.cambiar_mi_clave,
                    reset_on_submit=True,
                ),
                width="100%",
                max_width="420px",
            ),
            spacing="4",
            width="100%",
        ),
    )
