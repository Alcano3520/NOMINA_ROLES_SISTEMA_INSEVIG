from __future__ import annotations

import reflex as rx

from insevig_web.components.job_progress import job_progress
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.observaciones_state import ObservacionesState

_S = ObservacionesState


@rx.page(
    route="/observaciones/carga-masiva",
    title="INSEVIG — Carga masiva de observaciones",
    on_load=AuthState.cargar_sesion,
)
def carga_masiva() -> rx.Component:
    return pagina(
        page_heading(
            "Carga masiva de observaciones",
            "Sube un Excel con columnas EMPLEADO, PERIODO (AAAA-MM) y TEXTO. Cada observación "
            "va al primer espacio libre del mes; se ignoran las repetidas.",
        ),
        rx.link("← Volver a Observaciones", href="/observaciones", size="2"),
        rx.vstack(
            card(
                rx.vstack(
                    rx.upload(
                        rx.vstack(rx.icon("upload", size=28), rx.text("Arrastra o selecciona el .xlsx")),
                        id="obs_masiva",
                        accept={".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                        max_files=1,
                        border="1px dashed var(--gray-6)",
                        padding="2rem",
                        width="100%",
                    ),
                    rx.button(
                        "Cargar y previsualizar",
                        on_click=_S.subir_masiva(rx.upload_files(upload_id="obs_masiva")),
                    ),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                _S.masiva_errores.length() > 0,
                rx.callout(
                    rx.foreach(_S.masiva_errores, lambda e: rx.text(e, size="1")),
                    color_scheme="amber",
                    size="1",
                ),
            ),
            rx.cond(
                _S.masiva_filas.length() > 0,
                card(
                    rx.vstack(
                        rx.text(
                            _S.masiva_filas.length().to_string() + " observaciones listas para aplicar",
                            weight="bold",
                        ),
                        rx.scroll_area(
                            rx.foreach(
                                _S.masiva_filas,
                                lambda f: rx.text(
                                    f"{f['empleado']} · {f['periodo']} · {f['texto']}", size="1"
                                ),
                            ),
                            type="hover",
                            scrollbars="vertical",
                            style={"maxHeight": "200px"},
                        ),
                        rx.cond(
                            AuthState.permisos_flat.contains("observaciones:crear"),
                            primary_button("Aplicar", on_click=_S.aplicar_masiva),
                            rx.text("Sin permiso para crear observaciones.", size="1", color_scheme="red"),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    width="100%",
                ),
            ),
            rx.cond(
                _S.masiva_job > 0,
                job_progress(
                    status=_S.masiva_status,
                    progress=rx.Var.create(0),
                    total=rx.Var.create(1),
                    message=_S.masiva_msg,
                    error=rx.Var.create(""),
                    corriendo=_S.masiva_status.contains("corriendo") | _S.masiva_status.contains("pendiente"),
                    tiene_resultado=_S.masiva_path != "",
                    on_cancelar=_S.cancelar_masiva,
                    on_descargar=_S.descargar_masiva,
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("observaciones", "crear"),
    )
