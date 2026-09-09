from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, data_cell, data_table, page_heading
from insevig_web.pages.empleados._editor_panel import editor_panel
from insevig_web.states.auth_state import AuthState
from insevig_web.states.empleados_state import EmpleadosState

_S = EmpleadosState

_SELECT = {
    "padding": "6px 8px", "borderRadius": "6px",
    "border": "1px solid var(--gray-6)", "background": "var(--color-panel-solid)",
    "color": "var(--gray-12)", "fontSize": "13px",
}


def _fila(e: rx.Var) -> rx.Component:
    seleccionado = _S.edit_empleado == e["empleado"]
    return rx.table.row(
        data_cell(rx.text(e["empleado"], size="1", weight="bold", color_scheme="gray"),
                  style={"width": "1%", "whiteSpace": "nowrap"}),
        data_cell(rx.text(e["apellidos_nombres"], weight="medium",
                          style={"whiteSpace": "nowrap", "overflow": "hidden",
                                 "textOverflow": "ellipsis", "maxWidth": "12rem"})),
        data_cell(e["cedula"], style={"width": "1%", "whiteSpace": "nowrap"}),
        data_cell(rx.badge(e["estado"], size="1",
                           color_scheme=rx.cond(e["estado"] == "ACT", "green", "gray")),
                  style={"width": "1%"}),
        on_click=lambda: _S.abrir_editor(e["empleado"]),
        style={"cursor": "pointer"},
        background=rx.cond(seleccionado, "var(--blue-3)", "transparent"),
        _hover={"background": rx.cond(seleccionado, "var(--blue-3)", "var(--gray-2)")},
    )


def _arrow(icono: str, delta: int, extremo: str = "") -> rx.Component:
    return rx.button(
        rx.icon(icono, size=14),
        on_click=lambda: _S.ir_a_indice(delta, extremo),
        variant="soft", size="1",
    )


def _lista() -> rx.Component:
    return card(
        rx.vstack(
            rx.flex(
                rx.debounce_input(
                    rx.input(
                        value=_S.grid_texto, on_change=_S.set_grid_texto,
                        placeholder="Buscar por código, cédula o nombre…",
                        size="2", flex_grow="1", min_width="0",
                    ),
                    debounce_timeout=350,
                ),
                rx.button(rx.icon("search", size=15), on_click=_S.buscar_grid, size="2"),
                rx.cond(
                    AuthState.permisos_flat.contains("empleados:crear"),
                    rx.button(rx.icon("plus", size=15), "Nuevo", on_click=_S.nuevo,
                              size="2", color_scheme="blue", flex_shrink="0"),
                ),
                gap="2", align="center", width="100%", wrap="wrap",
            ),
            rx.flex(
                rx.el.select(
                    rx.el.option("Activos", value="ACTIVOS"),
                    rx.el.option("Inactivos", value="INACTIVOS"),
                    rx.el.option("Todos", value="TODOS"),
                    value=_S.grid_estado, on_change=_S.set_grid_estado, style=_SELECT,
                ),
                rx.debounce_input(
                    rx.input(
                        value=_S.grid_filtro_vivo, on_change=_S.set_grid_filtro_vivo,
                        placeholder="Filtrar la lista…", size="2", flex_grow="1", min_width="0",
                    ),
                    debounce_timeout=250,
                ),
                rx.text(_S.grid_conteo, size="1", color_scheme="gray", white_space="nowrap"),
                _arrow("chevrons-left", 0, "primero"),
                _arrow("chevron-left", -1),
                _arrow("chevron-right", 1),
                _arrow("chevrons-right", 0, "ultimo"),
                gap="2", align="center", width="100%", wrap="wrap",
            ),
            rx.cond(
                _S.grid_cargando,
                rx.center(rx.spinner(), padding="1.5rem", width="100%"),
                rx.box(
                    data_table(
                        ["Código", "Empleado", "Cédula", "Estado"],
                        rx.foreach(_S.grid_filtrado, _fila),
                    ),
                    max_height="62vh", overflow_y="auto", width="100%",
                ),
            ),
            spacing="2", width="100%", align="start",
        ),
        width="100%",
    )


@rx.page(
    route="/empleados/buscar",
    title="INSEVIG — Gestión de empleados",
    on_load=[AuthState.cargar_sesion, EmpleadosState.cargar_lista_inicial],
)
def buscar() -> rx.Component:
    return pagina(
        page_heading("Gestión de empleados", "Elegí un empleado para ver y editar su ficha."),
        rx.grid(
            _lista(),
            card(editor_panel(), width="100%"),
            columns=rx.breakpoints(initial="1", lg="minmax(400px, 520px) minmax(0, 1fr)"),
            spacing="3", width="100%", align_items="start",
        ),
        requiere=("empleados", "ver"),
    )
