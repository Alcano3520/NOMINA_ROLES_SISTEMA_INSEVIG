"""/faltas/restas — Cargador de Restas de Horas (pestaña 4 del legado)."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, data_cell, data_table, page_heading, primary_button
from insevig_web.pages.faltas._comunes import periodo_picker
from insevig_web.states.auth_state import AuthState
from insevig_web.states.faltas_state import FaltasState

_S = FaltasState

_COLOR_ESTADO = {
    "OK": "grass", "REVISION": "amber", "SIN_HORAS": "gray", "ERROR": "red",
    "ERROR_CEDULA": "red",
}


def _fila(r: rx.Var) -> rx.Component:
    return rx.table.row(
        data_cell(r["EMPLEADO"]),
        data_cell(r["CEDULA"]),
        data_cell(rx.text(f"{r['APELLIDOS']} {r['NOMBRES']}", size="1")),
        data_cell(r["NUM_FALTAS"].to_string()),
        data_cell(r["HOR50_ACTUAL"].to_string()),
        data_cell(r["HOR50_NUEVO"].to_string()),
        data_cell(r["HOR100_ACTUAL"].to_string()),
        data_cell(r["HOR100_NUEVO"].to_string()),
        data_cell(
            rx.badge(
                r["ESTADO"],
                color_scheme=rx.match(
                    r["ESTADO"], *[(k, v) for k, v in _COLOR_ESTADO.items()], "gray"
                ),
                size="1",
            )
        ),
    )


@rx.page(route="/faltas/restas", title="INSEVIG — Faltas · Cargador de restas de horas",
         on_load=AuthState.cargar_sesion)
def restas() -> rx.Component:
    return pagina(
        page_heading("Cargador de restas de horas",
                     "Quien acumuló más de 3 faltas en el período pierde horas extra "
                     "(HOR50 → HOR100, factor 0.75). Subí FALTAS_PARA_RESTA.xlsx, revisá "
                     "la previsualización y ejecutá."),
        rx.vstack(
            periodo_picker(),
            card(
                rx.vstack(
                    rx.upload(
                        rx.vstack(
                            rx.icon("upload", size=26),
                            rx.text("Arrastrá o elegí el .xlsx (columnas Cédula, Fecha)"),
                        ),
                        id="faltas_restas",
                        accept={".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                        max_files=1,
                        border="1px dashed var(--gray-6)", padding="1.5rem", width="100%",
                    ),
                    rx.flex(
                        rx.button(
                            "Cargar y calcular",
                            on_click=_S.restas_subir(rx.upload_files(upload_id="faltas_restas")),
                            size="2", loading=_S.restas_cargando,
                        ),
                        rx.cond(
                            (_S.restas_filas.length() > 0) & ~_S.restas_ejecutado
                            & AuthState.permisos_flat.contains("faltas:cargar_masivo"),
                            primary_button("Ejecutar restas", on_click=_S.restas_ejecutar),
                        ),
                        rx.button("Limpiar", on_click=_S.restas_limpiar, size="2", variant="ghost"),
                        rx.spacer(),
                        rx.text(_S.restas_msg, size="1", color_scheme="gray"),
                        gap="2", align="center", wrap="wrap", width="100%",
                    ),
                    spacing="3", width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                _S.restas_filas.length() > 0,
                card(
                    data_table(
                        ["Código", "Cédula", "Nombre", "Faltas", "HOR50 ant.", "HOR50 nuevo",
                         "HOR100 ant.", "HOR100 nuevo", "Estado"],
                        rx.foreach(_S.restas_filas, _fila),
                    ),
                    width="100%",
                ),
            ),
            spacing="4", width="100%",
        ),
        requiere=("faltas", "cargar_masivo"),
    )
