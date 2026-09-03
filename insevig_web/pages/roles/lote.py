from __future__ import annotations

import reflex as rx

from insevig_web.components.job_progress import job_progress
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.roles_pdf_state import FORMATOS_LISTA, RolesState


@rx.page(
    route="/roles/lote",
    title="INSEVIG — Roles por lote",
    on_load=[AuthState.cargar_sesion, RolesState.on_load],
)
def lote() -> rx.Component:
    return pagina(
        page_heading("Roles de pago por lote", "Genera un ZIP con un PDF por empleado."),
        rx.vstack(
            card(
                rx.vstack(
                    rx.hstack(
                        rx.input(value=RolesState.periodo, on_change=RolesState.set_periodo, placeholder="2026-06", width="120px"),
                        rx.select(FORMATOS_LISTA, default_value="cedula-nombre", on_change=RolesState.set_formato),
                        spacing="2",
                        wrap="wrap",
                    ),
                    rx.hstack(
                        rx.checkbox("2 roles por hoja", checked=RolesState.dos_por_hoja, on_change=RolesState.toggle_doble),
                        rx.checkbox("Incluir logo", checked=RolesState.con_logo, on_change=RolesState.toggle_logo),
                        spacing="4",
                        wrap="wrap",
                    ),
                    rx.text("Identificaciones (una por línea o separadas por coma):", size="1", weight="bold"),
                    rx.text_area(
                        value=RolesState.lista_texto,
                        on_change=RolesState.set_lista,
                        placeholder="1012\n2050\n0920116811",
                        rows="6",
                        width="100%",
                    ),
                    primary_button("Generar lote", on_click=RolesState.generar_lote),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                RolesState.lote_job > 0,
                job_progress(
                    status=RolesState.lote_status,
                    progress=rx.Var.create(0),
                    total=rx.Var.create(1),
                    message=RolesState.lote_msg,
                    error=rx.Var.create(""),
                    corriendo=RolesState.lote_status.contains("corriendo") | RolesState.lote_status.contains("pendiente"),
                    tiene_resultado=RolesState.lote_path != "",
                    on_cancelar=RolesState.cancelar_lote,
                    on_descargar=RolesState.descargar_lote,
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("roles", "generar_pdf"),
    )
