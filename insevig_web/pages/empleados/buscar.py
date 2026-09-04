from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading
from insevig_web.pages.empleados._editor_panel import editor_panel
from insevig_web.states.auth_state import AuthState
from insevig_web.states.empleados_state import EmpleadosState

_S = EmpleadosState


def _fila(e: rx.Var) -> rx.Component:
    seleccionado = _S.edit_empleado == e["empleado"]
    return rx.box(
        rx.hstack(
            rx.text(e["empleado"], size="1", weight="bold", width="48px"),
            rx.vstack(
                rx.text(e["apellidos_nombres"], size="1", weight="medium"),
                rx.text(
                    f"{e['cedula']}  ·  {e['cargo']}  ·  {e['estado']}",
                    size="1",
                    color_scheme="gray",
                ),
                spacing="0",
                align="start",
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        on_click=lambda: _S.abrir_editor(e["empleado"]),
        padding="6px 8px",
        border_radius="6px",
        cursor="pointer",
        background=rx.cond(seleccionado, "var(--accent-4)", "transparent"),
        _hover={"background": "var(--accent-3)"},
        width="100%",
    )


def _arrow(txt: str, delta: int, extremo: str = "") -> rx.Component:
    return rx.button(
        txt,
        on_click=lambda: _S.ir_a_indice(delta, extremo),
        variant="soft",
        size="1",
    )


def _lista() -> rx.Component:
    return card(
        rx.vstack(
            rx.hstack(
                rx.input(
                    value=_S.grid_texto,
                    on_change=_S.set_grid_texto,
                    placeholder="Buscar por código, cédula o nombre…",
                    size="2",
                    width="100%",
                ),
                rx.button("Buscar", on_click=_S.buscar_grid, size="2"),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                rx.text("Mostrar:", size="1", weight="bold"),
                rx.el.select(
                    rx.el.option("Activos", value="ACTIVOS"),
                    rx.el.option("Inactivos", value="INACTIVOS"),
                    rx.el.option("Todos", value="TODOS"),
                    value=_S.grid_estado,
                    on_change=_S.set_grid_estado,
                    style={"padding": "4px 6px", "borderRadius": "6px",
                           "border": "1px solid var(--gray-6)", "background": "#fff"},
                ),
                rx.spacer(),
                rx.cond(
                    AuthState.permisos_flat.contains("empleados:crear"),
                    rx.button("Nuevo empleado", on_click=_S.nuevo, size="2", color_scheme="blue"),
                ),
                width="100%",
                align="center",
                wrap="wrap",
            ),
            rx.input(
                value=_S.grid_filtro_vivo,
                on_change=_S.set_grid_filtro_vivo,
                placeholder="Filtrar la lista…",
                size="1",
                width="100%",
            ),
            rx.hstack(
                rx.text(
                    _S.grid_filtrado.length().to_string() + " empleados",
                    size="1",
                    color_scheme="gray",
                ),
                rx.spacer(),
                _arrow("◀◀", 0, "primero"),
                _arrow("◀", -1),
                _arrow("▶", 1),
                _arrow("▶▶", 0, "ultimo"),
                width="100%",
                align="center",
            ),
            rx.cond(
                _S.grid_cargando,
                rx.center(rx.spinner(), padding="2rem"),
                rx.vstack(
                    rx.foreach(_S.grid_filtrado, _fila),
                    spacing="1",
                    width="100%",
                    max_height="58vh",
                    overflow_y="auto",
                ),
            ),
            spacing="2",
            width="100%",
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
        page_heading("Gestión de empleados", "Selecciona un empleado para ver y editar su ficha."),
        rx.grid(
            rx.box(_lista(), width="100%"),
            rx.box(card(editor_panel(), width="100%"), width="100%"),
            columns=rx.breakpoints(initial="1", lg="minmax(360px, 420px) 1fr"),
            spacing="4",
            width="100%",
            align_items="start",
        ),
        requiere=("empleados", "ver"),
    )
