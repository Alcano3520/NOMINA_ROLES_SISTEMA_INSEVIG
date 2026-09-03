from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.data_source_selector import data_source_selector
from insevig_web.components.employee_search import employee_search
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.observaciones_state import ObservacionesState


def _tabla(cols: list[str], filas: rx.Var, celdas) -> rx.Component:
    return scroll_x(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    *[
                        rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                        for c in cols
                    ]
                )
            ),
            rx.table.body(rx.foreach(filas, celdas)),
            variant="surface",
            size="1",
            width="100%",
        )
    )


@rx.page(
    route="/observaciones",
    title="INSEVIG — Observaciones",
    on_load=AuthState.cargar_sesion,
)
def index() -> rx.Component:
    return pagina(
        page_heading("Observaciones, Multas y Faltas", "Consulta por empleado."),
        rx.vstack(
            rx.hstack(rx.text("Fuente:", weight="bold", size="2"), data_source_selector("observaciones"), spacing="2"),
            employee_search(
                texto=ObservacionesState.texto_busqueda,
                resultados=ObservacionesState.resultados,
                on_set_texto=ObservacionesState.set_texto,
                on_buscar=ObservacionesState.buscar,
                on_seleccionar=ObservacionesState.seleccionar,
            ),
            rx.cond(
                ObservacionesState.empleado_sel != "",
                card(
                    rx.vstack(
                        rx.heading(
                            f"{ObservacionesState.empleado_sel} — {ObservacionesState.nombre_sel}", size="4"
                        ),
                        rx.cond(
                            ObservacionesState.cargando,
                            rx.spinner(),
                            rx.tabs.root(
                                rx.tabs.list(
                                    rx.tabs.trigger("Observaciones", value="obs"),
                                    rx.tabs.trigger("Multas", value="mul"),
                                    rx.tabs.trigger("Faltas", value="fal"),
                                ),
                                rx.tabs.content(
                                    _tabla(
                                        ["Fecha", "Texto"],
                                        ObservacionesState.observaciones,
                                        lambda o: rx.foreach(
                                            o["textos"],
                                            lambda t: rx.table.row(
                                                rx.table.cell(o["fecha_ven"]), rx.table.cell(t)
                                            ),
                                        ),
                                    ),
                                    value="obs",
                                ),
                                rx.tabs.content(
                                    _tabla(
                                        ["Fecha", "Valor", "Concepto", "Observación"],
                                        ObservacionesState.multas,
                                        lambda m: rx.table.row(
                                            rx.table.cell(m["fecha"]),
                                            rx.table.cell(m["valor"].to_string()),
                                            rx.table.cell(m["concepto"]),
                                            rx.table.cell(m["observ"]),
                                        ),
                                    ),
                                    value="mul",
                                ),
                                rx.tabs.content(
                                    rx.vstack(
                                        rx.text("Período actual", weight="bold", size="2"),
                                        _tabla(
                                            ["Período", "Ausencias", "F. Just.", "F. Injust.", "Total"],
                                            ObservacionesState.faltas,
                                            lambda f: rx.table.row(
                                                rx.table.cell(f["periodo"]),
                                                rx.table.cell(f["ausencias"].to_string()),
                                                rx.table.cell(f["faltas_justificadas"].to_string()),
                                                rx.table.cell(f["faltas_injustificadas"].to_string()),
                                                rx.table.cell(f["total"].to_string()),
                                            ),
                                        ),
                                        rx.text("Histórico", weight="bold", size="2", margin_top="0.5rem"),
                                        _tabla(
                                            ["Período", "Ausencias", "F. Just.", "F. Injust.", "Total"],
                                            ObservacionesState.faltas_hist,
                                            lambda f: rx.table.row(
                                                rx.table.cell(f["periodo"]),
                                                rx.table.cell(f["ausencias"].to_string()),
                                                rx.table.cell(f["faltas_justificadas"].to_string()),
                                                rx.table.cell(f["faltas_injustificadas"].to_string()),
                                                rx.table.cell(f["total"].to_string()),
                                            ),
                                        ),
                                        spacing="2",
                                        width="100%",
                                    ),
                                    value="fal",
                                ),
                                default_value="obs",
                            ),
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    width="100%",
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("observaciones", "ver"),
    )
