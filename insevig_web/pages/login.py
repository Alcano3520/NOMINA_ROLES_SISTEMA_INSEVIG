from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.ui import primary_button
from insevig_web.states.auth_state import AuthState


@rx.page(route="/login", title="INSEVIG — Acceso")
def login() -> rx.Component:
    return rx.center(
        rx.card(
            rx.vstack(
                rx.heading("INSEVIG", size="7", color=theme.PRIMARY),
                rx.text("Sistema Integrado de Nómina", color_scheme="gray", size="2"),
                rx.divider(margin_y="1rem"),
                rx.form(
                    rx.vstack(
                        rx.text("Usuario", size="2", weight="bold"),
                        rx.input(name="usuario", placeholder="usuario", size="3", width="100%"),
                        rx.text("Contraseña", size="2", weight="bold", margin_top="0.5rem"),
                        rx.input(
                            name="clave",
                            type="password",
                            placeholder="••••••••",
                            size="3",
                            width="100%",
                        ),
                        rx.cond(
                            AuthState.error_login != "",
                            rx.callout(
                                AuthState.error_login,
                                icon="triangle_alert",
                                color_scheme="red",
                                size="1",
                                margin_top="0.5rem",
                            ),
                        ),
                        primary_button(
                            "Acceder", type="submit", width="100%", margin_top="1rem"
                        ),
                        spacing="1",
                        width="100%",
                    ),
                    on_submit=AuthState.login,
                    width="100%",
                ),
                spacing="1",
                width="100%",
            ),
            width=rx.breakpoints(initial="92vw", sm="380px"),
            padding="2rem",
        ),
        height="100vh",
        background=theme.BG,
    )
