"""Página del módulo Vacaciones — porta las pestañas de `app.py` (Historial/
Gozadas/Pagadas/Cálculo) + Reportes. Ver `insevig_web/states/vacaciones_state.py`."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import (
    card,
    data_table,
    page_heading,
    primary_button,
    scroll_x,
    stat_card,
)
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


# ── Dashboard "Pendientes de Firma" ───────────────────────────────────────
# Porta app.py::_build_tab_dashboard (no depende de empleado seleccionado).

_DASH_CARDS = [
    ("Empleados activos", "dash_n_activos", "blue"),
    ("Gozadas sin firmar", "dash_n_sin_firmar", "red"),
    ("Pagadas sin confirmar", "dash_n_pagadas_sin_firmar", "orange"),
    ("Gozadas registradas (año)", "dash_n_gozadas_anio", "green"),
    ("Pagadas registradas (año)", "dash_n_pagadas_anio", "purple"),
]


def _dash_card(titulo: str, campo: str, color: str) -> rx.Component:
    return card(
        rx.vstack(
            rx.text(titulo, size="1", color_scheme="gray"),
            rx.heading(getattr(_S, campo).to_string(), size="7", color_scheme=color),
            spacing="1",
        ),
        width="100%",
    )


def _fila_top5(r: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.cond(r["tipo"] == "gozada", rx.badge("GOCE"), rx.badge("PAGO", color_scheme="green"))),
        rx.table.cell(r["nombre"]), rx.table.cell(r["periodo"]),
        rx.table.cell(r["desde"]), rx.table.cell(r["hasta"]), rx.table.cell(r["dias"]),
    )


def _fila_periodo_pendiente(p: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(p["periodo"], weight="bold", color_scheme="orange")),
        rx.table.cell(p["n_empleados"].to_string()),
        rx.table.cell(rx.text(p["total_dias"].to_string() + " días",
                              color_scheme="red", weight="bold")),
    )


def _fila_todos_sf(r: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.checkbox(checked=_S.dash_seleccionados.contains(r["vac_id"]),
                       on_change=lambda _v: _S.toggle_seleccion_dash(r["vac_id"]))
        ),
        rx.table.cell(rx.cond(r["tipo"] == "gozada", rx.badge("GOCE"), rx.badge("PAGO", color_scheme="green"))),
        rx.table.cell(r["cedula"]), rx.table.cell(f"{r['apellidos']} {r['nombres']}"),
        rx.table.cell(r["departamento"]), rx.table.cell(r["periodo"]),
        rx.table.cell(r["desde"]), rx.table.cell(r["hasta"]), rx.table.cell(r["dias_tomados"]),
    )


def _panel_ver_todos() -> rx.Component:
    return rx.cond(
        _S.dash_mostrar_todos,
        card(
            rx.vstack(
                rx.hstack(
                    rx.heading("Sin firmar / sin confirmar — personal activo", size="3"),
                    rx.spacer(),
                    rx.text(f"{_S.dash_todos_sf.length()} registros", size="1", color_scheme="gray"),
                    width="100%",
                ),
                rx.hstack(
                    rx.button("Marcar seleccionados como Firmado", color_scheme="green",
                             on_click=_S.marcar_seleccionados_firmado),
                    rx.button("Cerrar", on_click=_S.cerrar_ver_todos_sf, variant="soft"),
                    spacing="2",
                ),
                scroll_x(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(*[rx.table.column_header_cell(c) for c in
                                           ("", "Tipo", "Cédula", "Empleado", "Depto.", "Período", "Desde", "Hasta", "Días")])
                        ),
                        rx.table.body(rx.foreach(_S.dash_todos_sf, _fila_todos_sf)),
                        variant="surface", size="1", width="100%",
                    )
                ),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
    )


def _tab_dashboard() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.spacer(),
            rx.cond(_S.dash_actualizado != "",
                   rx.text(f"Actualizado: {_S.dash_actualizado}", size="1", color_scheme="gray")),
            rx.button("Actualizar", on_click=_S.cargar_dashboard, loading=_S.dash_cargando, size="2"),
            width="100%", align="center",
        ),
        rx.cond(_S.dash_error != "", rx.callout(_S.dash_error, size="1", color_scheme="red")),
        rx.grid(*[_dash_card(t, c, col) for t, c, col in _DASH_CARDS],
               columns=rx.breakpoints(initial="1", sm="2", lg="5"), spacing="3", width="100%"),
        rx.grid(
            card(
                rx.vstack(
                    rx.heading("Sin firmar / sin confirmar (top 5)", size="3"),
                    scroll_x(
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(*[rx.table.column_header_cell(c) for c in
                                               ("Tipo", "Empleado", "Período", "Desde", "Hasta", "Días")])
                            ),
                            rx.table.body(rx.foreach(_S.dash_top5, _fila_top5)),
                            variant="surface", size="1", width="100%",
                        )
                    ),
                    rx.button("Ver todos los sin firmar...", on_click=_S.abrir_ver_todos_sf,
                             color_scheme="red", variant="soft", width="100%"),
                    spacing="2", width="100%",
                ),
                width="100%",
            ),
            card(
                rx.vstack(
                    rx.heading("Vacaciones pendientes — últimos 3 períodos", size="3"),
                    rx.cond(
                        _S.dash_pendientes_periodos.length() > 0,
                        data_table(
                            ["Período", "Empleados", "Días pendientes"],
                            rx.foreach(_S.dash_pendientes_periodos, _fila_periodo_pendiente),
                        ),
                        rx.text("Sin pendientes registrados.", size="1", color_scheme="gray"),
                    ),
                    spacing="2", width="100%",
                ),
                width="100%",
            ),
            columns=rx.breakpoints(initial="1", lg="2"), spacing="3", width="100%",
        ),
        _panel_ver_todos(),
        spacing="3", width="100%",
    )


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
        rx.text(label, size="1", weight="bold", color_scheme="gray"),
        rx.input(value=_S.form_gozada[key], on_change=lambda v, k=key: _S.set_campo_gozada(k, v),
                 type=tipo, size="2", width="100%"),
        spacing="1", width="100%",
    )


def _form_gozada() -> rx.Component:
    return rx.cond(
        _S.mostrar_form_gozada,
        card(
            rx.vstack(
                rx.heading(rx.cond(_S.editando_gozada_id > 0, "Editar vacación gozada", "Nueva vacación gozada"), size="4"),
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
                rx.button("Editar", size="1", variant="soft", on_click=lambda: _S.editar_gozada(v)),
                rx.button("PDF", size="1", variant="soft", on_click=lambda: _S.descargar_comprobante(v["id"])),
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

_CAMPOS_EDITAR_PAGADA = [
    ("periodo", "Período", "text"), ("total_periodo", "Total período ($)", "number"),
    ("vacaciones_calc", "Vacaciones calc. ($)", "number"), ("dias_adicionales", "Días adicionales", "number"),
    ("anticipo", "Anticipo ($)", "number"), ("total_pagar", "TOTAL A PAGAR ($)", "number"),
    ("banco", "Banco", "text"), ("cta_cte_no", "Cta. Cte. No.", "text"),
    ("no_cheque", "No. Cheque/Transferencia", "text"), ("fecha_pago", "Fecha pago", "date"),
    ("observaciones", "Observaciones", "text"),
]


def _form_editar_pagada() -> rx.Component:
    return rx.cond(
        _S.mostrar_form_editar_pagada,
        card(
            rx.vstack(
                rx.heading("Editar vacación pagada", size="4"),
                rx.grid(
                    rx.vstack(rx.text("Forma de pago", size="1", weight="bold", color_scheme="gray"),
                             rx.select(FORMAS_PAGO, value=_S.form_editar_pagada["forma_pago"],
                                      on_change=lambda v: _S.set_campo_editar_pagada("forma_pago", v))),
                    rx.vstack(rx.text("Estado", size="1", weight="bold", color_scheme="gray"),
                             rx.select(ESTADOS_DOC, value=_S.form_editar_pagada["estado_doc"],
                                      on_change=lambda v: _S.set_campo_editar_pagada("estado_doc", v))),
                    *[
                        rx.vstack(
                            rx.text(lbl, size="1", weight="bold", color_scheme="gray"),
                            rx.input(value=_S.form_editar_pagada[k], type=t,
                                     on_change=lambda v, k=k: _S.set_campo_editar_pagada(k, v)),
                            spacing="1", width="100%",
                        )
                        for k, lbl, t in _CAMPOS_EDITAR_PAGADA
                    ],
                    columns=rx.breakpoints(initial="1", sm="2", lg="3"), spacing="3", width="100%",
                ),
                rx.hstack(
                    primary_button("Guardar", on_click=_S.guardar_edicion_pagada),
                    rx.button("Cancelar", on_click=_S.cerrar_form_editar_pagada, variant="soft"),
                    spacing="2",
                ),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
    )


def _form_registrar_pago() -> rx.Component:
    return rx.cond(
        _S.mostrar_form_registrar_pago,
        card(
            rx.vstack(
                rx.heading("Completar pago (cheque)", size="3"),
                rx.text("Ingrese el número de cheque/transferencia para pasar esta pagada a 'completado'.",
                       size="1", color_scheme="gray"),
                rx.grid(
                    rx.vstack(rx.text("Banco", size="1", weight="bold", color_scheme="gray"),
                             rx.input(value=_S.form_registrar_pago["banco"],
                                      on_change=lambda v: _S.set_campo_registrar_pago("banco", v))),
                    rx.vstack(rx.text("No. Cheque/Transferencia", size="1", weight="bold", color_scheme="gray"),
                             rx.input(value=_S.form_registrar_pago["no_cheque"],
                                      on_change=lambda v: _S.set_campo_registrar_pago("no_cheque", v))),
                    rx.vstack(rx.text("Fecha de pago", size="1", weight="bold", color_scheme="gray"),
                             rx.input(value=_S.form_registrar_pago["fecha_pago"], type="date",
                                      on_change=lambda v: _S.set_campo_registrar_pago("fecha_pago", v))),
                    columns=rx.breakpoints(initial="1", sm="3"), spacing="3", width="100%",
                ),
                rx.hstack(
                    primary_button("Confirmar pago", on_click=_S.confirmar_registrar_pago),
                    rx.button("Cancelar", on_click=_S.cerrar_form_registrar_pago, variant="soft"),
                    spacing="2",
                ),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
    )


def _fila_pagada(v: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(v["periodo"]),
        rx.table.cell(v["fecha_pago"]),
        rx.table.cell(v["dias_tomados"]),
        rx.table.cell(f"${v['total_pagar']}"),
        rx.table.cell(v["forma_pago"]),
        rx.table.cell(v["estado_doc"]),
        rx.table.cell(
            rx.hstack(
                rx.cond(v["estado_doc"] == "pendiente",
                        rx.button("Registrar pago", size="1", color_scheme="green",
                                  on_click=lambda: _S.abrir_registrar_pago(v))),
                rx.button("Editar", size="1", variant="soft", on_click=lambda: _S.editar_pagada(v)),
                rx.button("PDF", size="1", variant="soft", on_click=lambda: _S.descargar_comprobante(v["id"])),
                rx.button("Eliminar", size="1", color_scheme="red", variant="soft",
                          on_click=lambda: _S.eliminar_vacacion(v["id"])),
                spacing="1",
            )
        ),
    )


def _tab_pagadas() -> rx.Component:
    return rx.vstack(
        _form_editar_pagada(),
        _form_registrar_pago(),
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(*[rx.table.column_header_cell(c) for c in
                                   ("Período", "Fecha pago", "Días", "Total", "Forma", "Estado", "")])
                ),
                rx.table.body(rx.foreach(_S.pagadas, _fila_pagada)),
                variant="surface", size="1", width="100%",
            )
        ),
        spacing="3", width="100%",
    )


# ── Cálculo ──────────────────────────────────────────────────────────────


def _dialog_anticipo() -> rx.Component:
    """Porta app.py::_dialogo_anticipo (recibo puntual, no persiste nada)."""
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Comprobante de Anticipo"),
            rx.alert_dialog.description(
                rx.vstack(
                    rx.text(f"${_S.form_pago['anticipo']}", size="6", weight="bold", color_scheme="green"),
                    rx.vstack(
                        rx.text("Fecha del comprobante", size="1", weight="bold", color_scheme="gray"),
                        rx.input(value=_S.anticipo_fecha, type="date", on_change=_S.set_anticipo_fecha),
                        spacing="1", width="100%",
                    ),
                    spacing="3", width="100%",
                ),
            ),
            rx.hstack(
                rx.button("Cancelar", on_click=_S.cerrar_dialogo_anticipo, variant="soft"),
                rx.button("Generar comprobante", on_click=_S.descargar_comprobante_anticipo, color_scheme="green"),
                spacing="3", justify="end", margin_top="1rem",
            ),
        ),
        open=_S.mostrar_dialogo_anticipo,
    )


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
                    rx.hstack(
                        rx.vstack(rx.text("Días gozados", size="1", weight="bold", color_scheme="gray"),
                                  rx.input(value=_S.calc_dias_gozados.to_string(), type="number",
                                           on_change=lambda v: _S.set_calc_dias("gozados", v),
                                           size="1", width="6em")),
                        rx.vstack(rx.text("Días adicionales Art.69", size="1", weight="bold", color_scheme="gray"),
                                  rx.input(value=_S.calc_dias_adicionales.to_string(), type="number",
                                           on_change=lambda v: _S.set_calc_dias("adicionales", v),
                                           size="1", width="6em")),
                        rx.vstack(rx.text("Días a pagar", size="1", weight="bold", color_scheme="gray"),
                                  rx.text(_S.calc_resultado["dias_a_pagar"], size="2")),
                        spacing="2", wrap="wrap", align="end",
                    ),
                    rx.text("Podés editar los días o un mes de la tabla — el total se recalcula solo.",
                            size="1", color_scheme="gray"),
                    scroll_x(rx.table.root(
                        rx.table.header(rx.table.row(*[
                            rx.table.column_header_cell(c) for c in ("Mes", "Total del mes ($)")
                        ])),
                        rx.table.body(rx.foreach(
                            _S.calc_detalles,
                            lambda m, i: rx.table.row(
                                rx.table.cell(m["fecha_mes"]),
                                rx.table.cell(rx.input(
                                    value=m["total_mes"].to_string(), type="number", size="1", width="120px",
                                    on_change=lambda v: _S.set_calc_mes(i, v),
                                )),
                            ),
                        )),
                        variant="surface", size="1",
                    )),
                    rx.hstack(rx.text("Total período (12m):", weight="bold"),
                              rx.text(f"${_S.calc_resultado['total_periodo']}")),
                    rx.hstack(rx.text("Vacaciones calc. (total/24):", weight="bold"),
                              rx.text(f"${_S.calc_resultado['vacaciones_calc']}")),
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
                    rx.vstack(rx.text("Forma de pago", size="1", weight="bold", color_scheme="gray"),
                             rx.select(FORMAS_PAGO, value=_S.form_pago["forma_pago"],
                                      on_change=lambda v: _S.set_campo_pago("forma_pago", v))),
                    rx.vstack(rx.text("Banco", size="1", weight="bold", color_scheme="gray"),
                             rx.input(value=_S.form_pago["banco"], on_change=lambda v: _S.set_campo_pago("banco", v))),
                    rx.vstack(rx.text("Cta. Cte. No.", size="1", weight="bold", color_scheme="gray"),
                             rx.input(value=_S.form_pago["cta_cte_no"], on_change=lambda v: _S.set_campo_pago("cta_cte_no", v))),
                    rx.vstack(rx.text("No. Cheque/Transferencia", size="1", weight="bold", color_scheme="gray"),
                             rx.input(value=_S.form_pago["no_cheque"], on_change=lambda v: _S.set_campo_pago("no_cheque", v))),
                    rx.vstack(rx.text("Fecha de pago", size="1", weight="bold", color_scheme="gray"),
                             rx.input(value=_S.form_pago["fecha_pago"], type="date",
                                      on_change=lambda v: _S.set_campo_pago("fecha_pago", v))),
                    rx.vstack(rx.text("Anticipo ($)", size="1", weight="bold", color_scheme="gray"),
                             rx.input(value=_S.form_pago["anticipo"], type="number",
                                      on_change=lambda v: _S.set_campo_pago("anticipo", v))),
                    rx.vstack(rx.text("Observaciones", size="1", weight="bold", color_scheme="gray"),
                             rx.input(value=_S.form_pago["observaciones"],
                                      on_change=lambda v: _S.set_campo_pago("observaciones", v))),
                    columns=rx.breakpoints(initial="1", sm="2", lg="3"), spacing="3", width="100%",
                ),
                rx.hstack(
                    primary_button("Crear vacación pagada", on_click=_S.registrar_pagada),
                    rx.cond(
                        _S.form_pago["anticipo"].to(float) > 0,
                        rx.button("Comprobante de anticipo", on_click=_S.abrir_dialogo_anticipo, variant="soft"),
                    ),
                    spacing="2",
                ),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
        _dialog_anticipo(),
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
        rx.divider(margin_y="0.5rem"),
        rx.heading("Vacaciones pendientes (global)", size="3"),
        rx.text(
            "Días de vacaciones pendientes por empleado y período, para todo el personal activo.",
            size="1", color_scheme="gray",
        ),
        rx.hstack(
            rx.input(placeholder="Departamento (opcional)", value=_S.pg_departamento,
                     on_change=_S.set_pg_departamento, width="16em"),
            rx.select(["3", "4", "5", "6", "8", "10"], value=_S.pg_n_periodos,
                      on_change=_S.set_pg_n_periodos, width="7em"),
            rx.checkbox("Solo 15 días base", checked=_S.pg_solo_15, on_change=_S.set_pg_solo_15),
            primary_button("Cargar", on_click=_S.cargar_pendientes_global, loading=_S.pg_cargando),
            rx.button("Exportar Excel", on_click=_S.exportar_pendientes_global, variant="soft"),
            spacing="2", wrap="wrap", align="center",
        ),
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(*[rx.table.column_header_cell(c) for c in
                                   ("Cédula", "Nombre", "Departamento", "Período", "Derecho", "Gozados", "Pendientes")])
                ),
                rx.table.body(rx.foreach(_S.pg_filas, _fila_pendiente_global)),
                variant="surface", size="1", width="100%",
            )
        ),
        spacing="3", width="100%",
    )


def _fila_pendiente_global(f: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(f["cedula"]),
        rx.table.cell(f"{f['apellidos']} {f['nombres']}"),
        rx.table.cell(f["departamento"]),
        rx.table.cell(f["periodo"]),
        rx.table.cell(f["dias_derecho"].to_string()),
        rx.table.cell(f["dias_gozados"].to_string()),
        rx.table.cell(f["dias_pendientes"].to_string()),
    )


def _fila_periodo_anterior(p: rx.Var) -> rx.Component:
    return rx.text(f"• {p['periodo']}  ({p['dias_pendientes']} días pendientes)", size="2")


def _dialog_confirmar_periodo() -> rx.Component:
    """Porta app.py::_confirmar_periodo_prioritario (bloqueaba con messagebox.askyesno)."""
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Períodos anteriores pendientes"),
            rx.alert_dialog.description(
                rx.vstack(
                    rx.text("El empleado tiene período(s) anteriores sin registrar:"),
                    rx.vstack(rx.foreach(_S.confirmar_periodo_detalle, _fila_periodo_anterior), spacing="1"),
                    rx.text("¿Desea continuar guardando este período sin registrar los anteriores primero?"),
                    spacing="3",
                ),
            ),
            rx.hstack(
                rx.button("No, cancelar", on_click=_S.confirmar_periodo_cancelar, variant="soft"),
                rx.button("Sí, guardar igual", on_click=_S.confirmar_periodo_continuar, color_scheme="amber"),
                spacing="3", justify="end", margin_top="1rem",
            ),
        ),
        open=_S.mostrar_confirmar_periodo,
    )


@rx.page(
    route="/vacaciones",
    title="INSEVIG — Vacaciones",
    on_load=[AuthState.cargar_sesion, VacacionesState.cargar_dashboard],
)
def index() -> rx.Component:
    return pagina(
        page_heading("Vacaciones", "Registro de vacaciones gozadas y pagadas — Art. 69/71/76 CT Ecuador."),
        rx.cond(_S.msg != "", rx.callout(_S.msg, size="1")),
        _dialog_confirmar_periodo(),
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("Pendientes de Firma", value="dashboard"),
                rx.tabs.trigger("Buscar", value="buscar"),
                rx.tabs.trigger("Resumen", value="resumen"),
                rx.tabs.trigger("Gozadas", value="gozadas"),
                rx.tabs.trigger("Pagadas", value="pagadas"),
                rx.tabs.trigger("Cálculo", value="calculo"),
                rx.tabs.trigger("Reportes", value="reportes"),
            ),
            rx.tabs.content(_tab_dashboard(), value="dashboard"),
            rx.tabs.content(_tab_buscar(), value="buscar"),
            rx.tabs.content(_tab_resumen(), value="resumen"),
            rx.tabs.content(_tab_gozadas(), value="gozadas"),
            rx.tabs.content(_tab_pagadas(), value="pagadas"),
            rx.tabs.content(_tab_calculo(), value="calculo"),
            rx.tabs.content(_tab_reportes(), value="reportes"),
            value=_S.tab, on_change=_S.set_tab, default_value="dashboard", width="100%",
        ),
        requiere=("vacaciones", "ver"),
    )
