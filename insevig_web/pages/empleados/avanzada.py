from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.empleados_state import EmpleadosState

_S = EmpleadosState
_COLS = ("Código", "Apellidos", "Nombres", "Cédula", "Cargo", "Departamento", "Sueldo", "Teléfono", "Email", "Estado")


def _crit(etq: str, campo: str, placeholder: str = "") -> rx.Component:
    return rx.vstack(
        rx.text(etq, size="1", weight="bold"),
        rx.input(
            value=getattr(_S, f"av_{campo}"),
            on_change=lambda v: _S.set_av(campo, v),
            placeholder=placeholder,
            size="2",
            width="100%",
        ),
        spacing="1",
    )


@rx.page(route="/empleados/avanzada", title="INSEVIG — Búsqueda avanzada", on_load=AuthState.cargar_sesion)
def avanzada() -> rx.Component:
    return pagina(
        page_heading("Búsqueda avanzada de empleados", "Combina varios criterios; exporta a Excel."),
        rx.vstack(
            card(
                rx.vstack(
                    rx.grid(
                        _crit("Apellidos", "apellidos", "parcial"),
                        _crit("Nombres", "nombres", "parcial"),
                        _crit("Cédula", "cedula", "exacta"),
                        rx.vstack(
                            rx.text("Estado", size="1", weight="bold"),
                            rx.el.select(
                                rx.el.option("Todos", value=""),
                                rx.el.option("Activo", value="ACTIVO"),
                                rx.el.option("Liquidado", value="LIQUIDADO"),
                                rx.el.option("Suspendido", value="SUSPENDIDO"),
                                value=_S.av_estado,
                                on_change=lambda v: _S.set_av("estado", v),
                                style={"padding": "6px", "borderRadius": "6px",
                                       "border": "1px solid var(--gray-6)", "background": "#fff"},
                            ),
                            spacing="1",
                        ),
                        _crit("Departamento", "depto", "código"),
                        _crit("Cargo", "cargo", "código"),
                        columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                        spacing="3",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_button("Buscar", on_click=lambda: _S.buscar_avanzada(False)),
                        rx.button("Mostrar todos", on_click=lambda: _S.buscar_avanzada(True), variant="soft"),
                        rx.button("Exportar catálogos", on_click=_S.exportar_catalogos, variant="ghost"),
                        rx.spacer(),
                        rx.cond(
                            _S.av_resultados.length() > 0,
                            rx.button("Exportar Excel", on_click=_S.exportar_avanzada, variant="soft"),
                        ),
                        spacing="2",
                        width="100%",
                        wrap="wrap",
                    ),
                    rx.cond(_S.av_msg != "", rx.text(_S.av_msg, size="1", color_scheme="gray")),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                _S.av_cargando,
                rx.center(rx.spinner(), padding="2rem"),
                rx.cond(
                    _S.av_resultados.length() > 0,
                    scroll_x(
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(*[
                                    rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                                    for c in _COLS
                                ])
                            ),
                            rx.table.body(
                                rx.foreach(
                                    _S.av_resultados,
                                    lambda e: rx.table.row(
                                        rx.table.cell(
                                            rx.link(e["empleado"], on_click=lambda: _S.abrir_editor(e["empleado"]),
                                                    href="/empleados/buscar")
                                        ),
                                        rx.table.cell(e["apellidos"]),
                                        rx.table.cell(e["nombres"]),
                                        rx.table.cell(e["cedula"]),
                                        rx.table.cell(e["cargo_nombre"]),
                                        rx.table.cell(e["depto_nombre"]),
                                        rx.table.cell(e["sueldo"].to_string()),
                                        rx.table.cell(e["telefono"]),
                                        rx.table.cell(e["email"]),
                                        rx.table.cell(e["estado"]),
                                    ),
                                )
                            ),
                            variant="surface",
                            size="1",
                            width="100%",
                        )
                    ),
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("empleados", "ver"),
    )
