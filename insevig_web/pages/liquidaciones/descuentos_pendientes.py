from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x
from insevig_web.pages.liquidaciones._nav import subnav
from insevig_web.states.auth_state import AuthState
from insevig_web.states.descuentos_pendientes_state import DescuentosPendientesState

_S = DescuentosPendientesState
_INP = {"size": "2"}


def _chip(label: str, valor: str) -> rx.Component:
    activo = _S.filtro == valor if valor != "todos" else _S.filtro == ""
    return rx.button(
        label,
        on_click=lambda: _S.set_filtro(valor),
        size="1",
        variant=rx.cond(activo, "solid", "soft"),
    )


def _form() -> rx.Component:
    return card(
        rx.vstack(
            rx.text("Registrar descuento", weight="bold", size="2"),
            rx.hstack(
                rx.input(value=_S.f_cedula, on_change=lambda v: _S.set_campo("cedula", v),
                         placeholder="Cédula", width="140px", **_INP),
                rx.input(value=_S.f_nombre, on_change=lambda v: _S.set_campo("nombre", v),
                         placeholder="Nombre (opcional)", width="220px", **_INP),
                rx.input(value=_S.f_monto, on_change=lambda v: _S.set_campo("monto", v),
                         placeholder="Monto", width="110px", **_INP),
                rx.input(value=_S.f_fecha, on_change=lambda v: _S.set_campo("fecha", v),
                         type="date", width="180px", **_INP),
                spacing="2", wrap="wrap",
            ),
            rx.hstack(
                rx.input(value=_S.f_motivo, on_change=lambda v: _S.set_campo("motivo", v),
                         placeholder="Motivo", width="100%", **_INP),
                primary_button("Registrar", on_click=_S.crear),
                spacing="2", width="100%", align="center",
            ),
            rx.divider(),
            rx.text("Registro masivo — una línea por descuento: cédula, monto, motivo", size="1"),
            rx.text_area(value=_S.bulk_texto, on_change=_S.set_bulk, rows="4", width="100%",
                         placeholder="0912345678, 25.50, Uniforme\n0923456789, 40, Anticipo"),
            rx.button("Cargar lista", on_click=_S.crear_masivo, size="2", variant="soft"),
            spacing="3", width="100%",
        ),
        width="100%",
    )


@rx.page(
    route="/liquidaciones/descuentos-pendientes",
    title="INSEVIG — Descuentos pendientes",
    on_load=[AuthState.cargar_sesion, DescuentosPendientesState.cargar],
)
def descuentos_pendientes() -> rx.Component:
    return pagina(
        subnav("/liquidaciones/descuentos-pendientes"),
        page_heading(
            "Descuentos pendientes",
            "Montos a descontar en la próxima liquidación del empleado. Se aplican solos al "
            "guardar la liquidación (no al previsualizar).",
        ),
        rx.link("← Volver a Liquidaciones guardadas", href="/liquidaciones/guardadas", size="2"),
        rx.vstack(
            rx.cond(
                AuthState.permisos_flat.contains("liquidaciones:editar"),
                _form(),
            ),
            rx.cond(_S.msg != "", rx.callout(_S.msg, size="1")),
            rx.hstack(
                _chip("Pendientes", "pendiente"),
                _chip("Aplicados", "aplicado"),
                _chip("Todos", "todos"),
                rx.spacer(),
                rx.cond(
                    AuthState.permisos_flat.contains("liquidaciones:editar")
                    & (_S.seleccion.length() > 0),
                    rx.button(
                        rx.icon("trash-2", size=14),
                        "Eliminar (" + _S.seleccion.length().to_string() + ")",
                        on_click=_S.eliminar_seleccionados, size="1", color_scheme="red", variant="soft",
                    ),
                ),
                width="100%", align="center", wrap="wrap",
            ),
            rx.cond(
                _S.cargando,
                rx.center(rx.spinner(), padding="1rem"),
                scroll_x(
                    rx.table.root(
                        rx.table.header(rx.table.row(*[
                            rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                            for c in ("", "Cédula", "Nombre", "Monto", "Motivo", "Fecha", "Estado")
                        ])),
                        rx.table.body(
                            rx.foreach(
                                _S.filas,
                                lambda d: rx.table.row(
                                    rx.table.cell(
                                        rx.cond(
                                            d["estado"] == "pendiente",
                                            rx.checkbox(
                                                checked=_S.seleccion.contains(d["id"]),
                                                on_change=lambda _v: _S.toggle_sel(d["id"]),
                                            ),
                                        )
                                    ),
                                    rx.table.cell(d["cedula_norm"]),
                                    rx.table.cell(d["empleado_nombre"]),
                                    rx.table.cell("$" + d["monto"].to_string()),
                                    rx.table.cell(d["motivo"]),
                                    rx.table.cell(d["fecha"]),
                                    rx.table.cell(
                                        rx.badge(
                                            d["estado"],
                                            color_scheme=rx.cond(d["estado"] == "aplicado", "green", "amber"),
                                        )
                                    ),
                                ),
                            )
                        ),
                        variant="surface", size="1", width="100%",
                    )
                ),
            ),
            rx.cond(_S.filas.length() == 0, rx.text("Sin descuentos.", size="2", color_scheme="gray")),
            spacing="4", width="100%",
        ),
        requiere=("liquidaciones", "ver"),
    )
