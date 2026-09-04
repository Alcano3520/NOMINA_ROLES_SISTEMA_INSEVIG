from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.employee_search import employee_search
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, scroll_x, stat_card
from insevig_web.states.auth_state import AuthState
from insevig_web.states.empleados_state import EmpleadosState


def _historial_multi() -> rx.Component:
    _S = EmpleadosState
    return card(
        rx.vstack(
            rx.hstack(
                rx.heading("Historial por período", size="3"),
                rx.spacer(),
                rx.button("Exportar CSV", on_click=_S.exportar_historial, variant="soft", size="1"),
                width="100%",
            ),
            rx.cond(
                _S.hist_cargando,
                rx.center(rx.spinner(), padding="1rem"),
                scroll_x(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(*[
                                rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                                for c in ("Período", "Días", "Ingresos", "Egresos", "Neto", "")
                            ])
                        ),
                        rx.table.body(
                            rx.foreach(
                                _S.hist_periodos,
                                lambda f: rx.table.row(
                                    rx.table.cell(f["periodo"]),
                                    rx.table.cell(f["dias"].to_string()),
                                    rx.table.cell(f["ingresos"].to_string()),
                                    rx.table.cell(f["egresos"].to_string()),
                                    rx.table.cell(f["neto"].to_string()),
                                    rx.table.cell(
                                        rx.button("Conceptos", size="1", variant="soft",
                                                  on_click=lambda: _S.ver_detalle_periodo(f["periodo"]))
                                    ),
                                ),
                            )
                        ),
                        variant="surface",
                        size="1",
                        width="100%",
                    )
                ),
            ),
            rx.cond(
                _S.hist_detalle.length() > 0,
                rx.vstack(
                    rx.heading("Conceptos de " + _S.hist_detalle_periodo, size="2"),
                    scroll_x(
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Concepto", style={"background": theme.PRIMARY, "color": "white"}),
                                    rx.table.column_header_cell("Valor", style={"background": theme.PRIMARY, "color": "white"}),
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    _S.hist_detalle,
                                    lambda c: rx.table.row(
                                        rx.table.cell(c["concepto"]),
                                        rx.table.cell(c["valor"].to_string()),
                                    ),
                                )
                            ),
                            variant="surface",
                            size="1",
                            width="100%",
                        )
                    ),
                    spacing="2",
                    width="100%",
                ),
            ),
            spacing="2",
            width="100%",
        ),
        width="100%",
    )


@rx.page(
    route="/empleados/historial",
    title="INSEVIG — Historial de nómina",
    on_load=[AuthState.cargar_sesion, EmpleadosState.on_load],
)
def historial() -> rx.Component:
    return pagina(
        page_heading("Historial de nómina del empleado", "Consolidado de un período."),
        rx.vstack(
            employee_search(
                texto=EmpleadosState.texto_busqueda,
                resultados=EmpleadosState.resultados,
                on_set_texto=EmpleadosState.set_texto,
                on_buscar=EmpleadosState.buscar,
                on_seleccionar=EmpleadosState.seleccionar,
            ),
            rx.cond(
                EmpleadosState.empleado_sel != "",
                card(
                    rx.vstack(
                        rx.hstack(
                            rx.heading(
                                f"{EmpleadosState.empleado_sel} — {EmpleadosState.nombre_sel}", size="4"
                            ),
                            rx.input(
                                value=EmpleadosState.periodo,
                                on_change=EmpleadosState.set_periodo,
                                placeholder="2026-06",
                                width="120px",
                            ),
                            rx.button("Ver período", on_click=EmpleadosState.recargar),
                            rx.text("Últimos", size="1"),
                            rx.input(
                                value=EmpleadosState.hist_n,
                                on_change=EmpleadosState.set_hist_n,
                                type="number",
                                width="64px",
                            ),
                            rx.button(
                                "meses", on_click=EmpleadosState.cargar_varios_periodos, variant="soft"
                            ),
                            spacing="3",
                            align="center",
                            wrap="wrap",
                        ),
                        rx.cond(
                            EmpleadosState.hist_periodos.length() > 0,
                            _historial_multi(),
                        ),
                        rx.cond(
                            EmpleadosState.cargando,
                            rx.spinner(),
                            rx.cond(
                                EmpleadosState.sin_datos,
                                rx.callout("Sin datos para ese período.", color_scheme="amber", size="1"),
                                rx.vstack(
                                    rx.grid(
                                        stat_card("Ingresos", "", EmpleadosState.fila["ingresos"].to_string(), "trending-up"),
                                        stat_card("Egresos", "", EmpleadosState.fila["egresos"].to_string(), "trending-down"),
                                        stat_card("Neto", "", EmpleadosState.fila["recibir"].to_string(), "wallet"),
                                        columns=rx.breakpoints(initial="1", sm="3"),
                                        spacing="3",
                                        width="100%",
                                    ),
                                    scroll_x(
                                        rx.table.root(
                                            rx.table.header(
                                                rx.table.row(
                                                    rx.table.column_header_cell(
                                                        "Concepto", style={"background": theme.PRIMARY, "color": "white"}
                                                    ),
                                                    rx.table.column_header_cell(
                                                        "Valor", style={"background": theme.PRIMARY, "color": "white"}
                                                    ),
                                                )
                                            ),
                                            rx.table.body(
                                                rx.foreach(
                                                    EmpleadosState.conceptos,
                                                    lambda c: rx.table.row(
                                                        rx.table.cell(c["concepto"]),
                                                        rx.table.cell(c["valor"].to_string()),
                                                    ),
                                                )
                                            ),
                                            variant="surface",
                                            size="1",
                                            width="100%",
                                        )
                                    ),
                                    spacing="3",
                                    width="100%",
                                ),
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
        requiere=("empleados", "ver"),
    )
