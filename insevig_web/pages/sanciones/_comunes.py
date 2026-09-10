"""Piezas compartidas de las páginas de sanciones."""

from __future__ import annotations

import reflex as rx

from insevig_web.states.sanciones_state import SancionesState

_S = SancionesState

_TABS = [
    ("Bandeja", "/sanciones/bandeja"),
    ("Historial", "/sanciones/historial"),
    ("Buscar", "/sanciones/buscar"),
    ("Novedades de horario", "/sanciones/novedades"),
    ("Estadísticas", "/sanciones/estadisticas"),
]

_COLOR_ESTADO = {
    "borrador": "gray", "enviado": "amber", "aprobado": "grass",
    "rechazado": "red", "procesado": "blue",
}


def tabs_nav(activo: str) -> rx.Component:
    return rx.flex(
        *[
            rx.link(
                rx.text(txt, size="2", weight=rx.cond(ruta == activo, "bold", "regular")),
                href=ruta, padding="6px 12px",
                border_bottom=rx.cond(ruta == activo, "2px solid var(--accent-9)", "2px solid transparent"),
                color=rx.cond(ruta == activo, "var(--accent-11)", "var(--gray-11)"),
            )
            for txt, ruta in _TABS
        ],
        gap="1", wrap="wrap", border_bottom="1px solid var(--gray-4)", margin_bottom="1rem",
    )


def badge_estado(estado: rx.Var) -> rx.Component:
    return rx.badge(
        estado,
        color_scheme=rx.match(estado, *[(k, v) for k, v in _COLOR_ESTADO.items()], "gray"),
        size="1",
    )


def _dato(etq: str, valor: rx.Var) -> rx.Component:
    return rx.vstack(
        rx.text(etq, size="1", weight="bold", color_scheme="gray"),
        rx.text(valor, size="2"), spacing="1",
    )


def dialog_detalle() -> rx.Component:
    d = _S.detalle
    return rx.dialog.root(
        rx.dialog.content(
            rx.flex(
                rx.dialog.title(rx.text(d["tipo_sancion"].to(str), size="4", weight="bold")),
                rx.spacer(),
                badge_estado(d["status"].to(str)),
                align="center", width="100%",
            ),
            rx.grid(
                _dato("Empleado", d["empleado_nombre"].to(str)),
                _dato("Cédula", d["empleado_cedula"].to(str)),
                _dato("Código", d["empleado_cod"].to_string()),
                _dato("Cargo", d["empleado_cargo"].to(str)),
                _dato("Departamento", d["empleado_departamento"].to(str)),
                _dato("Puesto", d["puesto"].to(str)),
                _dato("Fecha", d["fecha"].to(str)),
                _dato("Hora", d["hora"].to(str)),
                _dato("Agente", d["agente"].to(str)),
                columns=rx.breakpoints(initial="2", sm="3"), spacing="3", width="100%",
                margin_top="0.6rem",
            ),
            rx.divider(margin_y="0.6rem"),
            _dato("Observaciones", d["observaciones"].to(str)),
            rx.cond(
                d["observaciones_adicionales"].to(str) != "",
                _dato("Observaciones adicionales", d["observaciones_adicionales"].to(str)),
            ),
            rx.cond(
                d["comentarios_gerencia"].to(str) != "",
                _dato("Comentarios de gerencia", d["comentarios_gerencia"].to(str)),
            ),
            rx.cond(
                d["comentarios_rrhh"].to(str) != "",
                _dato("Comentarios RRHH", d["comentarios_rrhh"].to(str)),
            ),
            rx.flex(
                rx.cond(
                    _S.detalle_urls["firma"].to(str) != "",
                    rx.link("Ver firma ↗", href=_S.detalle_urls["firma"].to(str), is_external=True, size="1"),
                ),
                rx.cond(
                    _S.detalle_urls["foto"].to(str) != "",
                    rx.link("Ver foto de evidencia ↗", href=_S.detalle_urls["foto"].to(str),
                            is_external=True, size="1"),
                ),
                gap="3", margin_top="0.6rem", wrap="wrap",
            ),
            rx.flex(
                rx.button(rx.icon("file-down", size=14), "PDF", on_click=_S.descargar_pdf_detalle,
                          size="2", variant="soft"),
                rx.spacer(),
                rx.dialog.close(rx.button("Cerrar", on_click=_S.cerrar_detalle, variant="soft")),
                margin_top="1rem", width="100%",
            ),
            max_width="640px",
        ),
        open=_S.detalle_abierto,
    )
