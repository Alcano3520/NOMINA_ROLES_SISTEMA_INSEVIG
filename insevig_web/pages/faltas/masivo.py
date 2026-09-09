"""/faltas/masivo — Registro Masivo (pestaña 1 del legado)."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, data_cell, data_table, page_heading, primary_button
from insevig_web.pages.faltas._comunes import buscador_empleado, log_consola, periodo_picker
from insevig_web.states.auth_state import AuthState
from insevig_web.states.faltas_state import FaltasState

_S = FaltasState


def _fila(f: rx.Var) -> rx.Component:
    return rx.table.row(
        data_cell(f["codigo"]),
        data_cell(f["nombre"]),
        data_cell(f["tipo"]),
        data_cell(f["cant"]),
        data_cell(f["fecha"]),
        data_cell(rx.text(f["observ"], size="1")),
        data_cell(
            rx.match(
                f["estado"],
                ("ok", rx.badge("válida", color_scheme="grass", size="1")),
                ("error", rx.badge(f["detalle"], color_scheme="red", size="1")),
                rx.badge("sin validar", color_scheme="gray", size="1"),
            )
        ),
    )


@rx.page(route="/faltas/masivo", title="INSEVIG — Faltas · Registro masivo",
         on_load=AuthState.cargar_sesion)
def masivo() -> rx.Component:
    return pagina(
        page_heading("Registro masivo de faltas / permisos",
                     "Pegá desde Excel: Código · Tipo (FALTA/PERMISO/SUSPENSIÓN) · Cantidad · "
                     "Fecha (DD/MM/AAAA) · Observación. La fecha del evento es cualquier día "
                     "del mes; el vencimiento se ajusta al último día del período."),
        rx.vstack(
            periodo_picker(),
            card(
                rx.vstack(
                    rx.text("Pegado (una fila por línea)", size="1", weight="bold", color_scheme="gray"),
                    rx.text_area(
                        value=_S.masivo_pegado, on_change=_S.set_masivo_pegado,
                        placeholder="1234\tFALTA\t1\t05/09/2026\tllegó tarde",
                        rows="5", width="100%", font_family="monospace",
                    ),
                    rx.flex(
                        rx.button("Cargar pegado", on_click=_S.masivo_cargar_pegado, size="2"),
                        rx.button("Validar", on_click=_S.masivo_validar, size="2", variant="soft",
                                  color_scheme="blue"),
                        rx.cond(
                            AuthState.permisos_flat.contains("faltas:crear"),
                            primary_button("Registrar todo", on_click=_S.masivo_registrar,
                                           loading=_S.masivo_procesando),
                        ),
                        rx.button("Limpiar", on_click=_S.masivo_limpiar, size="2", variant="ghost"),
                        rx.spacer(),
                        rx.text(_S.masivo_conteo, size="1", color_scheme="gray"),
                        gap="2", align="center", wrap="wrap", width="100%",
                    ),
                    spacing="3", width="100%",
                ),
                width="100%",
            ),
            buscador_empleado(_S.elegir_emp_masivo),
            rx.cond(
                _S.masivo_filas.length() > 0,
                card(
                    data_table(
                        ["Código", "Nombre", "Tipo", "Cant.", "Fecha", "Observación", "Estado"],
                        rx.foreach(_S.masivo_filas, _fila),
                    ),
                    width="100%",
                ),
            ),
            rx.cond(_S.masivo_log.length() > 0, card(log_consola(_S.masivo_log), width="100%")),
            spacing="4", width="100%",
        ),
        requiere=("faltas", "crear"),
    )
