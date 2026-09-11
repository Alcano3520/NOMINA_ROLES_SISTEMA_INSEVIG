from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, data_cell, data_table, empty_state, page_heading, primary_button
from insevig_web.pages.empleados._comunes import badge_estado, select_estado_lista
from insevig_web.pages.empleados._editor_panel import editor_panel
from insevig_web.states.auth_state import AuthState
from insevig_web.states.empleados_state import EmpleadosState

_S = EmpleadosState


def _cel(*children, sel: rx.Var, **props) -> rx.Component:
    """Celda de la fila con el fondo de selección — puesto en la celda (no en
    el `<tr>`) para que gane sobre la regla global `.rt-TableRow:hover`."""
    return data_cell(
        *children,
        background=rx.cond(sel, "var(--blue-3)", "transparent"),
        **props,
    )


def _fila(e: rx.Var) -> rx.Component:
    seleccionado = _S.edit_empleado == e["empleado"]
    return rx.table.row(
        _cel(
            rx.text(e["empleado"], size="1", weight="bold", color_scheme="gray"),
            sel=seleccionado,
            style={"width": "1%", "whiteSpace": "nowrap"},
            box_shadow=rx.cond(seleccionado, "inset 3px 0 0 var(--blue-9)", "none"),
        ),
        _cel(
            rx.vstack(
                rx.text(e["apellidos_nombres"], weight="medium", size="2",
                        style={"whiteSpace": "nowrap", "overflow": "hidden",
                               "textOverflow": "ellipsis", "maxWidth": "100%"}),
                rx.text(e["cedula"], size="1", color_scheme="gray"),
                spacing="0", width="100%", align="start",
            ),
            sel=seleccionado,
        ),
        _cel(badge_estado(e["estado"], size="1"), sel=seleccionado, style={"width": "1%"}),
        on_click=lambda: _S.abrir_editor(e["empleado"]),
        style={"cursor": "pointer"},
    )


def _arrow(icono: str, delta: int, extremo: str = "") -> rx.Component:
    return rx.button(
        rx.icon(icono, size=14),
        on_click=lambda: _S.ir_a_indice(delta, extremo),
        variant="ghost", size="1",
    )


def _paginador() -> rx.Component:
    return rx.hstack(
        _arrow("chevrons-left", 0, "primero"),
        _arrow("chevron-left", -1),
        _arrow("chevron-right", 1),
        _arrow("chevrons-right", 0, "ultimo"),
        spacing="1", align="center",
        border="1px solid var(--gray-5)", border_radius="6px", padding="2px",
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
                rx.button(rx.icon("search", size=15), on_click=_S.buscar_grid, size="2", variant="soft"),
                rx.cond(
                    AuthState.permisos_flat.contains("empleados:crear"),
                    primary_button(rx.icon("plus", size=15), "Nuevo", on_click=_S.nuevo,
                                  size="2", flex_shrink="0"),
                ),
                gap="2", align="center", width="100%", wrap="wrap",
            ),
            rx.flex(
                select_estado_lista(_S.grid_estado, _S.set_grid_estado, width="130px"),
                rx.debounce_input(
                    rx.input(
                        value=_S.grid_filtro_vivo, on_change=_S.set_grid_filtro_vivo,
                        placeholder="Filtrar la lista…", size="2", flex_grow="1", min_width="0",
                    ),
                    debounce_timeout=250,
                ),
                rx.badge(_S.grid_conteo, variant="surface", size="2", white_space="nowrap"),
                _paginador(),
                gap="2", align="center", width="100%", wrap="wrap",
            ),
            rx.cond(
                _S.grid_cargando,
                rx.center(rx.spinner(), padding="1.5rem", width="100%"),
                rx.cond(
                    _S.grid_filtrado.length() > 0,
                    data_table(
                        ["Código", "Empleado", "Estado"],
                        rx.foreach(_S.grid_filtrado, _fila),
                        max_height="62vh",
                    ),
                    empty_state("users", "Sin resultados",
                               "Probá con otro texto o cambiá el filtro de estado."),
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
