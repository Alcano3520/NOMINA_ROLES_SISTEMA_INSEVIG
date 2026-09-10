"""/sanciones/novedades — cambios de horario que reportan los supervisores."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, data_cell, data_table, page_heading
from insevig_web.pages.sanciones._comunes import tabs_nav
from insevig_web.states.auth_state import AuthState
from insevig_web.states.sanciones_state import SancionesState

_S = SancionesState


def _fila(n: rx.Var) -> rx.Component:
    nid = n["id"].to_string()
    return rx.table.row(
        data_cell(n["id"].to_string()),
        data_cell(n["periodo"].to(str)),
        data_cell(rx.text(n["empleado_nombre"].to(str), size="1")),
        data_cell(rx.text(n["puesto_nuevo_nom"].to(str), size="1")),
        data_cell(rx.text(n["motivo"].to(str), size="1")),
        data_cell(
            rx.hstack(
                rx.input(
                    default_value=n["observacion_rrhh"].to(str),
                    placeholder="Observación RRHH…", size="1", width="180px",
                    on_change=lambda v: _S.set_nov_obs(nid, v),
                ),
                rx.cond(
                    AuthState.permisos_flat.contains("sanciones:editar"),
                    rx.button("Marcar procesada", size="1",
                              on_click=lambda: _S.nov_marcar(n["id"])),
                ),
                align="center", spacing="1",
            )
        ),
    )


@rx.page(route="/sanciones/novedades", title="INSEVIG — Sanciones · Novedades de horario",
         on_load=[AuthState.cargar_sesion, SancionesState.nov_cargar])
def novedades() -> rx.Component:
    return pagina(
        page_heading("Novedades de horario",
                     "Cambios de horario que cargan los supervisores desde la app. "
                     "Marcá cada una como procesada cuando la apliques en la nómina."),
        tabs_nav("/sanciones/novedades"),
        rx.vstack(
            rx.flex(
                rx.button("Recargar", on_click=_S.nov_cargar, size="2", variant="soft",
                          loading=_S.nov_cargando),
                rx.spacer(),
                rx.text(_S.nov.length().to_string() + " pendientes", size="1", color_scheme="gray"),
                align="center", width="100%",
            ),
            rx.cond(
                _S.nov.length() > 0,
                card(
                    data_table(
                        ["#", "Período", "Empleado", "Puesto nuevo", "Motivo", "Acción"],
                        rx.foreach(_S.nov, _fila),
                    ),
                    width="100%",
                ),
                rx.callout("Sin novedades pendientes.", size="1", color_scheme="gray"),
            ),
            spacing="4", width="100%",
        ),
        requiere=("sanciones", "ver"),
    )
