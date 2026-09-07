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
                        for c in ("Fecha", "Concepto", "Valor", "Tipo", "Origen", "N°", "Cuadre")
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
                        rx.table.cell(
                            rx.match(
                                m["tipo"],
                                ("pendiente", "Pendiente"),
                                ("desembolso", "Desembolso"),
                                "Pago",
                            )
                        ),
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
                        for c in ("N°", "Desde", "Hasta", "Prestado", "Pagado", "Saldo", "Cuotas", "Estado", "")
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


_INP = {"size": "1", "width": "120px"}
_SEL_STYLE = {"padding": "5px", "borderRadius": "6px", "border": "1px solid var(--gray-6)",
              "background": "#fff", "fontSize": "13px"}


def _filtros() -> rx.Component:
    S = PrestamosState
    return rx.hstack(
        rx.el.select(
            rx.el.option("Todo tipo", value=""),
            rx.el.option("Solo pagos", value="pago"),
            rx.el.option("Solo pendiente (RPINGDES)", value="pendiente"),
            value=S.filtro_tipo, on_change=lambda v: S.set_filtro("tipo", v), style=_SEL_STYLE,
        ),
        rx.el.select(
            rx.el.option("Todo origen", value=""),
            rx.el.option("Sistema actual", value="RPINGDES"),
            rx.el.option("Histórico", value="RPHISTOR"),
            rx.el.option("Migrado", value="MIGRADO"),
            value=S.filtro_origen, on_change=lambda v: S.set_filtro("origen", v), style=_SEL_STYLE,
        ),
        rx.input(value=S.filtro_numero, on_change=lambda v: S.set_filtro("numero", v),
                 placeholder="N°", **_INP),
        rx.input(value=S.filtro_texto, on_change=lambda v: S.set_filtro("texto", v),
                 placeholder="Concepto…", **_INP),
        rx.input(value=S.filtro_desde, on_change=lambda v: S.set_filtro("desde", v),
                 placeholder="Desde AAAA-MM-DD", **{**_INP, "width": "150px"}),
        rx.input(value=S.filtro_hasta, on_change=lambda v: S.set_filtro("hasta", v),
                 placeholder="Hasta AAAA-MM-DD", **{**_INP, "width": "150px"}),
        rx.input(value=S.filtro_monto_min, on_change=lambda v: S.set_filtro("monto_min", v),
                 placeholder="Monto min", **{**_INP, "width": "100px"}),
        rx.input(value=S.filtro_monto_max, on_change=lambda v: S.set_filtro("monto_max", v),
                 placeholder="Monto max", **{**_INP, "width": "100px"}),
        rx.cond(S.hay_filtros,
                rx.button("Limpiar", on_click=S.limpiar_filtros, variant="soft", size="1")),
        spacing="2", align="center", wrap="wrap",
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
                                    for c in ("Fecha", "Concepto", "Valor", "Tipo", "Origen", "Cuadre")
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
                                    rx.table.cell(
                                        rx.match(
                                            m["tipo"],
                                            ("pendiente", "Pendiente"),
                                            ("desembolso", "Desembolso"),
                                            "Pago",
                                        )
                                    ),
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
                                "Saldo pendiente: " + PrestamosState.saldo_empleado.to_string(),
                                color_scheme="blue",
                                size="2",
                            ),
                            spacing="3",
                            align="center",
                            wrap="wrap",
                        ),
                        _filtros(),
                        rx.hstack(
                            rx.badge("Mostrando " + PrestamosState.conteo_filtrado),
                            rx.badge("Pagos visibles: " + PrestamosState.pagado_filtrado.to_string()),
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
