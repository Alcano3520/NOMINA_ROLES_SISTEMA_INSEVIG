from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.job_progress import job_progress
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.registrador_state import (
    CLASES_CONSULTA,
    CLASES_OPCIONES,
    RegistradorState,
)

_S = RegistradorState
_SEL = {
    "padding": "6px", "borderRadius": "6px", "border": "1px solid var(--gray-6)",
    "background": "#fff", "color": "#1f2937",
}


def _msg() -> rx.Component:
    return rx.fragment(
        rx.cond(_S.error != "", rx.callout(_S.error, color_scheme="red", size="1")),
        rx.cond(_S.resultado != "", rx.callout(_S.resultado, color_scheme="green", size="1")),
    )


def _buscador_empleado() -> rx.Component:
    return card(
        rx.vstack(
            rx.hstack(
                rx.input(value=_S.busca, on_change=_S.set_busca,
                         placeholder="Empleado: código, cédula o nombre…", width="100%", size="2"),
                rx.button("Buscar", on_click=_S.buscar_emp, size="2"),
                spacing="2", width="100%",
            ),
            rx.cond(
                _S.encontrados.length() > 0,
                rx.vstack(
                    rx.foreach(
                        _S.encontrados,
                        lambda e: rx.box(
                            rx.text(f"{e['empleado']} — {e['apellidos_nombres']} ({e['cedula']})", size="1"),
                            on_click=lambda: _S.elegir_emp(e["empleado"], e["apellidos_nombres"]),
                            padding="4px 6px", cursor="pointer", border_radius="4px",
                            _hover={"background": "var(--accent-3)"},
                        ),
                    ),
                    spacing="1", width="100%", max_height="180px", overflow_y="auto",
                ),
            ),
            rx.cond(
                _S.emp_sel != "",
                rx.badge(f"Empleado: {_S.emp_sel} — {_S.emp_nombre}", color_scheme="blue", size="2"),
            ),
            spacing="2", width="100%",
        ),
        width="100%",
    )


def _tabla(cols: list[str], filas: rx.Var, fila_fn) -> rx.Component:
    return scroll_x(
        rx.table.root(
            rx.table.header(rx.table.row(*[
                rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                for c in cols
            ])),
            rx.table.body(rx.foreach(filas, fila_fn)),
            variant="surface", size="1", width="100%",
        )
    )


# ── 1. Préstamo individual ──────────────────────────────────────────────
def _panel_movimientos_emp() -> rx.Component:
    """Historial de registros vigentes del empleado elegido (como el panel lateral
    de las pestañas Préstamo / Egresos-Ingresos del sistema anterior)."""
    return rx.cond(
        (_S.emp_sel != "") & (_S.emp_movimientos.length() > 0),
        card(
            rx.vstack(
                rx.heading("Movimientos vigentes de " + _S.emp_nombre, size="2"),
                _tabla(
                    ["N°", "Tipo", "Fecha", "Valor", "Cuotas"],
                    _S.emp_movimientos,
                    lambda m: rx.table.row(
                        rx.table.cell(m["numero"]),
                        rx.table.cell(m["tipo_clase"]),
                        rx.table.cell(m["fecha"]),
                        rx.table.cell("$" + m["valor"].to_string()),
                        rx.table.cell(m["cuotas"].to_string()),
                    ),
                ),
                spacing="2", width="100%",
            ),
            width="100%",
        ),
    )


def _panel_proyeccion() -> rx.Component:
    return rx.cond(
        _S.p_proyeccion.length() > 0,
        card(
            rx.vstack(
                rx.hstack(
                    rx.heading("Carga programada del empleado", size="2"),
                    rx.spacer(),
                    rx.button("Actualizar", on_click=_S.refrescar_proyeccion, size="1", variant="ghost"),
                    width="100%",
                ),
                rx.text("Descuentos de préstamo ya agendados por mes. Úsalo para elegir la cuota.",
                        size="1", color_scheme="gray"),
                _tabla(
                    ["Mes", "Ya agendado"],
                    _S.p_proyeccion,
                    lambda p: rx.table.row(
                        rx.table.cell(p["mes"]),
                        rx.table.cell("$" + p["valor"].to_string()),
                    ),
                ),
                spacing="2", width="100%",
            ),
            width="100%",
        ),
    )


