"""/sanciones/buscar — búsqueda server-side en Supabase."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, data_cell, data_table, page_heading, primary_button
from insevig_web.pages.sanciones._comunes import badge_estado, dialog_detalle, tabs_nav
from insevig_web.states.auth_state import AuthState
from insevig_web.states.sanciones_state import SancionesState

_S = SancionesState

_SEL = {
    "padding": "6px 8px", "borderRadius": "6px",
    "border": "1px solid var(--gray-6)", "background": "var(--color-panel-solid)",
    "color": "var(--gray-12)", "fontSize": "14px",
}

_TIPOS = ["", "FALTA", "PERMISO", "ATRASO", "DORMIDO", "MALA URBANIDAD", "FALTA DE RESPETO",
          "MAL UNIFORMADO", "ABANDONO DE PUESTO", "MAL SERVICIO DE GUARDIA",
          "INCUMPLIMIENTO DE POLITICAS", "MAL USO DEL EQUIPO DE DOTACION",
          "HORAS EXTRAS", "FRANCO TRABAJADO"]


def _fila(s: rx.Var) -> rx.Component:
    return rx.table.row(
        data_cell(rx.link(s["empleado_nombre"], on_click=lambda: _S.ver_detalle(s["id"]),
                          cursor="pointer")),
        data_cell(s["empleado_cedula"]),
        data_cell(s["tipo_sancion"]),
        data_cell(s["fecha"]),
        data_cell(badge_estado(s["status"])),
        data_cell(rx.text(s["observaciones"], size="1")),
    )


@rx.page(route="/sanciones/buscar", title="INSEVIG — Sanciones · Buscar",
         on_load=AuthState.cargar_sesion)
def buscar() -> rx.Component:
    return pagina(
        page_heading("Buscar sanciones", "Por nombre, cédula, código, agente, tipo u observación."),
        tabs_nav("/sanciones/buscar"),
        rx.vstack(
            card(
                rx.flex(
                    rx.input(value=_S.q_texto, on_change=_S.set_q_texto,
                             placeholder="Texto libre (mín. 2 caracteres)…", size="2", width="280px"),
                    rx.el.select(
                        *[rx.el.option(t or "Todos los tipos", value=t) for t in _TIPOS],
                        value=_S.q_tipo, on_change=_S.set_q_tipo, style=_SEL,
                    ),
                    rx.checkbox("Solo historial (procesadas)", checked=_S.q_solo_hist,
                                on_change=_S.toggle_q_solo_hist),
                    primary_button("Buscar", on_click=_S.buscar),
                    rx.cond(
                        (_S.q_resultados.length() > 0)
                        & AuthState.permisos_flat.contains("sanciones:exportar"),
                        rx.button("Exportar Excel", on_click=_S.exportar_busqueda, size="2",
                                  variant="soft"),
                    ),
                    gap="2", align="center", wrap="wrap",
                ),
                width="100%",
            ),
            rx.cond(
                _S.q_buscando,
                rx.center(rx.spinner(), padding="2rem"),
                rx.cond(
                    _S.q_resultados.length() > 0,
                    card(
                        rx.vstack(
                            rx.text(_S.q_resultados.length().to_string() + " resultados", size="1",
                                    color_scheme="gray"),
                            data_table(
                                ["Empleado", "Cédula", "Tipo", "Fecha", "Estado", "Observaciones"],
                                rx.foreach(_S.q_resultados, _fila),
                            ),
                            spacing="2", width="100%",
                        ),
                        width="100%",
                    ),
                ),
            ),
            dialog_detalle(),
            spacing="4", width="100%",
        ),
        requiere=("sanciones", "ver"),
    )
