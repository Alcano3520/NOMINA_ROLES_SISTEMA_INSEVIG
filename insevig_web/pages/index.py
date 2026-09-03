from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, stat_card
from insevig_web.registry import MODULES
from insevig_web.states.auth_state import AuthState


def _tarjeta_modulo(spec) -> rx.Component:
    return rx.cond(
        AuthState.permisos_flat.contains(f"{spec.nombre}:ver"),
        rx.link(
            card(
                rx.hstack(
                    rx.icon(spec.icono, size=20),
                    rx.heading(spec.titulo, size="3"),
                    *([] if spec.disponible else [rx.badge("pronto", size="1")]),
                    spacing="2",
                    align="center",
                ),
                width="100%",
            ),
            href=spec.ruta_principal,
            width="100%",
        ),
    )


@rx.page(route="/", title="INSEVIG — Inicio", on_load=AuthState.cargar_sesion)
def index() -> rx.Component:
    return pagina(
        page_heading(
            f"Bienvenido, {AuthState.nombre}",
            "Selecciona un módulo del menú o de los accesos rápidos.",
        ),
        rx.grid(
            stat_card("Empleados", "Personal activo", "—", "users"),
            stat_card("Roles de pago", "Nóminas mensuales", "—", "receipt-text"),
            stat_card("Reportes", "Análisis de nómina", "—", "file-bar-chart"),
            columns=rx.breakpoints(initial="1", sm="2", lg="3"),
            spacing="4",
            width="100%",
            margin_bottom="1.5rem",
        ),
        rx.heading("Módulos", size="4", margin_bottom="0.75rem"),
        rx.grid(
            *[_tarjeta_modulo(m) for m in MODULES],
            columns=rx.breakpoints(initial="1", sm="2", lg="3"),
            spacing="3",
            width="100%",
        ),
    )
