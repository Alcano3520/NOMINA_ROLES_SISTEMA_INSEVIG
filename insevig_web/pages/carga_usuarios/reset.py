"""/carga-usuarios/reset — resetear contraseña de un usuario."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.pages.carga_usuarios._comunes import aviso_service_key, tabs_nav
from insevig_web.states.auth_state import AuthState
from insevig_web.states.carga_usuarios_state import CargaUsuariosState

_S = CargaUsuariosState


@rx.page(route="/carga-usuarios/reset", title="INSEVIG — Usuarios app · Reset",
         on_load=AuthState.cargar_sesion)
def reset() -> rx.Component:
    return pagina(
        page_heading("Resetear contraseña", "Buscá el usuario por email y asigná una nueva clave."),
        tabs_nav("/carga-usuarios/reset"),
        rx.vstack(
            aviso_service_key(),
            card(
                rx.vstack(
                    rx.flex(
                        rx.input(value=_S.rst_email, on_change=_S.set_rst_email,
                                 placeholder="email del usuario", size="2", width="100%"),
                        rx.button("Buscar", on_click=_S.rst_buscar, size="2", variant="soft"),
                        gap="2", width="100%",
                    ),
                    rx.cond(
                        _S.rst_user.contains("id"),
                        rx.box(
                            rx.text(f"{_S.rst_user['email']} · rol {_S.rst_user['rol']}", size="2",
                                    weight="bold"),
                            rx.flex(
                                rx.input(value=_S.rst_password, on_change=_S.set_rst_password,
                                         placeholder="(vacío = generar automática)", size="2", width="100%"),
                                rx.button("Generar", on_click=_S.generar_rst_password, size="2",
                                          variant="soft"),
                                rx.cond(
                                    AuthState.permisos_flat.contains("carga_usuarios:editar"),
                                    primary_button("Resetear", on_click=_S.rst_resetear),
                                ),
                                gap="2", width="100%", wrap="wrap",
                            ),
                            rx.cond(
                                _S.rst_password != "",
                                rx.hstack(
                                    rx.code(_S.rst_password, size="2"),
                                    rx.button(rx.icon("copy", size=12), "Copiar",
                                              on_click=rx.set_clipboard(_S.rst_password),
                                              size="1", variant="ghost"),
                                    align="center",
                                ),
                            ),
                            background="var(--gray-2)", border="1px solid var(--gray-4)",
                            border_radius="8px", padding="10px 12px", width="100%",
                            margin_top="0.5rem",
                        ),
                    ),
                    rx.cond(_S.rst_msg != "", rx.callout(_S.rst_msg, size="1")),
                    spacing="3", width="100%",
                ),
                width="100%",
            ),
            spacing="4", width="100%",
        ),
        requiere=("carga_usuarios", "editar"),
    )
