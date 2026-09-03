"""Sistema de diseño. Los módulos usan SOLO estos componentes, nunca estilos
propios — así la consistencia visual y la responsividad se arreglan en un lugar.

★ CONGELADO.
"""

from __future__ import annotations

import reflex as rx

from insevig_web import theme


def page_heading(titulo: str, subtitulo: str = "") -> rx.Component:
    return rx.vstack(
        rx.heading(titulo, size=rx.breakpoints(initial="6", md="7")),
        rx.cond(subtitulo != "", rx.text(subtitulo, color_scheme="gray", size="2")),
        spacing="1",
        margin_bottom="1rem",
        align_items="start",
    )


def card(*children, **props) -> rx.Component:
    return rx.card(*children, size=rx.breakpoints(initial="2", md="3"), **props)


def stat_card(titulo: str, descripcion: str, valor: str, icono: str) -> rx.Component:
    return card(
        rx.hstack(
            rx.icon(icono, size=22, color=theme.PRIMARY),
            rx.heading(titulo, size="4"),
            spacing="2",
            align="center",
        ),
        rx.text(descripcion, color_scheme="gray", size="2", margin_y="0.5rem"),
        rx.heading(valor, size="8", color=theme.SECONDARY),
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
