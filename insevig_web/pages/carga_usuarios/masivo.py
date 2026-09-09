"""/carga-usuarios/masivo — carga masiva desde pegado de Excel."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, data_cell, data_table, page_heading, primary_button
from insevig_web.pages.carga_usuarios._comunes import aviso_service_key, tabs_nav
from insevig_web.states.auth_state import AuthState
from insevig_web.states.carga_usuarios_state import CargaUsuariosState

_S = CargaUsuariosState


def _fila(r: rx.Var) -> rx.Component:
    return rx.table.row(
        data_cell(r["email"]),
        data_cell(
            rx.match(
                r["accion"],
                ("ERROR", rx.badge("error", color_scheme="red", size="1")),
                ("CREADO", rx.badge("creado", color_scheme="grass", size="1")),
                ("ACTUALIZADO", rx.badge("actualizado", color_scheme="blue", size="1")),
                rx.badge(r["accion"], color_scheme="gray", size="1"),
            )
        ),
        data_cell(
            rx.cond(
                r["password"] != "",
                rx.hstack(
                    rx.code(r["password"], size="1"),
                    rx.button(rx.icon("copy", size=11),
                              on_click=rx.set_clipboard(r["password"]), size="1", variant="ghost"),
                    align="center",
                ),
                rx.text("—", size="1", color_scheme="gray"),
            )
        ),
        data_cell(rx.text(r["detalle"], size="1")),
    )


@rx.page(route="/carga-usuarios/masivo", title="INSEVIG — Usuarios app · Carga masiva",
         on_load=AuthState.cargar_sesion)
def masivo() -> rx.Component:
    return pagina(
        page_heading("Carga masiva de usuarios",
                     "Pegá desde Excel: email · nombre · rol · departamento · contraseña "
                     "(la contraseña es opcional; si falta, se genera)."),
        tabs_nav("/carga-usuarios/masivo"),
        rx.vstack(
            aviso_service_key(),
            card(
                rx.vstack(
                    rx.text_area(value=_S.mas_pegado, on_change=_S.set_mas_pegado,
                                 placeholder="ana@insevig.com\tAna Perez\tsupervisor\tOperaciones",
                                 rows="5", width="100%", font_family="monospace"),
                    rx.flex(
                        rx.checkbox("Generar contraseñas faltantes", checked=_S.mas_generar,
                                    on_change=_S.toggle_mas_generar),
                        rx.checkbox("Actualizar si ya existe", checked=_S.mas_actualizar,
                                    on_change=_S.toggle_mas_actualizar),
                        gap="4", wrap="wrap",
                    ),
                    rx.flex(
                        rx.button("Analizar pegado", on_click=_S.mas_parsear, size="2"),
                        rx.cond(
                            _S.mas_filas.length() > 0,
                            rx.button("Simular (dry-run)", on_click=_S.mas_dry_run, size="2",
                                      variant="soft", color_scheme="blue"),
                        ),
                        rx.cond(
                            (_S.mas_filas.length() > 0)
                            & AuthState.permisos_flat.contains("carga_usuarios:cargar_masivo"),
                            primary_button("Crear usuarios", on_click=_S.mas_ejecutar,
                                           loading=_S.mas_procesando),
                        ),
                        rx.button("Limpiar", on_click=_S.mas_limpiar, size="2", variant="ghost"),
                        rx.spacer(),
                        rx.cond(
                            _S.mas_filas.length() > 0,
                            rx.text(_S.mas_filas.length().to_string() + " filas", size="1",
                                    color_scheme="gray"),
                        ),
                        gap="2", align="center", wrap="wrap", width="100%",
                    ),
                    rx.cond(
                        _S.mas_resumen.contains("creados"),
                        rx.callout(
                            rx.cond(_S.mas_resumen["dry_run"], "Simulación — ", "")
                            + "Creados " + _S.mas_resumen["creados"].to_string()
                            + " · Actualizados " + _S.mas_resumen["actualizados"].to_string()
                            + " · Errores " + _S.mas_resumen["errores"].to_string(),
                            size="1",
                        ),
                    ),
                    spacing="3", width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                _S.mas_resultados.length() > 0,
                card(
                    data_table(
                        ["Email", "Acción", "Contraseña", "Detalle"],
                        rx.foreach(_S.mas_resultados, _fila),
                    ),
                    width="100%",
                ),
            ),
            spacing="4", width="100%",
        ),
        requiere=("carga_usuarios", "cargar_masivo"),
    )
