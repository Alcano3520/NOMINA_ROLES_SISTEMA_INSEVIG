"""Shell de la app: header + sidebar responsive + contenedor de contenido.

Es la interfaz principal de integración. Toda página de módulo se envuelve con
`pagina(...)`. ★ CONGELADO.
"""

from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.sidebar import sidebar_drawer, sidebar_fijo
from insevig_web.state import AppState
from insevig_web.states.auth_state import AuthState


def _header() -> rx.Component:
    return rx.hstack(
        rx.button(
            rx.icon("menu", size=20),
            on_click=AppState.toggle_sidebar,
            variant="ghost",
            color="white",
            display=rx.breakpoints(initial="flex", lg="none"),
        ),
        rx.heading(
            "INSEVIG — Sistema Integrado",
            size=rx.breakpoints(initial="3", md="4"),
            color=theme.SECONDARY,
        ),
        rx.spacer(),
        rx.hstack(
            rx.color_mode.button(size="2"),
            rx.icon("user", size=16, color="white"),
            rx.text(AuthState.nombre, color="white", size="2"),
            spacing="2",
            align="center",
        ),
        width="100%",
        height="60px",
        padding_x="1rem",
        background=theme.PRIMARY,
        align="center",
        position="sticky",
        top="0",
        z_index="10",
    )


def pagina(
    *contenido: rx.Component,
    requiere: tuple[str, str] | None = None,
) -> rx.Component:
    """Envuelve el contenido de una página de módulo en la shell.

    `requiere=(modulo, accion)` protege la página: si el rol no cumple, muestra
    "sin permiso". El `on_load=AuthState.cargar_sesion` lo pone cada `@rx.page`.
    """
    cuerpo = rx.box(
        *contenido,
        padding=rx.breakpoints(initial="1rem", md="1.5rem 2rem"),
        width="100%",
        max_width="1400px",
        margin="0 auto",
    )

    if requiere is not None:
        modulo, accion = requiere
        cuerpo = rx.cond(
            AuthState.permisos_flat.contains(f"{modulo}:{accion}"),
            cuerpo,
            rx.center(
                rx.vstack(
                    rx.icon("lock", size=40),
                    rx.heading("Sin permiso", size="5"),
                    rx.text("Tu rol no tiene acceso a esta sección.", color_scheme="gray"),
                    rx.link("Volver al inicio", href="/"),
                    spacing="3",
                    align="center",
                ),
                height="70vh",
            ),
        )

    return rx.cond(
        AuthState.autenticado,
        rx.hstack(
            sidebar_fijo(),
            sidebar_drawer(),
            rx.box(
                _header(),
                cuerpo,
                flex="1",
                min_width="0",
                min_height="100vh",
                background=theme.BG,
            ),
            spacing="0",
            width="100%",
            align="start",
        ),
        rx.center(
            rx.vstack(
                rx.spinner(size="3"),
                rx.text("Verificando sesión…", color_scheme="gray"),
                rx.link("Ir a iniciar sesión", href="/login"),
                spacing="3",
            ),
            height="100vh",
        ),
    )
