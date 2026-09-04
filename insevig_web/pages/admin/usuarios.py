from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.auth import ROLES
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x
from insevig_web.states.admin_state import AdminState
from insevig_web.states.auth_state import AuthState


@rx.page(
    route="/admin/usuarios",
    title="INSEVIG — Usuarios",
    on_load=[AuthState.cargar_sesion, AdminState.cargar_usuarios],
)
def usuarios() -> rx.Component:
    return pagina(
        page_heading("Usuarios", "Alta y activación de usuarios de la app."),
        rx.vstack(
            card(
                rx.vstack(
                    rx.heading("Nuevo usuario", size="3"),
                    rx.grid(
                        rx.input(value=AdminState.nu_username, on_change=lambda v: AdminState.set_nu("username", v), placeholder="usuario"),
                        rx.input(value=AdminState.nu_nombre, on_change=lambda v: AdminState.set_nu("nombre", v), placeholder="Nombre completo"),
                        rx.input(value=AdminState.nu_clave, on_change=lambda v: AdminState.set_nu("clave", v), type="password", placeholder="contraseña"),
                        rx.select(list(ROLES), default_value="consulta", on_change=lambda v: AdminState.set_nu("rol", v)),
                        columns=rx.breakpoints(initial="1", sm="2", lg="4"),
                        spacing="2",
                        width="100%",
                    ),
                    primary_button("Crear", on_click=AdminState.crear_usuario),
                    rx.cond(AdminState.msg != "", rx.callout(AdminState.msg, size="1")),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            scroll_x(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            *[
                                rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                                for c in ("Usuario", "Nombre", "Roles", "Activo", "Último acceso", "")
                            ]
                        )
                    ),
                    rx.table.body(
                        rx.foreach(
                            AdminState.usuarios,
                            lambda u: rx.table.row(
                                rx.table.cell(u["username"]),
                                rx.table.cell(u["nombre"]),
                                rx.table.cell(u["roles"]),
                                rx.table.cell(rx.cond(u["activo"], "sí", "no")),
                                rx.table.cell(u["ultimo"]),
                                rx.table.cell(
                                    rx.hstack(
                                        rx.button(
                                            rx.cond(u["activo"], "Desactivar", "Activar"),
                                            on_click=lambda: AdminState.toggle_activo(u["id"]),
                                            size="1",
                                            variant="soft",
                                        ),
                                        rx.alert_dialog.root(
                                            rx.alert_dialog.trigger(
                                                rx.button(
                                                    "Resetear clave",
                                                    on_click=lambda: AdminState.abrir_reset(u["id"]),
                                                    size="1",
                                                    variant="soft",
                                                    color_scheme="amber",
                                                )
                                            ),
                                            rx.alert_dialog.content(
                                                rx.alert_dialog.title("Resetear contraseña"),
                                                rx.alert_dialog.description(
                                                    rx.text(f"Escribe la nueva contraseña para {u['username']}.")
                                                ),
                                                rx.input(
                                                    value=AdminState.reset_clave,
                                                    on_change=AdminState.set_reset_clave,
                                                    type="password",
                                                    placeholder="nueva contraseña",
                                                    margin_top="0.5rem",
                                                ),
                                                rx.hstack(
                                                    rx.alert_dialog.cancel(rx.button("Cancelar", variant="soft")),
                                                    rx.alert_dialog.action(
                                                        rx.button("Resetear", on_click=AdminState.resetear_clave, color_scheme="amber")
                                                    ),
                                                    spacing="3",
                                                    justify="end",
                                                    margin_top="1rem",
                                                ),
                                            ),
                                        ),
                                        spacing="2",
                                    )
                                ),
                            ),
                        )
                    ),
                    variant="surface",
                    size="1",
                    width="100%",
                )
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("admin", "ver"),
    )
