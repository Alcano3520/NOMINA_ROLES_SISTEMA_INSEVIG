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
                    rx.hstack(
                        rx.input(
                            value=RolesState.busca,
                            on_change=RolesState.set_busca,
                            placeholder="Buscar empleado para añadir…",
                            size="2",
                            width="100%",
                        ),
                        rx.button("Buscar", on_click=RolesState.buscar_emp, size="2"),
                        rx.button(
                            "Todo el período",
                            on_click=RolesState.generar_todo_periodo,
                            variant="soft",
                            size="2",
                        ),
                        spacing="2",
                        width="100%",
                        wrap="wrap",
                    ),
                    rx.cond(
                        RolesState.encontrados.length() > 0,
                        rx.vstack(
                            rx.foreach(
                                RolesState.encontrados,
                                lambda e: rx.box(
                                    rx.text(
                                        f"{e['empleado']} — {e['apellidos_nombres']} ({e['cedula']})",
                                        size="1",
                                    ),
                                    on_click=lambda: RolesState.anadir_emp(e["empleado"]),
                                    padding="4px 6px",
                                    cursor="pointer",
                                    border_radius="4px",
                                    _hover={"background": "var(--accent-3)"},
                                ),
                            ),
                            spacing="1",
                            max_height="160px",
                            overflow_y="auto",
                            width="100%",
                        ),
                    ),
                    rx.text("Empleados a incluir (uno por línea o coma):", size="1", weight="bold"),
                    rx.text_area(
                        value=RolesState.lista_texto,
                        on_change=RolesState.set_lista,
                        placeholder="1012\n2050\n0920116811",
                        rows="6",
                        width="100%",
                    ),
                    rx.cond(
                        RolesState.lote_todos_status != "",
                        rx.text(RolesState.lote_todos_status, size="1", color_scheme="gray"),
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
