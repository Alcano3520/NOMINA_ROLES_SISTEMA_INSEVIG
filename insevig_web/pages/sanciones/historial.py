"""/sanciones/historial — sanciones procesadas, paginado + exportar Excel.

Columnas iguales a `main.py` (HISTORIAL):
ID · Cód · Cédula · Nombre Empleado · Tipo · Fecha · Proc. Por · Fecha Proc. · Com. RRHH
"""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, data_cell, data_table, page_heading
from insevig_web.pages.sanciones._comunes import dialog_detalle, tabs_nav
from insevig_web.states.auth_state import AuthState
from insevig_web.states.sanciones_state import SancionesState

_S = SancionesState


def _fila(s: rx.Var) -> rx.Component:
    return rx.table.row(
        data_cell(rx.code(s["id_corto"], size="1")),
        data_cell(s["empleado_cod"].to_string()),
        data_cell(s["empleado_cedula"]),
        data_cell(rx.link(s["empleado_nombre"], on_click=lambda: _S.ver_detalle(s["id"]),
                          cursor="pointer")),
        data_cell(s["tipo_sancion"]),
        data_cell(s["fecha_fmt"]),
        data_cell(s["procesado_por"]),
        data_cell(s["fecha_procesamiento"]),
        data_cell(rx.text(s["comentarios_rrhh"], size="1")),
    )


@rx.page(route="/sanciones/historial", title="INSEVIG — Sanciones · Historial",
         on_load=[AuthState.cargar_sesion, SancionesState.hist_cargar])
def historial() -> rx.Component:
    return pagina(
        page_heading("Historial de sanciones procesadas", "Página de 50 registros, más recientes primero."),
        tabs_nav("/sanciones/historial"),
        rx.vstack(
            rx.flex(
                rx.button("‹ Anterior", on_click=_S.hist_anterior, size="2", variant="soft",
                          disabled=_S.hist_page <= 1),
                rx.text("Página " + _S.hist_page.to_string(), size="2"),
                rx.button("Siguiente ›", on_click=_S.hist_siguiente, size="2", variant="soft",
                          disabled=~_S.hist_has_more),
                rx.spacer(),
                rx.cond(
                    AuthState.permisos_flat.contains("sanciones:exportar"),
                    rx.button(rx.icon("file-down", size=14), "Exportar Excel",
                              on_click=_S.exportar_historial, size="2"),
                ),
                gap="2", align="center", wrap="wrap", width="100%",
            ),
            rx.cond(
                _S.hist.length() > 0,
                card(
                    data_table(
                        ["ID", "Cód", "Cédula", "Nombre Empleado", "Tipo", "Fecha",
                         "Proc. Por", "Fecha Proc.", "Com. RRHH"],
                        rx.foreach(_S.hist, _fila),
                    ),
                    width="100%",
                ),
                rx.callout("Sin registros en esta página.", size="1", color_scheme="gray"),
            ),
            dialog_detalle(),
            spacing="4", width="100%",
        ),
        requiere=("sanciones", "ver"),
    )
