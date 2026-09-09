"""/carga-usuarios/listado — ver usuarios de Auth + profiles."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, data_cell, data_table, page_heading
from insevig_web.pages.carga_usuarios._comunes import tabs_nav
from insevig_web.states.auth_state import AuthState
from insevig_web.states.carga_usuarios_state import CargaUsuariosState

_S = CargaUsuariosState


def _fila(u: rx.Var) -> rx.Component:
    return rx.table.row(
        data_cell(u["email"]),
        data_cell(u["nombre"]),
        data_cell(u["rol"]),
        data_cell(rx.cond(u["activo"], rx.badge("activo", color_scheme="grass", size="1"),
                          rx.badge("inactivo", color_scheme="gray", size="1"))),
        data_cell(u["created_at"]),
        data_cell(u["last_sign_in_at"]),
    )


@rx.page(route="/carga-usuarios/listado", title="INSEVIG — Usuarios app · Listado",
         on_load=AuthState.cargar_sesion)
def listado() -> rx.Component:
    return pagina(
        page_heading("Usuarios de la app de sanciones", "Auth + perfil, primera página."),
        tabs_nav("/carga-usuarios/listado"),
        rx.vstack(
            card(
                rx.flex(
                    rx.input(value=_S.lst_filtro, on_change=_S.set_lst_filtro,
                             placeholder="Filtrar por email o nombre…", size="2", width="260px"),
                    rx.button("Cargar", on_click=_S.lst_cargar, size="2", loading=_S.lst_cargando),
                    rx.spacer(),
                    rx.text(_S.lst_filtrados.length().to_string() + " usuarios", size="1",
                            color_scheme="gray"),
                    gap="2", align="center", wrap="wrap", width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                _S.lst_filtrados.length() > 0,
                card(
                    data_table(
                        ["Email", "Nombre", "Rol", "Estado", "Creado", "Último acceso"],
                        rx.foreach(_S.lst_filtrados, _fila),
                    ),
                    width="100%",
                ),
            ),
            spacing="4", width="100%",
        ),
        requiere=("carga_usuarios", "ver"),
    )
