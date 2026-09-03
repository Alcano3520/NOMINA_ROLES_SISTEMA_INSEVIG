from __future__ import annotations

import reflex as rx

from insevig_web.components.job_progress import job_progress
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.reportes_state import ReportesState


@rx.page(
    route="/reportes/comparador",
    title="INSEVIG — Verificación de datos",
    on_load=[AuthState.cargar_sesion, ReportesState.on_load],
)
def comparador() -> rx.Component:
    return pagina(
        page_heading(
            "Verificación de datos (administración)",
            "Recalcula el consolidado de nómina desde los dos orígenes y lista cualquier diferencia.",
        ),
        rx.vstack(
            card(
                rx.vstack(
                    rx.hstack(
                        rx.text("Período (YYYY-MM)", size="2", weight="bold"),
                        rx.input(
                            value=ReportesState.periodo,
                            on_change=ReportesState.set_periodo,
                            placeholder="2026-06",
                            width="140px",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    primary_button(
                        "Comparar",
                        on_click=ReportesState.generar_comparador,
                        disabled=ReportesState.corriendo,
                    ),
                    spacing="3",
                    align="start",
                ),
                width="100%",
            ),
            rx.cond(
                ReportesState.job_id > 0,
                job_progress(
                    status=ReportesState.job_status,
                    progress=ReportesState.job_progress,
                    total=ReportesState.job_total,
                    message=ReportesState.job_message,
                    error=ReportesState.job_error,
                    corriendo=ReportesState.corriendo,
                    tiene_resultado=ReportesState.result_path != "",
                    on_cancelar=ReportesState.cancelar,
                    on_descargar=ReportesState.descargar,
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("reportes", "exportar"),
    )
