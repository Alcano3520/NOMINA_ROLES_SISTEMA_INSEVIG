"""/sanciones/estadisticas — conteos + configuración de valores monetarios."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, data_cell, data_table, page_heading, stat_card
from insevig_web.pages.sanciones._comunes import tabs_nav
from insevig_web.states.auth_state import AuthState
from insevig_web.states.sanciones_state import SancionesState

_S = SancionesState


def _fila_estado(r: rx.Var) -> rx.Component:
    return rx.table.row(data_cell(r["k"]), data_cell(r["v"].to_string()))


def _fila_valor(r: rx.Var) -> rx.Component:
    tipo = r["tipo"].to_string()
    return rx.table.row(
        data_cell(r["tipo"]),
        data_cell(
            rx.hstack(
                rx.input(default_value=r["valor"].to_string(), size="1", width="90px",
                         on_change=lambda v: _S.set_val_edit(tipo, v)),
                rx.cond(
                    AuthState.permisos_flat.contains("sanciones:editar"),
                    rx.button("Guardar", size="1", variant="soft",
                              on_click=lambda: _S.guardar_valor(r["tipo"])),
                ),
                align="center", spacing="1",
            )
        ),
    )


@rx.page(route="/sanciones/estadisticas", title="INSEVIG — Sanciones · Estadísticas",
         on_load=[AuthState.cargar_sesion, SancionesState.stats_cargar, SancionesState.cargar_valores])
def estadisticas() -> rx.Component:
    return pagina(
        page_heading("Estadísticas de sanciones", "Sobre la tabla del proyecto de sanciones."),
        tabs_nav("/sanciones/estadisticas"),
        rx.vstack(
            rx.cond(
                _S.stats_cargando,
                rx.center(rx.spinner(), padding="2rem"),
                rx.vstack(
                    rx.grid(
                        stat_card("Pendientes de aprobación", "esperando gerencia",
                                  _S.stats["pendientes_aprobacion"].to_string(), "inbox"),
                        stat_card("Pendientes de proceso", "esperando RRHH",
                                  _S.stats["pendientes_proceso"].to_string(), "clock"),
                        stat_card("Procesadas hoy", "con comentario RRHH",
                                  _S.stats["procesadas_hoy"].to_string(), "check-check"),
                        stat_card("Total procesadas", "histórico",
                                  _S.stats["total_procesadas"].to_string(), "archive"),
                        columns=rx.breakpoints(initial="1", sm="2", lg="4"), spacing="3", width="100%",
                    ),
                    rx.grid(
                        card(
                            rx.vstack(
                                rx.heading("Por estado", size="3"),
                                data_table(["Estado", "Cantidad"],
                                           rx.foreach(_S.stats_por_estado, _fila_estado)),
                                spacing="2", width="100%",
                            ),
                            width="100%",
                        ),
                        card(
                            rx.vstack(
                                rx.heading("Procesadas por tipo", size="3"),
                                data_table(["Tipo", "Cantidad"],
                                           rx.foreach(_S.stats_por_tipo, _fila_estado)),
                                spacing="2", width="100%",
                            ),
                            width="100%",
                        ),
                        columns=rx.breakpoints(initial="1", lg="2"), spacing="3", width="100%",
                    ),
                    spacing="4", width="100%",
                ),
            ),
            card(
                rx.vstack(
                    rx.heading("Valores monetarios por tipo de sanción", size="3"),
                    rx.text("Se usan en la hoja «Detalle Resumen» del Excel.", size="1",
                            color_scheme="gray"),
                    data_table(["Tipo", "Valor"], rx.foreach(_S.valores, _fila_valor)),
                    spacing="2", width="100%",
                ),
                width="100%",
            ),
            spacing="4", width="100%",
        ),
        requiere=("sanciones", "ver"),
    )
