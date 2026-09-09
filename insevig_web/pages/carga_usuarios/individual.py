"""/carga-usuarios/individual — crear / actualizar un usuario."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.pages.carga_usuarios._comunes import aviso_service_key, tabs_nav
from insevig_web.states.auth_state import AuthState
from insevig_web.states.carga_usuarios_state import ROLES, CargaUsuariosState

_S = CargaUsuariosState

_SEL = {
    "padding": "6px 8px", "borderRadius": "6px", "width": "100%",
    "border": "1px solid var(--gray-6)", "background": "var(--color-panel-solid)",
    "color": "var(--gray-12)", "fontSize": "14px",
}


def _campo(label: str, control: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", weight="bold", color_scheme="gray"), control,
        spacing="1", width="100%",
    )


@rx.page(route="/carga-usuarios/individual", title="INSEVIG — Usuarios app · Individual",
         on_load=AuthState.cargar_sesion)
def individual() -> rx.Component:
    return pagina(
        page_heading("Usuarios de la app de sanciones", "Crear o actualizar una cuenta."),
        tabs_nav("/carga-usuarios/individual"),
        rx.vstack(
            aviso_service_key(),
            card(
                rx.vstack(
                    rx.grid(
                        _campo("Email", rx.input(value=_S.ind_email, on_change=_S.set_ind_email, size="2")),
                        _campo("Nombre", rx.input(value=_S.ind_nombre, on_change=_S.set_ind_nombre, size="2")),
                        _campo("Rol", rx.el.select(
                            *[rx.el.option(r, value=r) for r in ROLES],
                            value=_S.ind_rol, on_change=_S.set_ind_rol, style=_SEL,
                        )),
                        _campo("Departamento", rx.input(
                            value=_S.ind_departamento, on_change=_S.set_ind_departamento, size="2",
                        )),
                        columns=rx.breakpoints(initial="1", sm="2"), spacing="3", width="100%",
                    ),
                    _campo("Contraseña", rx.flex(
                        rx.input(value=_S.ind_password, on_change=_S.set_ind_password,
                                 placeholder="(vacío = generar automática)", size="2", width="100%"),
                        rx.button("Generar", on_click=_S.generar_ind_password, size="2", variant="soft"),
                        gap="2", width="100%",
                    )),
                    rx.flex(
                        rx.checkbox("Generar si queda vacía", checked=_S.ind_generar,
                                    on_change=_S.toggle_ind_generar),
                        rx.checkbox("Actualizar si ya existe", checked=_S.ind_actualizar,
                                    on_change=_S.toggle_ind_actualizar),
                        gap="4", wrap="wrap",
                    ),
                    rx.divider(),
                    rx.flex(
                        rx.button("Verificar", on_click=_S.ind_verificar, size="2", variant="soft"),
                        rx.cond(
                            AuthState.permisos_flat.contains("carga_usuarios:crear"),
                            primary_button("Crear / actualizar", on_click=_S.ind_crear),
                        ),
                        gap="2", wrap="wrap",
                    ),
                    rx.cond(_S.ind_msg != "", rx.callout(_S.ind_msg, size="1")),
                    rx.cond(
                        _S.ind_resultado.contains("email") & (_S.ind_resultado["accion"] != ""),
                        rx.box(
                            rx.text(f"{_S.ind_resultado['accion']} · {_S.ind_resultado['email']}",
                                    size="2", weight="bold"),
                            rx.cond(
                                _S.ind_resultado["password"] != "",
                                rx.hstack(
                                    rx.code(_S.ind_resultado["password"], size="2"),
                                    rx.button(rx.icon("copy", size=12), "Copiar",
                                              on_click=rx.set_clipboard(_S.ind_resultado["password"]),
                                              size="1", variant="ghost"),
                                    align="center",
                                ),
                            ),
                            background="var(--gray-2)", border="1px solid var(--gray-4)",
                            border_radius="8px", padding="10px 12px", width="100%",
                        ),
                    ),
                    spacing="3", width="100%",
                ),
                width="100%",
            ),
            spacing="4", width="100%",
        ),
        requiere=("carga_usuarios", "ver"),
    )
