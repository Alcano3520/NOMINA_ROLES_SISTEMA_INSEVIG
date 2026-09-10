"""/faltas/periodo — Ver / Editar Período (pestaña 3 del legado)."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, data_cell, data_table, page_heading, primary_button
from insevig_web.pages.faltas._comunes import periodo_picker
from insevig_web.states.auth_state import AuthState
from insevig_web.states.faltas_state import FaltasState

_S = FaltasState


def _fila(f: rx.Var) -> rx.Component:
    return rx.table.row(
        data_cell(f["empleado"]),
        data_cell(f["nombre"]),
        data_cell(f["cedula"]),
        data_cell(f["totaus"].to_string()),
        data_cell((f["totaus"].to(float) // 8).to_string()),
        data_cell(rx.text(f["observ"], size="1")),
        data_cell(f["fecha_ven"]),
        data_cell(
            rx.cond(
                _S.per_editable,
                rx.hstack(
                    rx.button("Editar", size="1", variant="soft",
                              on_click=lambda: _S.abrir_edicion(f)),
                    rx.button("Eliminar", size="1", variant="soft", color_scheme="red",
                              on_click=lambda: _S.eliminar_fila_periodo(f)),
                    spacing="1",
                ),
                rx.text("—", size="1", color_scheme="gray"),
            )
        ),
    )


def _dialog_editar() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Editar registro"),
            rx.dialog.description(
                _S.edit_empleado + " · vence " + _S.edit_fecha_ven, size="1",
            ),
            rx.vstack(
                rx.text("TOTAUS (horas acumuladas)", size="1", weight="bold", color_scheme="gray"),
                rx.input(type="number", value=_S.edit_totaus, on_change=_S.set_edit_totaus),
                rx.text("Observación", size="1", weight="bold", color_scheme="gray"),
                rx.text_area(value=_S.edit_observ, on_change=_S.set_edit_observ, rows="3"),
                rx.flex(
                    rx.button("Cancelar", on_click=_S.cerrar_edicion, variant="soft"),
                    primary_button("Guardar cambios", on_click=_S.guardar_edicion),
                    gap="2", justify="end",
                ),
                spacing="2", margin_top="0.5rem",
            ),
            max_width="480px",
        ),
        open=_S.edit_abierto,
    )


@rx.page(route="/faltas/periodo", title="INSEVIG — Faltas · Ver / editar período",
         on_load=[AuthState.cargar_sesion, FaltasState.per_cargar])
def periodo() -> rx.Component:
    return pagina(
        page_heading("Ver / editar período de faltas",
                     "Período actual (RPHORTOT, editable) o meses cerrados (RPHORHIS, solo lectura)."),
        rx.vstack(
            periodo_picker(),
            card(
                rx.flex(
                    rx.checkbox(
                        "Meses cerrados (solo lectura)",
                        checked=_S.per_historicas, on_change=_S.toggle_historicas,
                    ),
                    rx.button("Cargar", on_click=_S.per_cargar, size="2", loading=_S.per_cargando),
                    rx.cond(
                        _S.per_filas.length() > 0,
                        rx.button("Exportar Excel", on_click=_S.per_exportar, size="2", variant="soft"),
                    ),
                    rx.spacer(),
                    rx.text(_S.per_msg, size="1", color_scheme="gray"),
                    gap="3", align="center", wrap="wrap", width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                _S.per_filas.length() > 0,
                card(
                    data_table(
                        ["Código", "Nombre", "Cédula", "TOTAUS", "Días", "Observación", "Vence", ""],
                        rx.foreach(_S.per_filas, _fila),
                    ),
                    width="100%",
                ),
                rx.cond(
                    ~_S.per_cargando,
                    rx.callout("Sin registros en el período seleccionado.", size="1",
                               color_scheme="gray"),
                ),
            ),
            _dialog_editar(),
            spacing="4", width="100%",
        ),
        requiere=("faltas", "ver"),
    )
