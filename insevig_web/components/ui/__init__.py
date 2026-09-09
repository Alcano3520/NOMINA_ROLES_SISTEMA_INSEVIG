"""Sistema de diseño. Los módulos usan SOLO estos componentes, nunca estilos
propios — así la consistencia visual y la responsividad se arreglan en un lugar.

★ CONGELADO — cambiar aquí impacta TODA la app.
"""

from __future__ import annotations

import reflex as rx

from insevig_web import theme


def page_heading(titulo: str, subtitulo: str = "") -> rx.Component:
    """Encabezado de página: barra de acento + título grande + subtítulo, con
    divisor inferior para separar del contenido."""
    return rx.box(
        rx.hstack(
            rx.box(
                width="4px", align_self="stretch", border_radius="9999px",
                background=theme.PRIMARY, flex_shrink="0",
            ),
            rx.vstack(
                rx.heading(titulo, size=rx.breakpoints(initial="6", md="8"), weight="bold"),
                rx.cond(subtitulo != "", rx.text(subtitulo, color_scheme="gray", size="3")),
                spacing="1", align_items="start",
            ),
            spacing="3", align="stretch", width="100%",
        ),
        border_bottom="1px solid var(--gray-4)",
        padding_bottom="1rem",
        margin_bottom="1.5rem",
        width="100%",
    )


def card(*children, **props) -> rx.Component:
    """Tarjeta con elevación real (borde fino + sombra suave) para que se
    separe del fondo. Acepta los mismos overrides que `rx.card`."""
    base = {
        "border": "1px solid var(--gray-4)",
        "box_shadow": theme.SHADOW_SM,
        "background": "var(--color-panel-solid)",
    }
    base.update(props)
    return rx.card(*children, size=rx.breakpoints(initial="2", md="3"), **base)


def stat_card(titulo: str, descripcion: str, valor: str, icono: str) -> rx.Component:
    return card(
        rx.vstack(
            rx.hstack(
                rx.center(
                    rx.icon(icono, size=20, color="white"),
                    background=theme.PRIMARY, border_radius="10px",
                    width="36px", height="36px", flex_shrink="0",
                ),
                rx.text(titulo, size="2", weight="bold", color_scheme="gray"),
                spacing="3", align="center", width="100%",
            ),
            rx.heading(valor, size="8", weight="bold", color="var(--blue-11)"),
            rx.text(descripcion, color_scheme="gray", size="2"),
            spacing="2", align="start", width="100%",
        ),
        width="100%",
    )


def primary_button(texto: str, **props) -> rx.Component:
    return rx.button(texto, size="3", color_scheme="blue", **props)


def scroll_x(*children, **props) -> rx.Component:
    """Contenedor con scroll horizontal propio (para tablas anchas)."""
    return rx.box(*children, overflow_x="auto", width="100%", **props)


def placeholder(titulo: str, fase: str) -> rx.Component:
    return card(
        rx.vstack(
            rx.icon("construction", size=32, color=theme.PRIMARY),
            rx.heading(titulo, size="5"),
            rx.text(f"Módulo pendiente ({fase}).", color_scheme="gray"),
            spacing="2",
            align="center",
            padding="2rem",
        ),
        width="100%",
    )
