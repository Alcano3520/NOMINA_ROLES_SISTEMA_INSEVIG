"""Piezas compartidas por las 4 páginas de faltas."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.ui import card
from insevig_web.states.faltas_state import FaltasState

_S = FaltasState

_MESES = [
    ("1", "Enero"), ("2", "Febrero"), ("3", "Marzo"), ("4", "Abril"),
    ("5", "Mayo"), ("6", "Junio"), ("7", "Julio"), ("8", "Agosto"),
    ("9", "Septiembre"), ("10", "Octubre"), ("11", "Noviembre"), ("12", "Diciembre"),
]

_SEL = {
    "padding": "6px 8px", "borderRadius": "6px",
    "border": "1px solid var(--gray-6)", "background": "var(--color-panel-solid)",
    "color": "var(--gray-12)", "fontSize": "14px",
}


def periodo_picker() -> rx.Component:
    """Año + Mes + '→ Vence: fin de mes' (PeriodoPicker del legado)."""
    return card(
        rx.flex(
            rx.vstack(
                rx.text("Año", size="1", weight="bold", color_scheme="gray"),
                rx.input(
                    type="number", value=_S.anio.to_string(),
                    on_change=_S.set_anio, width="110px", size="2",
                ),
                spacing="1",
            ),
            rx.vstack(
                rx.text("Mes", size="1", weight="bold", color_scheme="gray"),
                rx.el.select(
                    *[rx.el.option(nom, value=v) for v, nom in _MESES],
                    value=_S.mes.to_string(),
                    on_change=_S.set_mes,
                    style=_SEL,
                ),
                spacing="1",
            ),
            rx.vstack(
                rx.text("Vence", size="1", weight="bold", color_scheme="gray"),
                rx.badge("→ " + _S.vence_txt, size="2", variant="soft"),
                spacing="1",
            ),
            gap="4", align="end", wrap="wrap",
        ),
        width="100%",
    )


def buscador_empleado(on_elegir) -> rx.Component:
    """Input + Buscar + resultados como botones. `on_elegir(codigo, nombre)`."""
    return card(
        rx.vstack(
            rx.text("Buscar en la nómina", size="1", weight="bold", color_scheme="gray"),
            rx.flex(
                rx.input(
                    value=_S.emp_texto, on_change=_S.set_emp_texto,
                    placeholder="Código, cédula o nombre…", width="100%", size="2",
                ),
                rx.button("Buscar", on_click=_S.buscar_empleado, size="2",
                          loading=_S.emp_buscando),
                gap="2", width="100%",
            ),
            rx.cond(
                _S.emp_resultados.length() > 0,
                rx.vstack(
                    rx.foreach(
                        _S.emp_resultados,
                        lambda e: rx.button(
                            rx.text(f"{e['nombre']}  ·  {e['cedula']}", size="1"),
                            on_click=lambda: on_elegir(e["empleado"], e["nombre"]),
                            variant="ghost", size="1", width="100%",
                            justify="start",
                        ),
                    ),
                    spacing="1", width="100%",
                    max_height="180px", overflow_y="auto",
                ),
            ),
            spacing="2", width="100%",
        ),
        width="100%",
    )


def log_consola(filas: rx.Var) -> rx.Component:
    """Log con tags de color ok/error/warn/info (LogConsola del legado)."""
    colores = {"ok": "grass", "error": "red", "warn": "amber", "info": "gray"}
    return rx.box(
        rx.foreach(
            filas,
            lambda f: rx.text(
                f["texto"], size="1",
                color_scheme=rx.match(f["nivel"], *[(k, v) for k, v in colores.items()], "gray"),
            ),
        ),
        background="var(--gray-2)", border="1px solid var(--gray-4)",
        border_radius="6px", padding="10px 12px", width="100%",
        max_height="220px", overflow_y="auto", font_family="monospace",
    )
