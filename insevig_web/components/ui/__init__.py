"""Sistema de diseño. Los módulos usan SOLO estos componentes, nunca estilos
propios — así la consistencia visual y la responsividad se arreglan en un lugar.

★ CONGELADO — cambiar aquí impacta TODA la app.
"""

from __future__ import annotations

import reflex as rx

from insevig_web import theme


def page_heading(titulo: str, subtitulo: str = "") -> rx.Component:
    """Encabezado de página: barra de acento + título + subtítulo, con divisor
    inferior. Compacto (densidad ERP)."""
    return rx.box(
        rx.hstack(
            rx.box(
                width="4px", align_self="stretch", border_radius="9999px",
                background=theme.PRIMARY, flex_shrink="0",
            ),
            rx.vstack(
                rx.heading(titulo, size=rx.breakpoints(initial="5", md="7"), weight="bold"),
                rx.cond(subtitulo != "", rx.text(subtitulo, color_scheme="gray", size="2")),
                spacing="1", align_items="start",
            ),
            spacing="3", align="stretch", width="100%",
        ),
        border_bottom="1px solid var(--gray-4)",
        padding_bottom="0.6rem",
        margin_bottom="0.9rem",
        width="100%",
    )


def card(*children, **props) -> rx.Component:
    """Tarjeta con elevación real (borde fino + sombra suave). Acepta los
    mismos overrides que `rx.card`."""
    base = {
        "border": "1px solid var(--gray-4)",
        "box_shadow": theme.SHADOW_SM,
        "background": "var(--color-panel-solid)",
    }
    base.update(props)
    return rx.card(*children, size=rx.breakpoints(initial="1", md="2"), **base)


def stat_card(titulo: str, descripcion: str, valor: str, icono: str) -> rx.Component:
    return card(
        rx.vstack(
            rx.hstack(
                rx.center(
                    rx.icon(icono, size=18, color="white"),
                    background=theme.PRIMARY, border_radius="8px",
                    width="30px", height="30px", flex_shrink="0",
                ),
                rx.text(titulo, size="2", weight="bold", color_scheme="gray"),
                spacing="2", align="center", width="100%",
            ),
            rx.heading(valor, size="7", weight="bold", color="var(--blue-11)"),
            rx.text(descripcion, color_scheme="gray", size="1"),
            spacing="1", align="start", width="100%",
        ),
        width="100%",
    )


# ── Tabla de datos compacta (estilo ERP / Excel) ────────────────────────────
# La densidad y la cuadrícula las pone `assets/theme.css` para TODAS las
# `.rt-Table*`; estos helpers son solo azúcar para armarlas rápido.

def data_table(cabeceras: list[str], filas: rx.Component, **box_props) -> rx.Component:
    """`rx.table` con la cuadrícula/densidad del sistema. `filas` es el
    resultado de un `rx.foreach(...)` que produce `rx.table.row(...)`."""
    box_props.setdefault("width", "100%")
    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    *[rx.table.column_header_cell(c) for c in cabeceras],
                )
            ),
            rx.table.body(filas),
            variant="surface",
            size="1",
            width="100%",
        ),
        overflow_x="auto",
        box_shadow=theme.SHADOW_SM,
        border_radius="8px",
        **box_props,
    )


def data_cell(*children, **props) -> rx.Component:
    return rx.table.cell(*children, **props)


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
