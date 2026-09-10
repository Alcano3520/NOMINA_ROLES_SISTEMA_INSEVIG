"""/sanciones/bandeja — pendientes de aprobación + pendientes de procesamiento.

Columnas iguales a `main.py` ContentArea:
- APROBACIONES: ID · Cód · Cédula · Nombre Empleado · Tipo · Fecha · Hora · Estado · Enviado · Agente
- por procesar:  ID · Cód · Cédula · Nombre Empleado · Tipo · Fecha · Supervisor/Creador · Observaciones
"""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, data_cell, data_table, page_heading, primary_button
from insevig_web.pages.sanciones._comunes import badge_estado, dialog_detalle, tabs_nav
from insevig_web.states.auth_state import AuthState
from insevig_web.states.sanciones_state import SancionesState

_S = SancionesState

_COLS_APROB = ["", "ID", "Cód", "Cédula", "Nombre Empleado", "Tipo", "Fecha", "Hora",
               "Estado", "Enviado", "Agente"]
_COLS_PROC = ["", "ID", "Cód", "Cédula", "Nombre Empleado", "Tipo", "Fecha",
              "Supervisor/Creador", "Observaciones"]


def _chk(s: rx.Var) -> rx.Component:
    return data_cell(rx.checkbox(
        checked=_S.sel.contains(s["id"]), on_change=lambda _v: _S.toggle_sel(s["id"]),
    ))


def _nombre(s: rx.Var) -> rx.Component:
    return data_cell(rx.link(s["empleado_nombre"], on_click=lambda: _S.ver_detalle(s["id"]),
                             cursor="pointer"))


def _fila_aprob(s: rx.Var) -> rx.Component:
    return rx.table.row(
        _chk(s),
        data_cell(rx.code(s["id_corto"], size="1")),
        data_cell(s["empleado_cod"].to_string()),
        data_cell(s["empleado_cedula"]),
        _nombre(s),
        data_cell(s["tipo_sancion"]),
        data_cell(s["fecha_fmt"]),
        data_cell(s["hora"]),
        data_cell(badge_estado(s["status"])),
        data_cell(s["enviado_fmt"]),
        data_cell(rx.text(s["agente"], size="1")),
    )


def _fila_proc(s: rx.Var) -> rx.Component:
    return rx.table.row(
        _chk(s),
        data_cell(rx.code(s["id_corto"], size="1")),
        data_cell(s["empleado_cod"].to_string()),
        data_cell(s["empleado_cedula"]),
        _nombre(s),
        data_cell(s["tipo_sancion"]),
        data_cell(s["fecha_fmt"]),
        data_cell(rx.text(s["supervisor_txt"], size="1")),
        data_cell(rx.text(s["observaciones"], size="1")),
    )


def _barra_acciones() -> rx.Component:
    return rx.cond(
        AuthState.permisos_flat.contains("sanciones:editar"),
        rx.match(
            _S.tab,
            ("aprobacion", rx.flex(
                rx.input(value=_S.motivo_rechazo, on_change=_S.set_motivo_rechazo,
                         placeholder="Motivo de rechazo (mín. 15 caracteres)…", size="2",
                         width="320px"),
                primary_button("Aprobar seleccionadas", on_click=_S.aprobar_sel),
                rx.button("Rechazar seleccionadas", on_click=_S.rechazar_sel, size="2",
                          variant="soft", color_scheme="red"),
                gap="2", align="center", wrap="wrap",
            )),
            rx.flex(primary_button("Procesar seleccionadas", on_click=_S.procesar_sel),
                    gap="2", align="center", wrap="wrap"),
        ),
    )


@rx.page(route="/sanciones/bandeja", title="INSEVIG — Sanciones · Bandeja",
         on_load=[AuthState.cargar_sesion, SancionesState.cargar_bandeja])
def bandeja() -> rx.Component:
    return pagina(
        page_heading("Bandeja de sanciones",
                     "Reportes de supervisores y coordinadores: pendientes de aprobación "
                     "(gerencia) y de procesamiento (RRHH)."),
        tabs_nav("/sanciones/bandeja"),
        rx.vstack(
            rx.flex(
                rx.segmented_control.root(
                    rx.segmented_control.item(
                        "Por aprobar (" + _S.conteo_aprob.to_string() + ")", value="aprobacion"),
                    rx.segmented_control.item(
                        "Por procesar (" + _S.conteo_proceso.to_string() + ")", value="proceso"),
                    value=_S.tab, on_change=_S.set_tab,
                ),
                rx.spacer(),
                rx.button("Recargar", on_click=_S.cargar_bandeja, size="2", variant="soft",
                          loading=_S.cargando),
                align="center", wrap="wrap", width="100%",
            ),
            _barra_acciones(),
            rx.cond(_S.msg != "", rx.callout(_S.msg, size="1")),
            rx.cond(
                _S.bandeja_actual.length() > 0,
                card(
                    rx.vstack(
                        rx.button("Seleccionar todo", on_click=_S.sel_todos, size="1", variant="ghost"),
                        rx.cond(
                            _S.tab == "aprobacion",
                            data_table(_COLS_APROB, rx.foreach(_S.bandeja_actual, _fila_aprob)),
                            data_table(_COLS_PROC, rx.foreach(_S.bandeja_actual, _fila_proc)),
                        ),
                        spacing="2", width="100%",
                    ),
                    width="100%",
                ),
                rx.callout("Sin sanciones en esta bandeja.", size="1", color_scheme="gray"),
            ),
            dialog_detalle(),
            spacing="4", width="100%",
        ),
        requiere=("sanciones", "ver"),
    )
