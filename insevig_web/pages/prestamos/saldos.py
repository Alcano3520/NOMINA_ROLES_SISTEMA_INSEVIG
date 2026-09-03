from __future__ import annotations

import reflex as rx

from insevig_web.components.data_source_selector import data_source_selector
from insevig_web.components.job_progress import job_progress
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.prestamos_state import PrestamosState


@rx.page(
    route="/prestamos/saldos",
    title="INSEVIG — Saldos de préstamos",
    on_load=AuthState.cargar_sesion,
)
def saldos() -> rx.Component:
    return pagina(
        page_heading("Saldos de préstamos", "CLASE 205 consolidado por empleado. Se exporta a Excel."),
        rx.vstack(
            card(
                rx.vstack(
                    rx.hstack(
                        rx.text("Fuente:", weight="bold", size="2"),
                        data_source_selector("prestamos"),
                        spacing="2",
                    ),
                    primary_button(
                        "Generar Excel de saldos",
                        on_click=PrestamosState.generar_saldos,
                        disabled=PrestamosState.saldos_status.contains("corriendo"),
                    ),
                    spacing="3",
                    align="start",
                ),
                width="100%",
            ),
            rx.cond(
                PrestamosState.saldos_job > 0,
                job_progress(
                    status=PrestamosState.saldos_status,
                    progress=rx.Var.create(0),
                    total=rx.Var.create(1),
                    message=PrestamosState.saldos_msg,
                    error=rx.Var.create(""),
                    corriendo=PrestamosState.saldos_status.contains("corriendo")
                    | PrestamosState.saldos_status.contains("pendiente"),
                    tiene_resultado=PrestamosState.saldos_path != "",
                    on_cancelar=PrestamosState.cancelar_saldos,
                    on_descargar=PrestamosState.descargar_saldos,
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("prestamos", "ver"),
    )
