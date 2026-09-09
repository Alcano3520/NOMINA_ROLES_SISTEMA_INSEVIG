from __future__ import annotations

import reflex as rx

from insevig_web.components.job_progress import job_progress
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.roles_pdf_state import FORMATOS_LISTA, RolesState

_S = RolesState


def _campo(label: str, control: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", weight="bold", color_scheme="gray"),
        control, spacing="1", width="100%",
    )


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
                    rx.grid(
                        _campo("Período", rx.input(
                            value=_S.periodo, on_change=_S.set_periodo,
                            placeholder="2026-06", size="2", width="100%",
                        )),
                        _campo("Formato de nombre del archivo", rx.select(
                            FORMATOS_LISTA, default_value="cedula-nombre",
                            on_change=_S.set_formato, size="2", width="100%",
                        )),
                        columns=rx.breakpoints(initial="1", sm="2"),
                        spacing="4", width="100%",
                    ),
                    rx.flex(
                        rx.checkbox("2 roles por hoja", checked=_S.dos_por_hoja,
                                    on_change=_S.toggle_doble),
                        rx.checkbox("Incluir logo", checked=_S.con_logo,
                                    on_change=_S.toggle_logo),
                        gap="5", wrap="wrap", align="center",
                    ),
                    rx.divider(),
                    _campo("Añadir empleados", rx.flex(
                        rx.input(
                            value=_S.busca, on_change=_S.set_busca,
                            placeholder="Buscar empleado para añadir…", size="2",
                            flex_grow="1", min_width="0",
                        ),
                        rx.button(rx.icon("search", size=15), on_click=_S.buscar_emp, size="2"),
                        rx.button("Todo el período", on_click=_S.generar_todo_periodo,
                                  variant="soft", size="2", flex_shrink="0"),
                        gap="2", width="100%", wrap="wrap", align="center",
                    )),
                    rx.cond(
                        _S.encontrados.length() > 0,
                        rx.vstack(
                            rx.foreach(
                                _S.encontrados,
                                lambda e: rx.box(
                                    rx.text(
                                        f"{e['empleado']}  —  {e['apellidos_nombres']}  ({e['cedula']})",
                                        size="1",
                                    ),
                                    on_click=lambda: _S.anadir_emp(e["empleado"]),
                                    padding="8px 10px", cursor="pointer", border_radius="6px",
                                    _hover={"background": "var(--gray-3)"},
                                ),
                            ),
                            spacing="1", max_height="180px", overflow_y="auto", width="100%",
                            border="1px solid var(--gray-5)", border_radius="8px", padding="4px",
                        ),
                    ),
                    _campo("Empleados a incluir (uno por línea o coma)", rx.text_area(
                        value=_S.lista_texto, on_change=_S.set_lista,
                        placeholder="1012\n2050\n0920116811", rows="6", width="100%",
                    )),
                    rx.cond(
                        _S.lote_todos_status != "",
                        rx.text(_S.lote_todos_status, size="1", color_scheme="gray"),
                    ),
                    rx.divider(),
                    primary_button("Generar lote", on_click=_S.generar_lote),
                    spacing="4", width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                _S.lote_job > 0,
                job_progress(
                    status=_S.lote_status,
                    progress=rx.Var.create(0), total=rx.Var.create(1),
                    message=_S.lote_msg, error=rx.Var.create(""),
                    corriendo=_S.lote_status.contains("corriendo") | _S.lote_status.contains("pendiente"),
                    tiene_resultado=_S.lote_path != "",
                    on_cancelar=_S.cancelar_lote, on_descargar=_S.descargar_lote,
                ),
            ),
            spacing="4", width="100%",
        ),
        requiere=("roles", "generar_pdf"),
    )
