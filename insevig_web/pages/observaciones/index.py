from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.employee_search import employee_search
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.observaciones_state import ObservacionesState


def _nueva_observacion() -> rx.Component:
    return rx.cond(
        AuthState.permisos_flat.contains("observaciones:crear"),
        card(
            rx.vstack(
                rx.heading("Añadir observación", size="3"),
                rx.hstack(
                    rx.input(
                        value=ObservacionesState.nueva_periodo,
                        on_change=ObservacionesState.set_nueva_periodo,
                        placeholder="AAAA-MM (por defecto: mes actual)",
                        width="240px",
                    ),
                    spacing="2",
                ),
                rx.text_area(
                    value=ObservacionesState.nueva_texto,
                    on_change=ObservacionesState.set_nueva_texto,
                    placeholder="Texto de la observación (se guarda en el primer slot libre del mes)",
                    rows="3",
                    width="100%",
                ),
                rx.hstack(
                    primary_button("Guardar observación", on_click=ObservacionesState.guardar_nueva),
                    rx.cond(
                        ObservacionesState.nueva_msg != "",
                        rx.badge(ObservacionesState.nueva_msg),
                    ),
                    spacing="2",
                ),
                spacing="2",
                width="100%",
            ),
            width="100%",
        ),
    )


def _dato(etq: str, valor: rx.Var) -> rx.Component:
    return rx.vstack(
        rx.text(etq, size="1", weight="bold", color_scheme="gray"),
        rx.text(valor, size="1"),
        spacing="0",
    )


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
                        rx.hstack(
                            rx.heading(
                                f"{ObservacionesState.empleado_sel} — {ObservacionesState.nombre_sel}", size="4"
                            ),
                            rx.button(
                                "Reporte imprimible",
                                on_click=ObservacionesState.descargar_reporte,
                                variant="soft",
                                size="1",
                            ),
                            spacing="3",
                            align="center",
                            wrap="wrap",
                        ),
                        rx.cond(
                            ObservacionesState.datos_emp.contains("cedula"),
                            rx.box(
                                rx.grid(
                                    _dato("Cédula", ObservacionesState.datos_emp["cedula"]),
                                    _dato("Cargo", ObservacionesState.datos_emp["cargo"]),
                                    _dato("Departamento", ObservacionesState.datos_emp["depto"]),
                                    _dato("Sección", ObservacionesState.datos_emp["seccion"]),
                                    _dato("Ingreso", ObservacionesState.datos_emp["fecha_ing"]),
                                    _dato("Salida", ObservacionesState.datos_emp["fecha_sal"]),
                                    _dato("Estado", ObservacionesState.datos_emp["estado"]),
                                    _dato("Teléfono", ObservacionesState.datos_emp["telefono"]),
                                    columns=rx.breakpoints(initial="2", sm="4"),
                                    spacing="2",
                                    width="100%",
                                ),
                                border="1px solid var(--gray-5)",
                                border_radius="8px",
                                padding="10px 12px",
                                width="100%",
                            ),
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
                                        lambda o: rx.table.row(
                                            rx.table.cell(o["fecha_ven"]), rx.table.cell(o["texto"])
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
            rx.cond(ObservacionesState.empleado_sel != "", _nueva_observacion()),
            spacing="4",
            width="100%",
        ),
        requiere=("observaciones", "ver"),
    )
