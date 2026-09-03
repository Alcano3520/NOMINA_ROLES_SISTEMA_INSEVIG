from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading
from insevig_web.pages.empleados._editor_panel import editor_panel
from insevig_web.states.auth_state import AuthState


@rx.page(route="/empleados/editar", title="INSEVIG — Ficha de empleado", on_load=AuthState.cargar_sesion)
def editar() -> rx.Component:
    """Ficha del empleado a pantalla completa (la gestión normal es /empleados/buscar)."""
    return pagina(
        page_heading("Ficha de empleado", "Todos los cambios quedan registrados con fecha y usuario."),
        rx.vstack(
            card(editor_panel(), width="100%"),
            rx.link(rx.button("Volver a la lista", variant="soft"), href="/empleados/buscar"),
            spacing="4",
            width="100%",
        ),
        requiere=("empleados", "ver"),
    )
