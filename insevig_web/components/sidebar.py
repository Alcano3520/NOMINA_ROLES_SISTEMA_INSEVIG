"""Menú lateral. Se arma desde `registry.MODULES`, filtrado por permisos.

★ CONGELADO: para añadir una entrada, registra un `ModuleSpec`, no edites esto.
"""

from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.registry import MODULES, ModuleSpec
from insevig_web.state import AppState
from insevig_web.states.auth_state import AuthState


def _entrada(spec: ModuleSpec) -> rx.Component:
    fila = rx.hstack(
        rx.icon(spec.icono, size=18),
        rx.text(spec.titulo, size="2"),
        *([] if spec.disponible else [rx.badge("pronto", color_scheme="gray", size="1")]),
        spacing="3",
        align="center",
        width="100%",
        padding_y="0.6rem",
        padding_x="0.75rem",
    )
    enlace = rx.link(
        fila,
        href=spec.ruta_principal,
        color="white",
        width="100%",
        _hover={"background": theme.HOVER, "text_decoration": "none"},
        border_radius="0.375rem",
        on_click=AppState.cerrar_sidebar,
    )
    return rx.cond(AuthState.permisos_flat.contains(f"{spec.nombre}:ver"), enlace)


def sidebar_contenido() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading("INSEVIG", size="5", color=theme.SECONDARY),
            rx.text("RRHH", size="1", color="white"),
            spacing="2",
            align="baseline",
            padding="1rem 0.75rem",
        ),
        rx.divider(),
        rx.vstack(*[_entrada(m) for m in MODULES], spacing="1", width="100%"),
        rx.spacer(),
        rx.button(
            rx.hstack(rx.icon("log-out", size=16), rx.text("Salir")),
            on_click=AuthState.logout,
            variant="soft",
            color_scheme="red",
            width="100%",
        ),
        spacing="2",
        height="100%",
        width="100%",
        padding="0.5rem",
        background=theme.SIDEBAR,
        align_items="start",
    )


def sidebar_fijo() -> rx.Component:
    """Visible en escritorio (>= lg)."""
    return rx.box(
        sidebar_contenido(),
        display=rx.breakpoints(initial="none", lg="block"),
        width="250px",
        min_width="250px",
        height="100vh",
        position="sticky",
        top="0",
    )


def sidebar_drawer() -> rx.Component:
    """Drawer para móvil/tablet (< lg)."""
    return rx.drawer.root(
        rx.drawer.overlay(),
        rx.drawer.portal(
            rx.drawer.content(
                sidebar_contenido(),
                width="250px",
                height="100%",
                background=theme.SIDEBAR,
            )
        ),
        open=AppState.sidebar_abierto,
        on_open_change=AppState.set_sidebar,
        direction="left",
    )
