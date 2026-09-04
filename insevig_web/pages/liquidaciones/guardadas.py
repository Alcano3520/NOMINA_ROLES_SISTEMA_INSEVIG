"""Liquidaciones guardadas — Editor + Gestión de liquidaciones (módulo 9)
combinados: buscar, ver detalle, cambiar estado, eliminar y regenerar PDF."""

from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.liquidaciones_guardadas_state import ESTADOS, LiquidacionesGuardadasState

_S = LiquidacionesGuardadasState
_SEL = {
    "padding": "6px", "borderRadius": "6px", "border": "1px solid var(--gray-6)",
    "background": "#fff", "color": "#1f2937",
}
_COLOR_ESTADO = {
    "borrador": "gray", "generada": "blue", "pagada": "green", "anulada": "red",
}


def _badge_estado(estado: rx.Var) -> rx.Component:
    return rx.badge(estado, color_scheme=rx.match(
        estado, ("borrador", "gray"), ("generada", "blue"), ("pagada", "green"), ("anulada", "red"), "gray"
    ))


def _fila(f) -> rx.Component:
    return rx.table.row(
        rx.table.cell(f["empleado_codigo"]),
        rx.table.cell(f["nombre"]),
        rx.table.cell(f["cargo"]),
        rx.table.cell(f["fecha_salida"]),
        rx.table.cell(f["tipo_liquidacion"]),
        rx.table.cell(_badge_estado(f["estado"])),
        rx.table.cell("$" + f["total_liquido"].to_string()),
        rx.table.cell(
            rx.hstack(
                rx.button("Ver", on_click=lambda: _S.ver_detalle(f["id"]), size="1", variant="soft"),
                rx.button("PDF", on_click=lambda: _S.generar_pdf(f["id"]), size="1", variant="soft"),
                spacing="1",
            )
        ),
    )


def _detalle() -> rx.Component:
    return rx.cond(
        _S.detalle_id != "",
        card(
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        _S.detalle["empleado_apellidos"].to_string() + " " + _S.detalle["empleado_nombres"].to_string(),
                        size="3",
                    ),
                    rx.spacer(),
                    rx.button("Cerrar", on_click=_S.cerrar_detalle, variant="soft", size="1"),
                    width="100%", align="center",
                ),
                rx.cond(
                    _S.detalle_msg != "",
                    rx.callout(_S.detalle_msg, color_scheme="red", size="1"),
                ),
                rx.cond(
                    _S.detalle.contains("id"),
                    rx.vstack(
                        rx.grid(
                            rx.text("Código: " + _S.detalle["empleado_codigo"].to_string(), size="2"),
                            rx.text("Cédula: " + _S.detalle["empleado_cedula"].to_string(), size="2"),
                            rx.text("Cargo: " + _S.detalle["cargo"].to_string(), size="2"),
                            rx.text("Sección: " + _S.detalle["seccion"].to_string(), size="2"),
                            rx.text("Ingreso: " + _S.detalle["fecha_ingreso"].to_string(), size="2"),
                            rx.text("Salida: " + _S.detalle["fecha_salida"].to_string(), size="2"),
                            rx.text("Motivo: " + _S.detalle["motivo"].to_string(), size="2"),
                            rx.text("Días trabajados: " + _S.detalle["dias_trabajados"].to_string(), size="2"),
                            columns=rx.breakpoints(initial="1", sm="2", lg="4"),
                            spacing="2", width="100%",
                        ),
                        rx.divider(),
                        scroll_x(
                            rx.table.root(
                                rx.table.header(rx.table.row(*[
                                    rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                                    for c in ("Concepto", "Tipo", "Valor")
                                ])),
                                rx.table.body(
                                    rx.foreach(
                                        _S.detalle_conceptos,
                                        lambda c: rx.table.row(
                                            rx.table.cell(c["concepto_nombre"]),
                                            rx.table.cell(c["concepto_tipo"]),
                                            rx.table.cell("$" + c["valor_total"].to_string()),
                                        ),
                                    )
                                ),
                                variant="surface", size="1", width="100%",
                            )
                        ),
                        rx.hstack(
                            rx.text("Total líquido: $" + _S.detalle["total_liquido"].to_string(),
                                    weight="bold", size="3"),
                            spacing="2",
                        ),
                        rx.divider(),
                        rx.hstack(
                            rx.text("Cambiar estado:", size="1", weight="bold"),
                            rx.el.select(
                                *[rx.el.option(e, value=e) for e in ESTADOS],
                                value=_S.detalle["estado"].to_string(),
                                on_change=lambda v: _S.cambiar_estado(_S.detalle_id, v),
                                style=_SEL,
                            ),
                            rx.button("PDF", on_click=lambda: _S.generar_pdf(_S.detalle_id), size="1", variant="soft"),
                            rx.cond(
                                AuthState.es_admin,
                                rx.alert_dialog.root(
                                    rx.alert_dialog.trigger(
                                        rx.button("Eliminar", size="1", color_scheme="red", variant="soft")
                                    ),
                                    rx.alert_dialog.content(
                                        rx.alert_dialog.title("Eliminar liquidación"),
                                        rx.alert_dialog.description(
                                            "Se eliminará esta liquidación (queda un respaldo interno). "
                                            "No se puede deshacer desde aquí."
                                        ),
                                        rx.hstack(
                                            rx.alert_dialog.cancel(rx.button("Cancelar", variant="soft")),
                                            rx.alert_dialog.action(
                                                rx.button("Sí, eliminar",
                                                          on_click=lambda: _S.eliminar(_S.detalle_id),
                                                          color_scheme="red")
                                            ),
                                            spacing="3", justify="end", margin_top="1rem",
                                        ),
                                    ),
                                ),
                            ),
                            spacing="2", align="center", wrap="wrap",
                        ),
                        spacing="3", width="100%",
                    ),
                ),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
    )


@rx.page(
    route="/liquidaciones/guardadas",
    title="INSEVIG — Liquidaciones guardadas",
    on_load=[AuthState.cargar_sesion, LiquidacionesGuardadasState.buscar],
)
def guardadas() -> rx.Component:
    return pagina(
        page_heading(
            "Liquidaciones guardadas",
            "Editor y Gestión: liquidaciones ya guardadas en el sistema — buscar, ver, "
            "cambiar estado, eliminar y regenerar PDF.",
        ),
        rx.vstack(
            card(
                rx.hstack(
                    rx.input(value=_S.texto, on_change=_S.set_texto,
                             placeholder="nombre, cédula o código…", width="220px", size="2"),
                    rx.el.select(
                        rx.el.option("(todos)", value="(todos)"),
                        *[rx.el.option(e, value=e) for e in ESTADOS],
                        default_value="(todos)", on_change=_S.set_estado_filtro, style=_SEL,
                    ),
                    rx.button("Buscar", on_click=_S.buscar, size="2"),
                    spacing="2", wrap="wrap",
                ),
                width="100%",
            ),
            rx.cond(_S.msg != "", rx.callout(_S.msg, size="1")),
            _detalle(),
            rx.cond(
                _S.cargando,
                rx.center(rx.spinner(), padding="1rem"),
                scroll_x(
                    rx.table.root(
                        rx.table.header(rx.table.row(*[
                            rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                            for c in ("Código", "Empleado", "Cargo", "Fecha salida", "Tipo", "Estado", "Total", "")
                        ])),
                        rx.table.body(rx.foreach(_S.filas, _fila)),
                        variant="surface", size="1", width="100%",
                    )
                ),
            ),
            spacing="4", width="100%",
        ),
        requiere=("liquidaciones", "ver"),
    )
