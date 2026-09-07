"""Página del módulo Vacaciones — porta las pestañas de `app.py` (Historial/
Gozadas/Pagadas/Cálculo) + Reportes. Ver `insevig_web/states/vacaciones_state.py`."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x, stat_card
from insevig_web.states.auth_state import AuthState
from insevig_web.states.vacaciones_state import (
    ESTADOS_DOC,
    FORMAS_PAGO,
    VacacionesState,
)

_S = VacacionesState

_CAMPOS_GOZADA = [
    ("periodo", "Período (ej. 2024-2025)", "text"),
    ("fecha_comprobante", "Fecha comprobante", "date"),
    ("desde", "Desde", "date"),
    ("hasta", "Hasta", "date"),
    ("dias_tomados", "Días tomados", "number"),
    ("dias_adicionales", "Días adicionales Art.69", "number"),
    ("lo_cubrio_agente", "Lo cubrió agente", "text"),
    ("referencia", "Referencia", "text"),
    ("observaciones", "Observaciones", "text"),
]


# ── Buscar ───────────────────────────────────────────────────────────────


def _fila_resultado(emp: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(emp["cedula"]),
        rx.table.cell(f"{emp['apellidos']} {emp['nombres']}"),
        rx.table.cell(emp["cargo"]),
        rx.table.cell(emp["departamento"]),
        rx.table.cell(rx.button("Seleccionar", size="1", on_click=lambda: _S.seleccionar(emp))),
    )


def _tab_buscar() -> rx.Component:
    return card(
        rx.vstack(
            rx.hstack(
                rx.input(
                    placeholder="Cédula o apellidos/nombres...",
                    value=_S.query, on_change=_S.set_query,
                    on_key_down=lambda k: rx.cond(k == "Enter", _S.buscar(), rx.noop()),
                    width="100%",
                ),
                primary_button("Buscar", on_click=_S.buscar, loading=_S.buscando),
                width="100%", spacing="2",
            ),
            rx.cond(_S.error != "", rx.callout(_S.error, size="1", color_scheme="red")),
            rx.cond(
                _S.resultados.length() > 0,
                scroll_x(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(*[rx.table.column_header_cell(c) for c in
                                           ("Cédula", "Nombre", "Cargo", "Departamento", "")])
                        ),
                        rx.table.body(rx.foreach(_S.resultados, _fila_resultado)),
                        variant="surface", size="1", width="100%",
                    )
                ),
            ),
            spacing="3", width="100%",
        ),
        width="100%",
    )


# ── Resumen ──────────────────────────────────────────────────────────────


def _panel_alertas() -> rx.Component:
    return rx.cond(
        (_S.alertas["pendientes"].length() > 0) | (_S.alertas["sin_firmar"].length() > 0),
        card(
            rx.vstack(
                rx.cond(
                    _S.alertas["pendientes"].length() > 0,
                    rx.callout(
                        rx.foreach(_S.alertas["pendientes"],
                                   lambda p: rx.text(f"Período {p['periodo']}: {p['dias_pendientes']} día(s) pendiente(s).")),
                        color_scheme="amber", icon="triangle_alert",
                    ),
                ),
                rx.cond(
                    _S.alertas["sin_firmar"].length() > 0,
                    rx.callout(
                        f"{_S.alertas['sin_firmar'].length()} gozada(s) sin firmar/confirmar.",
                        color_scheme="amber", icon="triangle_alert",
                    ),
                ),
                spacing="2", width="100%",
            ),
            width="100%",
        ),
    )


def _tab_resumen() -> rx.Component:
    return rx.vstack(
        rx.cond(
            _S.empleado,
            rx.heading(f"{_S.empleado['apellidos']} {_S.empleado['nombres']} — {_S.empleado['cedula']}", size="4"),
            rx.text("Seleccione un empleado en la pestaña Buscar.", color_scheme="gray"),
        ),
        _panel_alertas(),
        rx.grid(
            stat_card("Días gozados", "Total histórico", _S.resumen["dias_gozados"].to_string(), "calendar-check"),
            stat_card("Pagadas", f"{_S.resumen['pagada_count']} registro(s)", f"${_S.resumen['total_pagado']}", "dollar-sign"),
            stat_card("Pendientes", "Sin completar", _S.resumen["pendientes"].to_string(), "clock"),
            columns=rx.breakpoints(initial="1", sm="3"), spacing="3", width="100%",
        ),
        spacing="3", width="100%",
    )


# ── Gozadas ──────────────────────────────────────────────────────────────


def _campo_gozada(key: str, label: str, tipo: str) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", weight="bold"),
        rx.input(value=_S.form_gozada[key], on_change=lambda v, k=key: _S.set_campo_gozada(k, v),
                 type=tipo, size="2", width="100%"),
        spacing="1", width="100%",
    )


def _form_gozada() -> rx.Component:
    return rx.cond(
        _S.mostrar_form_gozada,
        card(
            rx.vstack(
                rx.heading("Nueva vacación gozada", size="3"),
                rx.grid(*[_campo_gozada(k, lbl, t) for k, lbl, t in _CAMPOS_GOZADA],
                        columns=rx.breakpoints(initial="1", sm="2", lg="3"), spacing="3", width="100%"),
                rx.hstack(
                    primary_button("Guardar", on_click=_S.guardar_gozada),
                    rx.button("Cancelar", on_click=_S.cerrar_form_gozada, variant="soft"),
                    spacing="2",
                ),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
    )


def _fila_gozada(v: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(v["periodo"]),
        rx.table.cell(v["desde"]),
        rx.table.cell(v["hasta"]),
        rx.table.cell(v["dias_tomados"]),
        rx.table.cell(v["estado_doc"]),
        rx.table.cell(rx.cond(v["firmado"] == "POSITIVO", rx.badge("Firmado", color_scheme="green"),
                              rx.badge("Sin firmar", color_scheme="amber"))),
        rx.table.cell(
            rx.hstack(
                rx.cond(v["firmado"] != "POSITIVO",
                        rx.button("Firmar", size="1", on_click=lambda: _S.firmar_gozada(v["id"]))),
                rx.button("Eliminar", size="1", color_scheme="red", variant="soft",
                          on_click=lambda: _S.eliminar_vacacion(v["id"])),
                spacing="1",
            )
        ),
    )


def _tab_gozadas() -> rx.Component:
    return rx.vstack(
        rx.hstack(rx.spacer(), primary_button("+ Nueva gozada", on_click=_S.nueva_gozada,
                                              disabled=~rx.cond(_S.empleado, True, False)), width="100%"),
        _form_gozada(),
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(*[rx.table.column_header_cell(c) for c in
                                   ("Período", "Desde", "Hasta", "Días", "Estado", "Firma", "")])
                ),
                rx.table.body(rx.foreach(_S.gozadas, _fila_gozada)),
                variant="surface", size="1", width="100%",
            )
        ),
        spacing="3", width="100%",
    )


# ── Pagadas ──────────────────────────────────────────────────────────────


def _fila_pagada(v: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(v["periodo"]),
        rx.table.cell(v["fecha_pago"]),
        rx.table.cell(v["dias_tomados"]),
        rx.table.cell(f"${v['total_pagar']}"),
        rx.table.cell(v["forma_pago"]),
        rx.table.cell(v["estado_doc"]),
    )


def _tab_pagadas() -> rx.Component:
    return scroll_x(
        rx.table.root(
            rx.table.header(
                rx.table.row(*[rx.table.column_header_cell(c) for c in
                               ("Período", "Fecha pago", "Días", "Total", "Forma", "Estado")])
            ),
            rx.table.body(rx.foreach(_S.pagadas, _fila_pagada)),
            variant="surface", size="1", width="100%",
        )
    )


# ── Cálculo ──────────────────────────────────────────────────────────────


def _tab_calculo() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.select(_S.periodos_emp, value=_S.calc_periodo,
                     on_change=_S.set_calc_periodo, placeholder="Período a calcular"),
            primary_button("Calcular", on_click=_S.calcular, loading=_S.calc_cargando),
            spacing="2",
        ),
        rx.cond(
            _S.calc_resultado,
            card(
                rx.vstack(
                    rx.hstack(rx.text("Días gozados:", weight="bold"), rx.text(_S.calc_dias_gozados)),
                    rx.hstack(rx.text("Días adicionales (Art.69):", weight="bold"), rx.text(_S.calc_dias_adicionales)),
                    rx.hstack(rx.text("Días a pagar:", weight="bold"), rx.text(_S.calc_resultado["dias_a_pagar"])),
                    rx.hstack(rx.text("Total período (12m):", weight="bold"), rx.text(f"${_S.calc_resultado['total_periodo']}")),
                    rx.hstack(rx.text("Vacaciones calc. (total/24):", weight="bold"), rx.text(f"${_S.calc_resultado['vacaciones_calc']}")),
                    rx.hstack(rx.text("TOTAL A PAGAR:", weight="bold", size="4"),
                             rx.text(f"${_S.calc_resultado['total_pagar']}", size="4", color_scheme="green")),
                    spacing="2", width="100%",
                ),
                width="100%",
            ),
        ),
        card(
            rx.vstack(
                rx.heading("Datos de pago", size="3"),
                rx.grid(
                    rx.vstack(rx.text("Forma de pago", size="1", weight="bold"),
                             rx.select(FORMAS_PAGO, value=_S.form_pago["forma_pago"],
                                      on_change=lambda v: _S.set_campo_pago("forma_pago", v))),
                    rx.vstack(rx.text("Banco", size="1", weight="bold"),
                             rx.input(value=_S.form_pago["banco"], on_change=lambda v: _S.set_campo_pago("banco", v))),
                    rx.vstack(rx.text("Cta. Cte. No.", size="1", weight="bold"),
                             rx.input(value=_S.form_pago["cta_cte_no"], on_change=lambda v: _S.set_campo_pago("cta_cte_no", v))),
                    rx.vstack(rx.text("No. Cheque/Transferencia", size="1", weight="bold"),
                             rx.input(value=_S.form_pago["no_cheque"], on_change=lambda v: _S.set_campo_pago("no_cheque", v))),
                    rx.vstack(rx.text("Fecha de pago", size="1", weight="bold"),
                             rx.input(value=_S.form_pago["fecha_pago"], type="date",
                                      on_change=lambda v: _S.set_campo_pago("fecha_pago", v))),
                    rx.vstack(rx.text("Anticipo ($)", size="1", weight="bold"),
                             rx.input(value=_S.form_pago["anticipo"], type="number",
                                      on_change=lambda v: _S.set_campo_pago("anticipo", v))),
                    rx.vstack(rx.text("Observaciones", size="1", weight="bold"),
                             rx.input(value=_S.form_pago["observaciones"],
                                      on_change=lambda v: _S.set_campo_pago("observaciones", v))),
                    columns=rx.breakpoints(initial="1", sm="2", lg="3"), spacing="3", width="100%",
                ),
                primary_button("Crear vacación pagada", on_click=_S.registrar_pagada),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
        spacing="3", width="100%",
    )


# ── Reportes ─────────────────────────────────────────────────────────────


def _fila_reporte(r: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(r["cedula"]), rx.table.cell(f"{r['apellidos']} {r['nombres']}"),
        rx.table.cell(r["periodo"]),
        rx.table.cell(rx.cond(r["tipo"] == "gozada", rx.badge("GOCE"), rx.badge("PAGO", color_scheme="green"))),
        rx.table.cell(r["estado_doc"]), rx.table.cell(r["dias_tomados"]),
        rx.table.cell(f"${r['total_pagar']}"),
    )


def _tab_reportes() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.select(["(todos)", *ESTADOS_DOC], value=rx.cond(_S.rep_estado == "", "(todos)", _S.rep_estado),
                     on_change=_S.set_rep_estado, placeholder="Estado"),
            rx.input(placeholder="Período (ej. 2024-2025)", value=_S.rep_periodo, on_change=_S.set_rep_periodo, width="14em"),
            primary_button("Cargar", on_click=_S.cargar_reporte, loading=_S.rep_cargando),
            rx.button("Exportar Excel", on_click=_S.exportar_excel, variant="soft"),
            spacing="2", wrap="wrap",
        ),
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(*[rx.table.column_header_cell(c) for c in
                                   ("Cédula", "Nombre", "Período", "Tipo", "Estado", "Días", "Total")])
                ),
                rx.table.body(rx.foreach(_S.rep_filas, _fila_reporte)),
                variant="surface", size="1", width="100%",
            )
        ),
        spacing="3", width="100%",
    )


@rx.page(
    route="/vacaciones",
    title="INSEVIG — Vacaciones",
    on_load=AuthState.cargar_sesion,
)
def index() -> rx.Component:
    return pagina(
        page_heading("Vacaciones", "Registro de vacaciones gozadas y pagadas — Art. 69/71/76 CT Ecuador."),
        rx.cond(_S.msg != "", rx.callout(_S.msg, size="1")),
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("Buscar", value="buscar"),
                rx.tabs.trigger("Resumen", value="resumen"),
                rx.tabs.trigger("Gozadas", value="gozadas"),
                rx.tabs.trigger("Pagadas", value="pagadas"),
                rx.tabs.trigger("Cálculo", value="calculo"),
                rx.tabs.trigger("Reportes", value="reportes"),
            ),
            rx.tabs.content(_tab_buscar(), value="buscar"),
            rx.tabs.content(_tab_resumen(), value="resumen"),
            rx.tabs.content(_tab_gozadas(), value="gozadas"),
            rx.tabs.content(_tab_pagadas(), value="pagadas"),
            rx.tabs.content(_tab_calculo(), value="calculo"),
            rx.tabs.content(_tab_reportes(), value="reportes"),
            value=_S.tab, on_change=_S.set_tab, default_value="buscar", width="100%",
        ),
        requiere=("vacaciones", "ver"),
    )
