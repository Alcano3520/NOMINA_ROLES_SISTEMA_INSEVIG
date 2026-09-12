from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.admin_state import AdminState
from insevig_web.states.auth_state import AuthState


@rx.page(
    route="/admin/parametros",
    title="INSEVIG — Parámetros",
    on_load=[AuthState.cargar_sesion, AdminState.cargar_sbu, AdminState.cargar_ia,
             AdminState.cargar_liq_params],
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
        card(
            rx.vstack(
                rx.heading("Parámetros de liquidaciones", size="3"),
                rx.text(
                    "\"⚙ Configuración de Parámetros Anuales\" del sistema original de "
                    "escritorio -- antes fijos en el código, ahora editables acá.",
                    size="1", color_scheme="gray",
                ),
                rx.grid(
                    rx.vstack(
                        rx.text("Aporte IESS personal (%)", size="1", weight="bold"),
                        rx.input(value=AdminState.liq_iess_pct, type="number", width="100%",
                                 on_change=lambda v: AdminState.set_liq_param("iess_pct", v)),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Fondo de Reserva (%)", size="1", weight="bold"),
                        rx.input(value=AdminState.liq_fondo_reserva_pct, type="number", width="100%",
                                 on_change=lambda v: AdminState.set_liq_param("fondo_reserva_pct", v)),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Región por defecto", size="1", weight="bold"),
                        rx.el.select(
                            rx.el.option("COSTA", value="COSTA"), rx.el.option("SIERRA", value="SIERRA"),
                            value=AdminState.liq_region_defecto, width="100%",
                            style={"padding": "6px", "borderRadius": "6px", "border": "1px solid var(--gray-6)"},
                            on_change=lambda v: AdminState.set_liq_param("region_defecto", v),
                        ),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Anticipo — días umbral", size="1", weight="bold"),
                        rx.input(value=AdminState.liq_anticipo_dias_umbral, type="number", width="100%",
                                 on_change=lambda v: AdminState.set_liq_param("anticipo_dias_umbral", v)),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Anticipo — divisor", size="1", weight="bold"),
                        rx.input(value=AdminState.liq_anticipo_divisor, type="number", width="100%",
                                 on_change=lambda v: AdminState.set_liq_param("anticipo_divisor", v)),
                        spacing="1",
                    ),
                    columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                    spacing="3",
                    width="100%",
                ),
                rx.text(
                    "Afecta a toda liquidación calculada de acá en adelante (no recalcula "
                    "retroactivamente las ya guardadas).",
                    size="1", color_scheme="gray",
                ),
                rx.hstack(
                    primary_button("Guardar", on_click=AdminState.guardar_liq_params),
                    rx.cond(AdminState.liq_params_msg != "", rx.badge(AdminState.liq_params_msg)),
                    spacing="2",
                ),
                spacing="3",
                width="100%",
            ),
            width="100%",
        ),
        requiere=("admin", "editar"),
    )