def _tab_prestamo() -> rx.Component:
    return rx.vstack(
        _buscador_empleado(),
        _panel_movimientos_emp(),
        _panel_proyeccion(),
        card(
            rx.vstack(
                rx.grid(
                    rx.vstack(rx.text("Valor total del préstamo", size="1", weight="bold"),
                              rx.input(value=_S.p_valor, on_change=lambda v: _S.set_p("valor", v),
                                       type="number", width="100%"), spacing="1"),
                    rx.vstack(rx.text("Fecha de emisión", size="1", weight="bold"),
                              rx.input(value=_S.p_fecha, on_change=lambda v: _S.set_p("fecha", v),
                                       type="date", width="100%"), spacing="1"),
                    columns=rx.breakpoints(initial="1", sm="2"), spacing="3", width="100%",
                ),
                rx.hstack(
                    rx.text("Planificar por:", size="1", weight="bold"),
                    rx.el.select(
                        rx.el.option("Número de cuotas", value="cuotas"),
                        rx.el.option("Cuota mensual fija", value="valor"),
                        value=_S.p_modo, on_change=lambda v: _S.set_p("modo", v), style=_SEL,
                    ),
                    rx.cond(
                        _S.p_modo == "cuotas",
                        rx.input(value=_S.p_num_cuotas, on_change=lambda v: _S.set_p("num_cuotas", v),
                                 type="number", width="90px", placeholder="cuotas"),
                        rx.input(value=_S.p_cuota_mensual, on_change=lambda v: _S.set_p("cuota_mensual", v),
                                 type="number", width="120px", placeholder="$/mes"),
                    ),
                    rx.button("Calcular cuotas", on_click=_S.calcular_cuotas, variant="soft", size="1"),
                    spacing="2", align="end", wrap="wrap",
                ),
                rx.text_area(value=_S.p_observ, on_change=lambda v: _S.set_p("observ", v),
                             placeholder="Observación (opcional)", rows="2", width="100%"),
                rx.cond(_S.p_aviso != "", rx.callout(_S.p_aviso, color_scheme="amber", size="1")),
                rx.cond(
                    _S.p_preview.length() > 0,
                    rx.vstack(
                        rx.text("Puedes ajustar el valor de una cuota antes de registrar.",
                                size="1", color_scheme="gray"),
                        scroll_x(
                            rx.table.root(
                                rx.table.header(rx.table.row(*[
                                    rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                                    for c in ("Cuota", "Vence", "Valor")
                                ])),
                                rx.table.body(
                                    rx.foreach(
                                        _S.p_preview,
                                        lambda c, i: rx.table.row(
                                            rx.table.cell(c["secuencia"].to_string()),
                                            rx.table.cell(
                                                rx.input(
                                                    value=c["fecha_vencimiento"], type="date",
                                                    on_change=lambda v: _S.set_preview_cuota(i, "fecha_vencimiento", v),
                                                    size="1", width="150px",
                                                )
                                            ),
                                            rx.table.cell(
                                                rx.input(
                                                    value=c["valor"].to_string(), type="number",
                                                    on_change=lambda v: _S.set_preview_cuota(i, "valor", v),
                                                    size="1", width="110px",
                                                )
                                            ),
                                        ),
                                    )
                                ),
                                variant="surface", size="1", width="100%",
                            )
                        ),
                        rx.text("Total cuotas: $" + _S.p_preview_total.to_string(), weight="bold", size="2"),
                        rx.cond(
                            AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                            primary_button("Registrar préstamo", on_click=_S.guardar_prestamo),
                        ),
                        spacing="2", width="100%",
                    ),
                ),
                _msg(),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
        spacing="4", width="100%",
    )


def _celda(fila, i, campo, set_fn, *, tipo="text", w="110px", readonly=False, opciones=None):
    if opciones is not None:
        return rx.table.cell(
            rx.el.select(
                *[rx.el.option(o["etiqueta"], value=o["codigo"]) for o in opciones],
                value=fila[campo], on_change=lambda v: set_fn(i, campo, v),
                style={**_SEL, "minWidth": "150px"},
            )
        )
    return rx.table.cell(
        rx.input(
            value=fila[campo], type=tipo, size="1", width=w, read_only=readonly,
            on_change=lambda v: set_fn(i, campo, v),
        )
    )


def _grilla(cabeceras, filas_var, fila_fn) -> rx.Component:
    return scroll_x(
        rx.table.root(
            rx.table.header(rx.table.row(*[
                rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                for c in [*cabeceras, ""]
            ])),
            rx.table.body(rx.foreach(filas_var, fila_fn)),
            variant="surface", size="1", width="100%",
        )
    )


# ── 2. Carga masiva de préstamos (grilla editable + pegar de Excel) ─────
def _tab_masiva() -> rx.Component:
    def _fila(f, i):
        return rx.table.row(
            _celda(f, i, "codigo", _S.pm_set_celda, w="120px"),
            rx.table.cell(rx.text(f["nombre"], size="1",
                                  color_scheme=rx.cond(f["nombre"] == "NO ENCONTRADO", "red", "gray"))),
            _celda(f, i, "valor_total", _S.pm_set_celda, tipo="number", w="100px"),
            _celda(f, i, "cuotas_valor", _S.pm_set_celda, tipo="number", w="90px"),
            _celda(f, i, "fecha", _S.pm_set_celda, tipo="date", w="150px"),
            _celda(f, i, "observacion", _S.pm_set_celda, w="200px"),
            rx.table.cell(
                rx.hstack(
                    rx.cond(f["valido"], rx.icon("check", size=14, color="green")),
                    rx.button(rx.icon("trash-2", size=12), size="1", variant="ghost",
                              color_scheme="red", on_click=lambda: _S.pm_quitar_fila(i)),
                    spacing="1",
                )
            ),
        )

    return rx.vstack(
        card(
            rx.vstack(
                rx.hstack(
                    rx.text("Planificar por:", size="1", weight="bold"),
                    rx.el.select(
                        rx.el.option("Número de cuotas", value="cuotas"),
                        rx.el.option("Cuota mensual fija", value="valor"),
                        value=_S.pm_modo, on_change=_S.set_pm_modo, style=_SEL,
                    ),
                    spacing="2", align="center",
                ),
                rx.text(
                    "Pega aquí desde Excel (una fila por préstamo): código o cédula · valor total · "
                    "nº de cuotas (o cuota mensual) · fecha (AAAA-MM-DD) · observación.",
                    size="1", color_scheme="gray",
                ),
                rx.text_area(
                    value=_S.pm_pegar, on_change=_S.set_pm_pegar, rows="4", width="100%",
                    placeholder="0920116811\t600\t12\t2026-07-31\tPRESTAMO\n1712345678\t300\t6\t2026-08-31",
                ),
                rx.hstack(
                    rx.button("Cargar en la tabla", on_click=_S.pm_cargar_pegado, variant="soft", size="1"),
                    rx.button("Agregar fila", on_click=_S.pm_nueva_fila, variant="soft", size="1"),
                    rx.button("Validar", on_click=_S.pm_validar, size="1"),
                    rx.button("Limpiar", on_click=_S.pm_limpiar, variant="ghost", size="1"),
                    rx.cond(
                        (_S.pm_grid.length() > 0)
                        & AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                        primary_button("Registrar todo", on_click=_S.aplicar_masiva),
                    ),
                    spacing="2", wrap="wrap",
                ),
                rx.cond(
                    _S.pm_grid.length() > 0,
                    _grilla(["Código / cédula", "Nombre", "Valor total", "Cuotas / $mes", "Fecha", "Observación"],
                            _S.pm_grid, _fila),
                ),
                rx.cond(
                    _S.masiva_job > 0,
                    job_progress(
                        status=_S.masiva_status, progress=rx.Var.create(0), total=rx.Var.create(1),
                        message=_S.masiva_msg, error=rx.Var.create(""),
                        corriendo=_S.masiva_status.contains("corriendo") | _S.masiva_status.contains("pendiente"),
                        tiene_resultado=_S.masiva_path != "",
                        on_cancelar=rx.console_log, on_descargar=_S.descargar_masiva,
                    ),
                ),
                _msg(),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
        spacing="4", width="100%",
    )


# ── 3 y 6. Egresos / Ingresos + Consulta / edición ─────────────────────
def _tab_consulta() -> rx.Component:
    return rx.vstack(
        card(
            rx.vstack(
                rx.hstack(
                    rx.input(value=_S.consulta_filtro, on_change=_S.set_consulta_filtro,
                             placeholder="Nº de movimiento o nombre…", width="100%", size="2"),
                    rx.button("Buscar", on_click=_S.buscar_movimientos, size="2"),
                    spacing="2", width="100%",
                ),
                rx.cond(
                    _S.cargando_mov,
                    rx.center(rx.spinner(), padding="1rem"),
                    _tabla(
                        ["N°", "Tipo", "Empleado", "Fecha", "Valor", "Cuotas", ""],
                        _S.movimientos,
                        lambda m: rx.table.row(
                            rx.table.cell(m["numero"]),
                            rx.table.cell(m["tipo_clase"]),
                            rx.table.cell(m["nombre"]),
                            rx.table.cell(m["fecha"]),
                            rx.table.cell(m["valor"].to_string()),
                            rx.table.cell(m["cuotas"].to_string()),
                            rx.table.cell(
                                rx.hstack(
                                    rx.cond(
                                        m["clase"] == "205",
                                        rx.button("Cuotas", size="1", variant="soft",
                                                  on_click=lambda: _S.ver_cuotas(m["numero"], m["empleado"], m["nombre"])),
                                    ),
                                    rx.cond(
                                        AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                                        rx.button("Borrar", size="1", color_scheme="red", variant="soft",
                                                  on_click=lambda: _S.eliminar_movimiento(m["numero"], m["empleado"], m["clase"])),
                                    ),
                                    spacing="1",
                                ),
                            ),
                        ),
                    ),
                ),
                rx.cond(
                    _S.detalle_cuotas.length() > 0,
                    rx.vstack(
                        rx.heading(_S.detalle_titulo, size="2"),
                        _tabla(
                            ["Cuota", "Vence", "Valor", "Asentada"],
                            _S.detalle_cuotas,
                            lambda c: rx.table.row(
                                rx.table.cell(c["secuencia"].to_string()),
                                rx.table.cell(c["fecha_ven"]),
                                rx.table.cell(c["valor"].to_string()),
                                rx.table.cell(rx.cond(c["asentado"], "SÍ", "")),
                            ),
                        ),
                        rx.cond(
                            AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                            rx.hstack(
                                rx.text("Mover cuotas pendientes desde:", size="1", weight="bold"),
                                rx.input(value=_S.mover_fecha, on_change=_S.set_mover_fecha,
                                         type="date", width="150px"),
                                rx.button("Mover", on_click=_S.mover_cuotas, variant="soft", size="1"),
                                spacing="2",
                                align="center",
                                wrap="wrap",
                            ),
                        ),
                        spacing="2", width="100%",
                    ),
                ),
                _msg(),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
        _consulta_detallada(),
        spacing="4", width="100%",
    )


def _consulta_detallada() -> rx.Component:
    def _cell_valor(f):
        clave = (
            f["numero"].to_string() + "-" + f["empleado"].to_string() + "-"
            + f["clase"].to_string() + "-" + f["secuencia"].to_string()
        )
        return rx.cond(
            f["asentado"],
            rx.text("$" + f["valor"].to_string()),
            rx.hstack(
                rx.input(
                    default_value=f["valor"].to_string(), type="number", size="1", width="90px",
                    on_change=lambda v: _S.set_cq_edit(clave, v),
                ),
                rx.cond(
                    AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                    rx.button("Guardar", size="1", variant="soft",
                              on_click=lambda: _S.guardar_valor_fila(f)),
                ),
                spacing="1",
            ),
        )

    return card(
        rx.vstack(
            rx.heading("Consulta detallada (fila por fila)", size="3"),
            rx.grid(
                rx.input(value=_S.cq_empleado, on_change=lambda v: _S.set_cq("empleado", v),
                         placeholder="Empleado: código o nombre", size="2"),
                rx.el.select(
                    *[rx.el.option(o["etiqueta"], value=o["codigo"]) for o in CLASES_CONSULTA],
                    value=_S.cq_clase, on_change=lambda v: _S.set_cq("clase", v), style=_SEL,
                ),
                rx.input(value=_S.cq_numero, on_change=lambda v: _S.set_cq("numero", v),
                         placeholder="N° de movimiento", size="2"),
                rx.hstack(
                    rx.text("Vence:", size="1"),
                    rx.input(value=_S.cq_desde, on_change=lambda v: _S.set_cq("desde", v),
                             type="date", size="1"),
                    rx.input(value=_S.cq_hasta, on_change=lambda v: _S.set_cq("hasta", v),
                             type="date", size="1"),
                    spacing="1", align="center",
                ),
                columns=rx.breakpoints(initial="1", sm="2", lg="4"),
                spacing="2", width="100%",
            ),
            rx.hstack(
                rx.checkbox("Solo no procesados", checked=_S.cq_solo_pend,
                            on_change=lambda _v: _S.toggle_cq_pend()),
                rx.button("Buscar", on_click=_S.buscar_filas, size="1"),
                rx.button("Limpiar", on_click=_S.limpiar_cq, size="1", variant="soft"),
                rx.button("Exportar CSV", on_click=_S.exportar_cq_csv, size="1", variant="soft"),
                spacing="2", align="center", wrap="wrap",
            ),
            rx.cond(
                _S.cq_cargando,
                rx.center(rx.spinner(), padding="1rem"),
                rx.vstack(
                    rx.text(_S.cq_filas.length().to_string() + " fila(s)", size="1", color_scheme="gray"),
                    scroll_x(
                        rx.table.root(
                            rx.table.header(rx.table.row(*[
                                rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                                for c in ("N°", "Empleado", "Tipo", "Seq", "Vence", "Valor", "Estado", "")
                            ])),
                            rx.table.body(
                                rx.foreach(
                                    _S.cq_filas,
                                    lambda f: rx.table.row(
                                        rx.table.cell(f["numero"]),
                                        rx.table.cell(f["nombre"]),
                                        rx.table.cell(f["tipo_clase"]),
                                        rx.table.cell(f["secuencia"].to_string()),
                                        rx.table.cell(f["fecha_ven"]),
                                        rx.table.cell(_cell_valor(f)),
                                        rx.table.cell(rx.cond(f["asentado"], "Procesado", "Pendiente")),
                                        rx.table.cell(
                                            rx.cond(
                                                ~f["asentado"]
                                                & AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                                                rx.button("Eliminar", size="1", color_scheme="red", variant="ghost",
                                                          on_click=lambda: _S.eliminar_fila(f)),
                                            )
                                        ),
                                    ),
                                )
                            ),
                            variant="surface", size="1", width="100%",
                        )
                    ),
                    spacing="2", width="100%",
                ),
            ),
            spacing="3", width="100%",
        ),
        width="100%",
    )


# ── 4. Registro individual ─────────────────────────────────────────────
def _tab_individual() -> rx.Component:
    return rx.vstack(
        _buscador_empleado(),
        _panel_movimientos_emp(),
        card(
            rx.vstack(
                rx.grid(
                    rx.vstack(rx.text("Tipo de movimiento", size="1", weight="bold"),
                              rx.el.select(
                                  *[rx.el.option(o["etiqueta"], value=o["codigo"]) for o in CLASES_OPCIONES],
                                  value=_S.ind_clase, on_change=lambda v: _S.set_ind("clase", v), style=_SEL,
                              ), spacing="1"),
                    rx.vstack(rx.text("Valor", size="1", weight="bold"),
                              rx.input(value=_S.ind_valor, on_change=lambda v: _S.set_ind("valor", v),
                                       type="number", width="100%"), spacing="1"),
                    rx.vstack(rx.text("Fecha", size="1", weight="bold"),
                              rx.input(value=_S.ind_fecha, on_change=lambda v: _S.set_ind("fecha", v),
                                       type="date", width="100%"), spacing="1"),
                    columns=rx.breakpoints(initial="1", sm="3"), spacing="3", width="100%",
                ),
                rx.text_area(value=_S.ind_observ, on_change=lambda v: _S.set_ind("observ", v),
                             placeholder="Observación (opcional)", rows="2", width="100%"),
                rx.hstack(
                    rx.button("Previsualizar", on_click=_S.previsualizar_individual, variant="soft"),
                    rx.cond(
                        AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                        primary_button("Registrar", on_click=_S.guardar_individual),
                    ),
                    spacing="2",
                ),
                rx.cond(_S.ind_preview != "", rx.callout(_S.ind_preview, size="1")),
                _msg(),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
        _bulk_egr_ing(),
        spacing="4", width="100%",
    )


def _bulk_egr_ing() -> rx.Component:
    def _fila(f, i):
        return rx.table.row(
            _celda(f, i, "codigo", _S.bulk_set_celda, w="120px"),
            rx.table.cell(rx.text(f["nombre"], size="1",
                                  color_scheme=rx.cond(f["nombre"] == "NO ENCONTRADO", "red", "gray"))),
            _celda(f, i, "clase", _S.bulk_set_celda, opciones=CLASES_OPCIONES),
            _celda(f, i, "valor", _S.bulk_set_celda, tipo="number", w="100px"),
            _celda(f, i, "fecha", _S.bulk_set_celda, tipo="date", w="150px"),
            _celda(f, i, "observacion", _S.bulk_set_celda, w="200px"),
            rx.table.cell(
                rx.hstack(
                    rx.cond(f["valido"], rx.icon("check", size=14, color="green")),
                    rx.button(rx.icon("trash-2", size=12), size="1", variant="ghost",
                              color_scheme="red", on_click=lambda: _S.bulk_quitar_fila(i)),
                    spacing="1",
                )
            ),
        )

    return card(
        rx.vstack(
            rx.heading("Carga masiva de egresos / ingresos", size="3"),
            rx.text(
                "Pega aquí desde Excel (una fila por movimiento): código o cédula · clase "
                "(203 multa, 202 anticipo, 102 bonificación…) · valor · fecha · observación.",
                size="1", color_scheme="gray",
            ),
            rx.text_area(
                value=_S.bulk_pegar, on_change=_S.set_bulk_pegar, rows="4", width="100%",
                placeholder="0920116811\t203\t25.00\t2026-07-31\tMULTA ATRASO\n1712345678\t102\t40\t2026-07-31\tBONO",
            ),
            rx.hstack(
                rx.button("Cargar en la tabla", on_click=_S.bulk_cargar_pegado, variant="soft", size="1"),
                rx.button("Agregar fila", on_click=_S.bulk_nueva_fila, variant="soft", size="1"),
                rx.button("Validar", on_click=_S.bulk_validar, size="1"),
                rx.button("Limpiar", on_click=_S.bulk_limpiar, variant="ghost", size="1"),
                rx.cond(
                    (_S.bulk_grid.length() > 0)
                    & AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                    primary_button("Registrar todo", on_click=_S.aplicar_bulk),
                ),
                spacing="2", wrap="wrap",
            ),
            rx.cond(
                _S.bulk_grid.length() > 0,
                _grilla(["Código / cédula", "Nombre", "Tipo", "Valor", "Fecha", "Observación"],
                        _S.bulk_grid, _fila),
            ),
            rx.cond(
                _S.bulk_job > 0,
                job_progress(
                    status=_S.bulk_status, progress=rx.Var.create(0), total=rx.Var.create(1),
                    message=_S.bulk_msg, error=rx.Var.create(""),
                    corriendo=_S.bulk_status.contains("corriendo") | _S.bulk_status.contains("pendiente"),
                    tiene_resultado=_S.bulk_path != "",
                    on_cancelar=rx.console_log, on_descargar=_S.descargar_bulk,
                ),
            ),
            spacing="3", width="100%",
        ),
        width="100%",
    )


# ── 5. BIESS quirografarios / hipotecarios ─────────────────────────────
def _tab_biess() -> rx.Component:
    return rx.vstack(
        card(
            rx.vstack(
                rx.grid(
                    rx.vstack(
                        rx.text("Tipo de préstamo", size="1", weight="bold"),
                        rx.el.select(
                            rx.el.option("204 — Quirografario", value="204"),
                            rx.el.option("207 — Hipotecario", value="207"),
                            value=_S.biess_tipo, on_change=lambda v: _S.set_biess("tipo", v), style=_SEL,
                        ),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Fecha del movimiento", size="1", weight="bold"),
                        rx.input(value=_S.biess_fecha, type="date",
                                 on_change=lambda v: _S.set_biess("fecha", v), width="100%"),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Período (AAAA-MM)", size="1", weight="bold"),
                        rx.input(value=_S.periodo, on_change=_S.set_periodo, width="100%"),
                        spacing="1",
                    ),
                    columns=rx.breakpoints(initial="1", sm="3"), spacing="3", width="100%",
                ),
                rx.vstack(
                    rx.text("Observación (obligatoria, se registra en la nómina)", size="1", weight="bold"),
                    rx.input(value=_S.biess_obs, on_change=lambda v: _S.set_biess("obs", v), width="100%"),
                    spacing="1",
                ),
                rx.upload(
                    rx.vstack(rx.icon("upload", size=24), rx.text("Arrastra o elige el Excel del BIESS")),
                    id="biess", accept={".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                    max_files=1, border="1px dashed var(--gray-6)", padding="1.5rem", width="100%",
                ),
                rx.button("Cargar", on_click=_S.subir_biess(rx.upload_files(upload_id="biess"))),
                rx.cond(
                    _S.biess_archivo != "",
                    rx.vstack(
                        rx.text(_S.biess_archivo, size="1", color_scheme="gray"),
                        rx.hstack(
                            rx.text("Fila de inicio:", size="1"),
                            rx.input(value=_S.biess_fila, on_change=lambda v: _S.set_biess("fila", v),
                                     width="60px", size="1"),
                            rx.text("Col. cédula:", size="1"),
                            rx.input(value=_S.biess_col_ced, on_change=lambda v: _S.set_biess("col_ced", v),
                                     width="60px", size="1"),
                            rx.text("Col. valor:", size="1"),
                            rx.input(value=_S.biess_col_val, on_change=lambda v: _S.set_biess("col_val", v),
                                     width="60px", size="1"),
                            rx.button("Releer", on_click=_S.releer_biess, size="1", variant="soft"),
                            rx.button("Ver Excel", on_click=_S.toggle_biess_diag, size="1", variant="ghost"),
                            spacing="2", align="center", wrap="wrap",
                        ),
                        rx.text(
                            "Autodetección: confianza " + (_S.biess_confianza * 100).to_string() + "%. "
                            "Si las columnas no son las correctas, ajústalas y pulsa Releer.",
                            size="1", color_scheme="amber",
                        ),
                        rx.cond(
                            _S.biess_ver_diag & (_S.biess_diag.length() > 0),
                            scroll_x(
                                rx.table.root(
                                    rx.table.body(
                                        rx.foreach(
                                            _S.biess_diag,
                                            lambda fila: rx.table.row(
                                                rx.foreach(fila, lambda c: rx.table.cell(c)),
                                            ),
                                        )
                                    ),
                                    variant="surface", size="1", width="100%",
                                )
                            ),
                        ),
                        spacing="2", width="100%",
                    ),
                ),
                rx.cond(_S.avisos.length() > 0, rx.callout(
                    rx.foreach(_S.avisos, lambda a: rx.text(a, size="1")), color_scheme="amber", size="1")),
                rx.cond(
                    _S.filas_biess.length() > 0,
                    rx.vstack(
                        rx.text(_S.filas_biess.length().to_string() + " cédulas leídas (duplicadas sumadas)",
                                weight="bold", size="2"),
                        rx.button("Previsualizar / emparejar", on_click=_S.preparar_biess, variant="soft"),
                        rx.cond(
                            _S.dry.contains("a_insertar"),
                            rx.callout(
                                "Se registrarán " + _S.dry["a_insertar"].to_string()
                                + " · liquidados " + _S.dry["liquidados"].to_string()
                                + " · sin empleado " + _S.dry["no_encontrados"].to_string()
                                + " · total $" + _S.dry["total"].to_string(),
                                size="1",
                            ),
                        ),
                        rx.cond(
                            _S.movs.length() > 0,
                            _tabla(
                                ["Cédula", "Código", "Nombre", "Valor", "Estado"],
                                _S.movs,
                                lambda m: rx.table.row(
                                    rx.table.cell(m["cedula"]),
                                    rx.table.cell(m["empleado"]),
                                    rx.table.cell(m["nombre"]),
                                    rx.table.cell("$" + m["valor"].to_string()),
                                    rx.table.cell(
                                        rx.badge(m["estado_biess"], color_scheme=rx.match(
                                            m["estado_biess"], ("activo", "green"),
                                            ("liquidado", "amber"), "red"))
                                    ),
                                ),
                            ),
                        ),
                        rx.hstack(
                            rx.cond(
                                _S.movs.length() > 0
                                & AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                                primary_button("Confirmar y registrar", on_click=_S.postear_biess),
                            ),
                            rx.cond(_S.movs.length() > 0,
                                    rx.button("Exportar CSV", on_click=_S.exportar_biess, variant="soft", size="1")),
                            spacing="2",
                        ),
                        spacing="2", width="100%",
                    ),
                ),
                _msg(),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
        spacing="4", width="100%",
    )


@rx.page(
    route="/registrador",
    title="INSEVIG — Registrar egresos/ingresos",
    on_load=[AuthState.cargar_sesion, RegistradorState.on_load],
)
def index() -> rx.Component:
    return pagina(
        page_heading("Registrar egresos / ingresos", "Préstamos, anticipos, multas, bonificaciones y BIESS."),
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("Préstamo individual", value="prestamo"),
                rx.tabs.trigger("Carga masiva préstamos", value="masiva"),
                rx.tabs.trigger("Egresos / Ingresos", value="individual"),
                rx.tabs.trigger("BIESS quirografarios", value="biess"),
                rx.tabs.trigger("Consulta / edición", value="consulta"),
                wrap="wrap",
            ),
            rx.tabs.content(rx.cond(_S.tab == "prestamo", _tab_prestamo(), rx.box()), value="prestamo"),
            rx.tabs.content(rx.cond(_S.tab == "masiva", _tab_masiva(), rx.box()), value="masiva"),
            rx.tabs.content(rx.cond(_S.tab == "individual", _tab_individual(), rx.box()), value="individual"),
            rx.tabs.content(rx.cond(_S.tab == "biess", _tab_biess(), rx.box()), value="biess"),
            rx.tabs.content(rx.cond(_S.tab == "consulta", _tab_consulta(), rx.box()), value="consulta"),
            value=_S.tab,
            on_change=_S.set_tab,
            default_value="prestamo",
            width="100%",
        ),
        requiere=("registrador", "ver"),
    )
