from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading
from insevig_web.pages.empleados._editor_panel import editor_panel
from insevig_web.states.auth_state import AuthState
from insevig_web.states.empleados_state import EmpleadosState

_S = EmpleadosState

_SELECT = {
    "padding": "7px 8px", "borderRadius": "6px",
    "border": "1px solid var(--gray-6)", "background": "var(--color-panel-solid)",
    "color": "var(--gray-12)", "fontSize": "14px",
}


def _fila(e: rx.Var) -> rx.Component:
    seleccionado = _S.edit_empleado == e["empleado"]
    return rx.box(
        rx.flex(
            rx.center(
                rx.text(e["apellidos_nombres"].to_string()[0], weight="bold", size="3"),
                width="40px", height="40px", border_radius="9999px", flex_shrink="0",
                background=rx.cond(seleccionado, "rgba(255,255,255,.22)", "var(--blue-3)"),
                color=rx.cond(seleccionado, "white", "var(--blue-11)"),
            ),
            rx.vstack(
                rx.text(e["apellidos_nombres"], size="3", weight="bold"),
                rx.text(
                    f"#{e['empleado']}  ·  {e['cedula']}  ·  {e['estado']}",
                    size="1",
                    color=rx.cond(seleccionado, "rgba(255,255,255,.8)", "var(--gray-10)"),
                ),
                spacing="1", align="start", min_width="0", flex_grow="1",
            ),
            gap="3", align="center", width="100%",
        ),
        on_click=lambda: _S.abrir_editor(e["empleado"]),
        padding="12px 14px",
        border_radius="12px",
        cursor="pointer",
        color=rx.cond(seleccionado, "white", "inherit"),
        background=rx.cond(seleccionado, theme.PRIMARY, "transparent"),
        box_shadow=rx.cond(seleccionado, theme.SHADOW_SM, "none"),
        _hover={"background": rx.cond(seleccionado, theme.PRIMARY, "var(--gray-3)")},
        transition="background 120ms ease",
        width="100%",
    )


def _arrow(icono: str, delta: int, extremo: str = "") -> rx.Component:
    return rx.button(
        rx.icon(icono, size=15),
        on_click=lambda: _S.ir_a_indice(delta, extremo),
        variant="soft", size="1",
    )


def _lista() -> rx.Component:
    return card(
        rx.vstack(
            rx.flex(
                rx.input(
                    value=_S.grid_texto, on_change=_S.set_grid_texto,
                    placeholder="Buscar por código, cédula o nombre…",
                    size="2", flex_grow="1", min_width="0",
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
                rx.input(
                    value=_S.grid_filtro_vivo, on_change=_S.set_grid_filtro_vivo,
                    placeholder="Filtrar la lista…", size="2", flex_grow="1", min_width="0",
                ),
                gap="2", align="center", width="100%", wrap="wrap",
            ),
            rx.flex(
                rx.text(_S.grid_filtrado.length().to_string() + " empleados",
                        size="1", color_scheme="gray"),
                rx.spacer(),
                _arrow("chevrons-left", 0, "primero"),
                _arrow("chevron-left", -1),
                _arrow("chevron-right", 1),
                _arrow("chevrons-right", 0, "ultimo"),
                gap="1", align="center", width="100%",
            ),
            rx.divider(),
            rx.cond(
                _S.grid_cargando,
                rx.center(rx.spinner(), padding="2rem", width="100%"),
                rx.vstack(
                    rx.foreach(_S.grid_filtrado, _fila),
                    spacing="1", width="100%", max_height="60vh", overflow_y="auto",
                    padding_right="4px",
                ),
            ),
            spacing="3", width="100%", align="start",
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
            columns=rx.breakpoints(initial="1", lg="minmax(340px, 400px) minmax(0, 1fr)"),
            spacing="4", width="100%", align_items="start",
        ),
        requiere=("empleados", "ver"),
    )
