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


_NATIVE_SELECT_SIZES = {
    "1": {"padding": "6px 8px", "fontSize": "13px"},
    "2": {"padding": "7px 8px", "fontSize": "14px", "width": "100%"},
}


def native_select(*opciones, size: str = "2", **props) -> rx.Component:
    """`rx.el.select` con el estilo del sistema (Radix no expone un `<select>`
    nativo estilable). `size="1"` = compacto sin ancho forzado (barras de
    filtro); `size="2"` = campo de formulario a `width:100%`."""
    style = {
        "borderRadius": "6px", "border": "1px solid var(--gray-6)",
        "background": "var(--color-panel-solid)", "color": "var(--gray-12)",
        **_NATIVE_SELECT_SIZES.get(size, _NATIVE_SELECT_SIZES["2"]),
    }
    style.update(props.pop("style", {}))
    return rx.el.select(*opciones, style=style, **props)


def field_label(texto: str) -> rx.Component:
    """Forma canónica de etiqueta de campo (encima de un input/select)."""
    return rx.text(texto, size="1", weight="bold", color_scheme="gray")


def section_box(titulo: str, *children, tono: str = "neutral", **props) -> rx.Component:
    """Recuadro con título tipo LabelFrame: punto de color + título en
    mayúsculas + caja bordeada. `tono="peligro"` para zonas destructivas.
    No arma el layout interno — el llamador decide qué va adentro."""
    punto = "var(--red-9)" if tono == "peligro" else "var(--blue-9)"
    fondo = "var(--red-2)" if tono == "peligro" else "var(--gray-2)"
    borde = "var(--red-6)" if tono == "peligro" else "var(--gray-5)"
    base = {"border": f"1px solid {borde}", "border_radius": "8px",
            "padding": "12px", "width": "100%", "background": fondo}
    base.update(props)
    return rx.box(
        rx.hstack(
            rx.box(width="7px", height="7px", border_radius="9999px",
                   background=punto, flex_shrink="0"),
            rx.text(titulo.upper(), size="1", weight="bold", letter_spacing="0.05em",
                    color_scheme=("red" if tono == "peligro" else "gray")),
            spacing="2", align="center", margin_bottom="8px",
        ),
        *children,
        **base,
    )


def empty_state(icono: str, titulo: str, texto: str) -> rx.Component:
    """Estado vacío centrado (sin ficha abierta, sin resultados, etc.)."""
    return rx.center(
        rx.vstack(
            rx.icon(icono, size=40, color="var(--gray-8)"),
            rx.heading(titulo, size="4", color_scheme="gray"),
            rx.text(texto, size="2", color_scheme="gray", text_align="center"),
            spacing="3", align="center", max_width="24em",
        ),
        padding="3rem", width="100%", min_height="280px",
    )


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

def data_table(cabeceras: list[str], filas: rx.Component, *, max_height: str = "",
              **box_props) -> rx.Component:
    """`rx.table` con la cuadrícula/densidad del sistema. `filas` es el
    resultado de un `rx.foreach(...)` que produce `rx.table.row(...)`.
    `max_height`: si se pasa, el scroll vertical queda DENTRO de este box (así
    la sombra/radio envuelven el área scrolleable, en vez de quedar recortados
    por un contenedor manual del llamador)."""
    box_props.setdefault("width", "100%")
    if max_height:
        box_props.setdefault("max_height", max_height)
        box_props.setdefault("overflow_y", "auto")
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


def primary_button(*children, **props) -> rx.Component:
    """Acepta uno o varios hijos (ej. `primary_button(rx.icon("plus"), "Nuevo")`)
    igual que un string único, como antes. `size`/`color_scheme` son overrideables
    (por defecto `size="3"`, `color_scheme="blue"`, igual que siempre)."""
    props.setdefault("size", "3")
    props.setdefault("color_scheme", "blue")
    return rx.button(*children, **props)


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
