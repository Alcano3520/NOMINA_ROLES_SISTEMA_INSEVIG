from __future__ import annotations

import reflex as rx

from insevig_web.components.data_source_selector import data_source_selector
from insevig_web.components.job_progress import job_progress
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.reportes_state import ReportesState


def _controles() -> rx.Component:
    return card(
        rx.vstack(
            rx.hstack(
                rx.text("Fuente:", size="2", weight="bold"),
                data_source_selector("reportes"),
                spacing="2",
                align="center",
                wrap="wrap",
            ),
            rx.hstack(
                rx.vstack(
                    rx.text("Período (YYYY-MM)", size="2", weight="bold"),
                    rx.input(
                        value=ReportesState.periodo,
                        on_change=ReportesState.setvar("periodo"),
                        placeholder="2026-06",
                        width="140px",
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.vstack(
                    rx.text("Alcance", size="2", weight="bold"),
                    rx.select(
                        ["Nómina actual", "Histórico (RPHISTOR)"],
                        default_value="Nómina actual",
                        on_change=ReportesState.set_alcance,
                    ),
                    spacing="1",
                    align="start",
                ),
                spacing="4",
                wrap="wrap",
                align="end",
            ),
            primary_button(
                "Generar reporte",
                on_click=ReportesState.generar,
                disabled=ReportesState.corriendo,
            ),
            spacing="4",
            align="start",
            width="100%",
        ),
        width="100%",
    )


@rx.page(
    route="/reportes/consolidado",
    title="INSEVIG — Consolidado de nómina",
    on_load=[AuthState.cargar_sesion, ReportesState.on_load],
)
def consolidado() -> rx.Component:
    return pagina(
        page_heading(
            "Consolidado de nómina",
            "Una fila por empleado, columnas por concepto. Se genera como Excel descargable.",
        ),
        rx.vstack(
            _controles(),
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
        requiere=("reportes", "ver"),
    )
