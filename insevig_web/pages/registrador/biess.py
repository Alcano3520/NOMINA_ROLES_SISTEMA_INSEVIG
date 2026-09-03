from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.registrador_state import RegistradorState


@rx.page(
    route="/registrador/biess",
    title="INSEVIG — Importar BIESS",
    on_load=[AuthState.cargar_sesion, RegistradorState.on_load],
)
def biess() -> rx.Component:
    return pagina(
        page_heading(
            "Importar BIESS quirografarios",
            "Sube el Excel del BIESS. Se detectan las columnas de cédula y valor y se registran los préstamos quirografarios, con vista previa antes de confirmar.",
        ),
        rx.vstack(
            card(
                rx.vstack(
                    rx.hstack(
                        rx.input(value=RegistradorState.periodo, on_change=RegistradorState.set_periodo, placeholder="2026-06", width="120px"),
                        rx.upload(
                            rx.button("Seleccionar Excel BIESS"),
                            id="biess",
                            accept={".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                            max_files=1,
                        ),
                        rx.button("Cargar", on_click=RegistradorState.subir_biess(rx.upload_files(upload_id="biess"))),
                        spacing="2",
                        wrap="wrap",
                    ),
                    rx.cond(
                        RegistradorState.filas_biess.length() > 0,
                        rx.hstack(
                            rx.text(RegistradorState.filas_biess.length().to_string() + " filas leídas", weight="bold"),
                            rx.button("Preparar (dry-run)", on_click=RegistradorState.preparar, variant="soft"),
                            spacing="2",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                RegistradorState.avisos.length() > 0,
                rx.callout(rx.foreach(RegistradorState.avisos, lambda a: rx.text(a, size="1")), color_scheme="amber", size="1"),
            ),
            rx.cond(
                RegistradorState.movs.length() > 0,
                card(
                    rx.vstack(
                        rx.text(
                            "Vista previa: se insertarán "
                            + RegistradorState.dry["insertados"].to_string()
                            + " · omitidos por duplicado: "
                            + RegistradorState.dry["omitidos_dedupe"].to_string()
                            + " · sin empleado: "
                            + RegistradorState.dry["sin_empleado"].to_string(),
                            weight="bold",
                        ),
                        scroll_x(
                            rx.table.root(
                                rx.table.header(
                                    rx.table.row(
                                        *[
                                            rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                                            for c in ("Empleado", "Valor", "Estado BIESS")
                                        ]
                                    )
                                ),
                                rx.table.body(
                                    rx.foreach(
                                        RegistradorState.movs,
                                        lambda m: rx.table.row(
                                            rx.table.cell(m["empleado"]),
                                            rx.table.cell(m["valor"].to_string()),
                                            rx.table.cell(m["estado_biess"]),
                                        ),
                                    )
                                ),
                                variant="surface",
                                size="1",
                                width="100%",
                            )
                        ),
                        rx.cond(
                            AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                            primary_button("Confirmar y registrar", on_click=RegistradorState.postear),
                        ),
                        rx.cond(RegistradorState.error != "", rx.callout(RegistradorState.error, color_scheme="red", size="1")),
                        rx.cond(RegistradorState.resultado != "", rx.callout(RegistradorState.resultado, color_scheme="green", size="1")),
                        spacing="3",
                        width="100%",
                    ),
                    width="100%",
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("registrador", "registrar_rpingdes"),
    )
