from __future__ import annotations

import reflex as rx

from insevig_web.components.job_progress import job_progress
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.empleados_state import EmpleadosState


@rx.page(
    route="/empleados/carga-masiva",
    title="INSEVIG — Carga masiva de empleados",
    on_load=AuthState.cargar_sesion,
)
def carga_masiva() -> rx.Component:
    return pagina(
        page_heading(
            "Carga masiva de empleados",
            "Sube un Excel con columna EMPLEADO + las columnas a actualizar. Solo SQL Server, con auditoría por fila.",
        ),
        rx.vstack(
            card(
                rx.vstack(
                    rx.upload(
                        rx.vstack(
                            rx.icon("upload", size=28),
                            rx.text("Arrastra o selecciona el .xlsx"),
                        ),
                        id="masiva",
                        accept={".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                        max_files=1,
                        border="1px dashed var(--gray-6)",
                        padding="2rem",
                        width="100%",
                    ),
                    rx.button(
                        "Cargar y previsualizar",
                        on_click=EmpleadosState.subir_masiva(rx.upload_files(upload_id="masiva")),
                    ),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                EmpleadosState.masiva_errores.length() > 0,
                rx.callout(
                    rx.foreach(EmpleadosState.masiva_errores, lambda e: rx.text(e, size="1")),
                    color_scheme="amber",
                    size="1",
                ),
            ),
            rx.cond(
                EmpleadosState.masiva_filas.length() > 0,
                card(
                    rx.vstack(
                        rx.text(
                            EmpleadosState.masiva_filas.length().to_string() + " filas listas para aplicar",
                            weight="bold",
                        ),
                        rx.cond(
                            AuthState.permisos_flat.contains("empleados:cargar_masivo"),
                            primary_button("Aplicar a SQL Server", on_click=EmpleadosState.aplicar_masiva),
                        ),
                        spacing="2",
                    ),
                    width="100%",
                ),
            ),
            rx.cond(
                EmpleadosState.masiva_job > 0,
                job_progress(
                    status=EmpleadosState.masiva_status,
                    progress=rx.Var.create(0),
                    total=rx.Var.create(1),
                    message=EmpleadosState.masiva_msg,
                    error=rx.Var.create(""),
                    corriendo=EmpleadosState.masiva_status.contains("corriendo")
                    | EmpleadosState.masiva_status.contains("pendiente"),
                    tiene_resultado=EmpleadosState.masiva_path != "",
                    on_cancelar=EmpleadosState.cancelar_masiva,
                    on_descargar=EmpleadosState.descargar_masiva,
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("empleados", "cargar_masivo"),
    )
