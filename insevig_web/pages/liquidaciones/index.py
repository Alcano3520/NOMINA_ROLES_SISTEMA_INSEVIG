from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.job_progress import job_progress
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.liquidaciones_state import LiquidacionesState


@rx.page(route="/liquidaciones", title="INSEVIG — Liquidaciones", on_load=AuthState.cargar_sesion)
def index() -> rx.Component:
    return pagina(
        page_heading(
            "Generador de liquidaciones (finiquitos)",
            "Cálculo legal: vacaciones, décimo 13/14, desahucio, indemnización por despido, IESS, "
            "fondo de reserva, split de anticipos. Una línea por empleado: cédula, dd/mm/aaaa, motivo.",
        ),
        rx.vstack(
            card(
                rx.vstack(
                    rx.hstack(
                        rx.text("Región:", weight="bold", size="2"),
                        rx.select(["COSTA", "SIERRA"], default_value="COSTA", on_change=LiquidacionesState.set_region),
                        spacing="3",
                        wrap="wrap",
                        align="center",
                    ),
                    rx.text_area(
                        value=LiquidacionesState.entrada,
                        on_change=LiquidacionesState.set_entrada,
                        placeholder="0920116811, 15/02/2026, RENUNCIA VOLUNTARIA\n1712345678, 28/02/2026, DESPIDO INTEMPESTIVO",
                        rows="6",
                        width="100%",
                    ),
                    rx.hstack(
                        rx.button("Previsualizar", on_click=LiquidacionesState.previsualizar, variant="soft"),
                        primary_button("Generar Excel", on_click=LiquidacionesState.generar_excel),
                        spacing="2",
                    ),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                LiquidacionesState.previsualizacion.length() > 0,
                scroll_x(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                *[
                                    rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                                    for c in ("Empleado", "Nombre", "Motivo", "Días", "Ingresos",
                                             "Descuentos", "A recibir", "Error", "")
                                ]
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                LiquidacionesState.previsualizacion,
                                lambda q, i: rx.table.row(
                                    rx.table.cell(q["empleado"]),
                                    rx.table.cell(q["nombre"]),
                                    rx.table.cell(q["motivo"]),
                                    rx.table.cell(q["dias"].to_string()),
                                    rx.table.cell(q["ingresos"].to_string()),
                                    rx.table.cell(q["descuentos"].to_string()),
                                    rx.table.cell(q["recibir"].to_string()),
                                    rx.table.cell(q["error"]),
                                    rx.table.cell(
                                        rx.cond(
                                            q["error"] == "",
                                            rx.vstack(
                                                rx.hstack(
                                                    rx.button("PDF", on_click=lambda: LiquidacionesState.generar_pdf_fila(i),
                                                              size="1", variant="soft"),
                                                    rx.cond(
                                                        AuthState.permisos_flat.contains("liquidaciones:editar"),
                                                        rx.button("Guardar", on_click=lambda: LiquidacionesState.guardar_fila(i),
                                                                  size="1", color_scheme="blue"),
                                                    ),
                                                    spacing="1",
                                                ),
                                                rx.cond(
                                                    LiquidacionesState.fila_msg.contains(i.to_string()),
                                                    rx.text(LiquidacionesState.fila_msg[i.to_string()], size="1", color_scheme="gray"),
                                                ),
                                                spacing="1", align="start",
                                            ),
                                        )
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
                LiquidacionesState.job > 0,
                job_progress(
                    status=LiquidacionesState.status,
                    progress=rx.Var.create(0),
                    total=rx.Var.create(1),
                    message=LiquidacionesState.msg,
                    error=rx.Var.create(""),
                    corriendo=LiquidacionesState.status.contains("corriendo") | LiquidacionesState.status.contains("pendiente"),
                    tiene_resultado=LiquidacionesState.path != "",
                    on_cancelar=LiquidacionesState.cancelar,
                    on_descargar=LiquidacionesState.descargar,
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("liquidaciones", "ver"),
    )
