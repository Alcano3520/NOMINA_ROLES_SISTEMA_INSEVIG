"""/faltas/individual — Registro Uno a Uno (pestaña 2 del legado)."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.pages.faltas._comunes import buscador_empleado, periodo_picker
from insevig_web.states.auth_state import AuthState
from insevig_web.states.faltas_state import TIPOS_INDIVIDUAL, FaltasState

_S = FaltasState

_SEL = {
    "padding": "6px 8px", "borderRadius": "6px", "width": "100%",
    "border": "1px solid var(--gray-6)", "background": "var(--color-panel-solid)",
    "color": "var(--gray-12)", "fontSize": "14px",
}


def _campo(label: str, control: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", weight="bold", color_scheme="gray"),
        control, spacing="1", width="100%",
    )


def _panel_descuento() -> rx.Component:
    return rx.cond(
        _S.ind_descuento_txt != "",
        rx.box(
            rx.text("Descuento de horas extra por suspensión", size="1", weight="bold"),
            rx.text(_S.ind_descuento_txt, size="2"),
            rx.text("El descuento nunca deja las horas en negativo (corrección del legado).",
                    size="1", color_scheme="gray"),
            background="var(--amber-2)", border="1px solid var(--amber-6)",
            border_radius="8px", padding="10px 12px", width="100%",
        ),
    )


@rx.page(route="/faltas/individual", title="INSEVIG — Faltas · Registro uno a uno",
         on_load=AuthState.cargar_sesion)
def individual() -> rx.Component:
    return pagina(
        page_heading("Registro de falta / permiso / suspensión",
                     "Un empleado a la vez. Soporta suspensión (con descuento opcional de "
                     "horas extra) y levantamiento de suspensión."),
        rx.vstack(
            periodo_picker(),
            buscador_empleado(_S.elegir_emp_individual),
            card(
                rx.vstack(
                    rx.grid(
                        _campo("Código", rx.input(
                            value=_S.ind_codigo, on_change=_S.set_ind_codigo,
                            on_blur=_S.ind_buscar_nombre, size="2",
                        )),
                        _campo("Nombre", rx.input(value=_S.ind_nombre, is_read_only=True, size="2")),
                        _campo("Tipo de registro", rx.el.select(
                            *[rx.el.option(t, value=t) for t in TIPOS_INDIVIDUAL],
                            value=_S.ind_tipo, on_change=_S.set_ind_tipo, style=_SEL,
                        )),
                        _campo("Cantidad (días / faltas)", rx.input(
                            type="number", value=_S.ind_cantidad, on_change=_S.set_ind_cantidad, size="2",
                        )),
                        rx.cond(
                            _S.ind_tipo == "SUSPENSIÓN",
                            _campo("Fecha de inicio", rx.input(
                                type="date", value=_S.ind_fecha_inicio,
                                on_change=_S.set_ind_fecha_inicio, size="2",
                            )),
                            _campo("Fecha del evento", rx.input(
                                type="date", value=_S.ind_fecha_evento,
                                on_change=_S.set_ind_fecha_evento, size="2",
                            )),
                        ),
                        columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                        spacing="3", width="100%",
                    ),
                    _campo("Observación", rx.text_area(
                        value=_S.ind_observ, on_change=_S.set_ind_observ, rows="2", width="100%",
                    )),
                    rx.cond(
                        _S.ind_tipo == "SUSPENSIÓN",
                        rx.checkbox(
                            "Descontar horas extra (HOR25/50/100)",
                            checked=_S.ind_descontar, on_change=_S.toggle_ind_descontar,
                        ),
                    ),
                    rx.divider(),
                    rx.flex(
                        rx.button("Previsualizar", on_click=_S.ind_previsualizar, size="2", variant="soft"),
                        rx.cond(
                            AuthState.permisos_flat.contains("faltas:crear"),
                            primary_button("Registrar", on_click=_S.ind_registrar),
                        ),
                        gap="2", align="center", wrap="wrap",
                    ),
                    rx.cond(_S.ind_error != "", rx.callout(_S.ind_error, color_scheme="red", size="1")),
                    rx.cond(_S.ind_msg != "", rx.callout(_S.ind_msg, color_scheme="green", size="1")),
                    rx.cond(
                        _S.ind_preview_detalle != "",
                        rx.box(
                            rx.text(f"Vista previa: {_S.ind_preview_detalle}", size="2", weight="bold"),
                            rx.text(_S.ind_preview_observ, size="1", color_scheme="gray"),
                            rx.cond(
                                _S.ind_alerta_msg != "",
                                rx.callout(_S.ind_alerta_msg, color_scheme="amber", size="1",
                                           margin_top="0.4rem"),
                            ),
                            background="var(--gray-2)", border="1px solid var(--gray-4)",
                            border_radius="8px", padding="10px 12px", width="100%",
                        ),
                    ),
                    _panel_descuento(),
                    spacing="3", width="100%",
                ),
                width="100%",
            ),
            spacing="4", width="100%",
        ),
        requiere=("faltas", "crear"),
    )
