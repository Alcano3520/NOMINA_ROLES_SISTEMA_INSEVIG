from __future__ import annotations

import reflex as rx

from insevig_web import theme
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
                    PrestamosState.movimientos_filtrados,
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


def _tabla_resumen() -> rx.Component:
    return scroll_x(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    *[
                        rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                        for c in ("N°", "Desde", "Hasta", "Prestado", "Abonado", "Saldo", "Cuotas", "Estado", "")
                    ]
                )
            ),
            rx.table.body(
                rx.foreach(
                    PrestamosState.resumen,
                    lambda g: rx.table.row(
                        rx.table.cell(g["numero"]),
                        rx.table.cell(g["desde"]),
                        rx.table.cell(g["hasta"]),
                        rx.table.cell(g["prestado"].to_string()),
                        rx.table.cell(g["abonado"].to_string()),
                        rx.table.cell(g["saldo"].to_string()),
                        rx.table.cell(g["cuotas"].to_string()),
                        rx.table.cell(
                            rx.text(
                                g["estado"],
                                size="1",
                                color_scheme=rx.cond(g["cancelado"], "green", "amber"),
                            )
                        ),
                        rx.table.cell(
                            rx.button(
                                "Ver",
                                size="1",
                                variant="soft",
                                on_click=lambda: PrestamosState.ver_detalle_prestamo(g["numero"]),
                            )
                        ),
                    ),
                )
            ),
            variant="surface",
            size="1",
            width="100%",
        )
    )


def _detalle_prestamo() -> rx.Component:
    return rx.cond(
        PrestamosState.detalle_movs.length() > 0,
        card(
            rx.vstack(
                rx.hstack(
                    rx.heading(PrestamosState.detalle_titulo, size="3"),
                    rx.spacer(),
                    rx.button("Cerrar", on_click=PrestamosState.cerrar_detalle, variant="soft", size="1"),
                    width="100%",
                ),
                scroll_x(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                *[
                                    rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                                    for c in ("Fecha", "Concepto", "Valor", "Origen", "Cuadre")
                                ]
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                PrestamosState.detalle_movs,
                                lambda m: rx.table.row(
                                    rx.table.cell(m["fecha"]),
                                    rx.table.cell(m["concepto"]),
                                    rx.table.cell(m["valor"].to_string()),
                                    rx.table.cell(m["origen"]),
                                    rx.table.cell(rx.cond(m["es_cuadre"], "SÍ", "")),
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
            width="100%",
        ),
    )


@rx.page(
    route="/prestamos/historial",
    title="INSEVIG — Historial de préstamos",
    on_load=AuthState.cargar_sesion,
)
def historial() -> rx.Component:
    return pagina(
        page_heading("Historial de préstamos", "Movimientos y saldo de los préstamos del empleado, incluido el histórico."),
        rx.vstack(
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
                        rx.hstack(
                            rx.text("Desde", size="1"),
                            rx.input(value=PrestamosState.filtro_desde, on_change=PrestamosState.set_filtro_desde,
                                     placeholder="AAAA-MM-DD", width="130px", size="1"),
                            rx.text("Hasta", size="1"),
                            rx.input(value=PrestamosState.filtro_hasta, on_change=PrestamosState.set_filtro_hasta,
                                     placeholder="AAAA-MM-DD", width="130px", size="1"),
                            rx.badge("Total: " + PrestamosState.total_filtrado.to_string()),
                            rx.button("Exportar a Excel", on_click=PrestamosState.exportar_empleado, variant="soft", size="1"),
                            rx.cond(
                                PrestamosState.exportar_path != "",
                                rx.button("Descargar", on_click=PrestamosState.descargar_exportar, size="1"),
                            ),
                            spacing="2",
                            align="center",
                            wrap="wrap",
                        ),
                        rx.cond(PrestamosState.cargando_hist, rx.spinner(), _tabla_movimientos()),
                        rx.cond(
                            PrestamosState.resumen.length() > 0,
                            rx.vstack(
                                rx.heading("Resumen por préstamo", size="3"),
                                _tabla_resumen(),
                                _detalle_prestamo(),
                                spacing="2",
                                width="100%",
                            ),
                        ),
                        rx.hstack(
                            rx.button(
                                "Analizar con IA",
                                on_click=PrestamosState.generar_narrativa,
                                variant="soft",
                            ),
                            rx.cond(
                                PrestamosState.narrativa != "",
                                rx.fragment(
                                    rx.button("🔊 Leer", on_click=PrestamosState.leer_en_voz_alta, variant="soft", size="1"),
                                    rx.button("■ Detener", on_click=PrestamosState.detener_voz, variant="ghost", size="1"),
                                ),
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
