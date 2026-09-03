from __future__ import annotations

import reflex as rx

from insevig_web.components.job_progress import job_progress
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.envio_state import EnvioState


@rx.page(
    route="/envio",
    title="INSEVIG — Envío de roles",
    on_load=[AuthState.cargar_sesion, EnvioState.on_load],
)
def index() -> rx.Component:
    return pagina(
        page_heading(
            "Envío de roles por correo",
            "Sube un Excel con columnas empleado/nombre/cedula/email. Genera el PDF de cada uno y lo envía (SMTP o Graph según config).",
        ),
        rx.vstack(
            card(
                rx.vstack(
                    rx.upload(
                        rx.vstack(rx.icon("upload", size=24), rx.text("Excel de destinatarios (.xlsx)")),
                        id="envio",
                        accept={".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                        max_files=1,
                        border="1px dashed var(--gray-6)",
                        padding="1.5rem",
                        width="100%",
                    ),
                    rx.button("Cargar", on_click=EnvioState.subir_lista(rx.upload_files(upload_id="envio"))),
                    rx.hstack(
                        rx.input(value=EnvioState.periodo, on_change=EnvioState.set_periodo, placeholder="2026-06", width="120px"),
                        rx.input(value=EnvioState.intervalo, on_change=EnvioState.set_intervalo, placeholder="seg entre envíos", width="120px"),
                        rx.input(value=EnvioState.cc, on_change=EnvioState.set_cc, placeholder="CC (coma)", width="220px"),
                        spacing="2",
                        wrap="wrap",
                    ),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                EnvioState.errores.length() > 0,
                rx.callout(rx.foreach(EnvioState.errores, lambda e: rx.text(e, size="1")), color_scheme="amber", size="1"),
            ),
            rx.cond(
                EnvioState.destinatarios.length() > 0,
                card(
                    rx.vstack(
                        rx.text(EnvioState.destinatarios.length().to_string() + " destinatarios con email válido", weight="bold"),
                        rx.cond(
                            AuthState.permisos_flat.contains("roles:enviar_email"),
                            primary_button("Enviar roles", on_click=EnvioState.enviar),
                        ),
                        spacing="2",
                    ),
                    width="100%",
                ),
            ),
            rx.cond(
                EnvioState.job > 0,
                job_progress(
                    status=EnvioState.status,
                    progress=rx.Var.create(0),
                    total=rx.Var.create(1),
                    message=EnvioState.msg,
                    error=rx.Var.create(""),
                    corriendo=EnvioState.status.contains("corriendo") | EnvioState.status.contains("pendiente"),
                    tiene_resultado=rx.Var.create(False),
                    on_cancelar=EnvioState.cancelar,
                    on_descargar=EnvioState.cancelar,
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("roles", "enviar_email"),
    )
