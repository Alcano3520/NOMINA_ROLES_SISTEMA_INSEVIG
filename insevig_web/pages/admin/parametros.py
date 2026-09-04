from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.admin_state import AdminState
from insevig_web.states.auth_state import AuthState


@rx.page(
    route="/admin/parametros",
    title="INSEVIG — Parámetros",
    on_load=[AuthState.cargar_sesion, AdminState.cargar_sbu, AdminState.cargar_ia],
)
def parametros() -> rx.Component:
    return pagina(
        page_heading("Parámetros de negocio", "Valores que usa el sistema para los cálculos."),
        card(
            rx.vstack(
                rx.heading("Narrativa por IA (Préstamos)", size="3"),
                rx.text(
                    "Genera un resumen en lenguaje sencillo del comportamiento de pago. "
                    "Para uso sin Internet: proveedor 'ollama' apuntando a un servidor local.",
                    size="1", color_scheme="gray",
                ),
                rx.grid(
                    rx.vstack(
                        rx.text("Proveedor", size="1", weight="bold"),
                        rx.el.select(
                            *[rx.el.option(o, value=o) for o in ("none", "groq", "openrouter", "ollama")],
                            value=AdminState.ia_provider,
                            on_change=lambda v: AdminState.set_ia("provider", v),
                            style={"width": "100%", "padding": "6px", "borderRadius": "6px",
                                   "border": "1px solid var(--gray-6)"},
                        ),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("URL base (ollama)", size="1", weight="bold"),
                        rx.input(value=AdminState.ia_base_url,
                                 on_change=lambda v: AdminState.set_ia("base_url", v),
                                 placeholder="http://localhost:11434", width="100%"),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Modelo", size="1", weight="bold"),
                        rx.input(value=AdminState.ia_model,
                                 on_change=lambda v: AdminState.set_ia("model", v),
                                 placeholder="llama3.1", width="100%"),
                        spacing="1",
                    ),
                    columns=rx.breakpoints(initial="1", sm="3"),
                    spacing="3",
                    width="100%",
                ),
                rx.text("Clave de API: " + AdminState.ia_key_estado + " (se configura en el archivo .env del servidor).",
                        size="1", color_scheme="gray"),
                rx.hstack(
                    primary_button("Guardar", on_click=AdminState.guardar_ia),
                    rx.cond(AdminState.ia_msg != "", rx.badge(AdminState.ia_msg)),
                    spacing="2",
                ),
                spacing="3",
                width="100%",
            ),
            width="100%",
        ),
        card(
            rx.vstack(
                rx.heading("Salario Básico Unificado (SBU) por año", size="3"),
                rx.text("Lo usa el cálculo de la décima cuarta remuneración en Liquidaciones.",
                        size="1", color_scheme="gray"),
                rx.grid(
                    rx.foreach(
                        AdminState.sbu,
                        lambda x: rx.vstack(
                            rx.text(x["anio"], size="1", weight="bold"),
                            rx.input(
                                value=x["valor"],
                                on_change=lambda v: AdminState.set_sbu_valor(x["anio"], v),
                                type="number",
                                width="100%",
                            ),
                            spacing="1",
                        ),
                    ),
                    columns=rx.breakpoints(initial="2", sm="4", lg="6"),
                    spacing="3",
                    width="100%",
                ),
                rx.hstack(
                    primary_button("Guardar", on_click=AdminState.guardar_sbu),
                    rx.cond(AdminState.sbu_msg != "", rx.badge(AdminState.sbu_msg)),
                    spacing="2",
                ),
                spacing="3",
                width="100%",
            ),
            width="100%",
        ),
        requiere=("admin", "editar"),
    )
