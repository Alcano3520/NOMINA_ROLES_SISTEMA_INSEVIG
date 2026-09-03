from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.data_source_selector import data_source_selector
from insevig_web.components.employee_search import employee_search
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.prestamos_state import PrestamosState


def _tabla_movimientos() -> rx.Component:
    return scroll_x(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    *[
                        rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                        for c in ("Fecha", "Concepto", "Valor", "Origen", "N°", "Cuadre")
                    ]
                )
            ),
            rx.table.body(
                rx.foreach(
                    PrestamosState.movimientos,
                    lambda m: rx.table.row(
                        rx.table.cell(m["fecha"]),
                        rx.table.cell(m["concepto"]),
                        rx.table.cell(m["valor"].to_string()),
                        rx.table.cell(m["origen"]),
                        rx.table.cell(m["numero"]),
                        rx.table.cell(rx.cond(m["es_cuadre"], "SÍ", "")),
                    ),
                )
            ),
            variant="surface",
            size="1",
            width="100%",
        )
    )


@rx.page(
    route="/prestamos/historial",
    title="INSEVIG — Historial de préstamos",
    on_load=AuthState.cargar_sesion,
)
def historial() -> rx.Component:
    return pagina(
        page_heading("Historial de préstamos", "CLASE 205. Combina SQL Server / Supabase + histórico migrado."),
        rx.vstack(
            rx.hstack(rx.text("Fuente:", weight="bold", size="2"), data_source_selector("prestamos"), spacing="2"),
            employee_search(
                texto=PrestamosState.texto_busqueda,
                resultados=PrestamosState.resultados,
                on_set_texto=PrestamosState.set_texto,
                on_buscar=PrestamosState.buscar,
                on_seleccionar=PrestamosState.seleccionar,
            ),
            rx.cond(
                PrestamosState.empleado_sel != "",
                card(
                    rx.vstack(
                        rx.hstack(
                            rx.heading(
                                f"{PrestamosState.empleado_sel} — {PrestamosState.nombre_sel}", size="4"
                            ),
                            rx.badge(
                                "Saldo: " + PrestamosState.saldo_empleado.to_string(),
                                color_scheme="blue",
                                size="2",
                            ),
                            spacing="3",
                            align="center",
                            wrap="wrap",
                        ),
                        rx.cond(PrestamosState.cargando_hist, rx.spinner(), _tabla_movimientos()),
                        rx.hstack(
                            rx.button(
                                "Analizar con IA",
                                on_click=PrestamosState.generar_narrativa,
                                variant="soft",
                            ),
                            rx.cond(
                                PrestamosState.narrativa_status != "",
                                rx.badge(PrestamosState.narrativa_status),
                            ),
                            spacing="2",
                        ),
                        rx.cond(
                            PrestamosState.narrativa != "",
                            rx.callout(PrestamosState.narrativa, size="1"),
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
        requiere=("prestamos", "ver"),
    )
