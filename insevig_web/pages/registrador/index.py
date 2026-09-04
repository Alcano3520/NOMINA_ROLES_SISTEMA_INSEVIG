from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.job_progress import job_progress
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.registrador_state import CLASES_OPCIONES, RegistradorState

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
def _tab_prestamo() -> rx.Component:
    return rx.vstack(
        _buscador_empleado(),
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
                        _tabla(
                            ["Cuota", "Vence", "Valor"],
                            _S.p_preview,
                            lambda c: rx.table.row(
                                rx.table.cell(c["secuencia"].to_string()),
                                rx.table.cell(c["fecha_vencimiento"]),
                                rx.table.cell(c["valor"].to_string()),
                            ),
                        ),
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


# ── 2. Carga masiva de préstamos ────────────────────────────────────────
def _tab_masiva() -> rx.Component:
    return rx.vstack(
        card(
            rx.vstack(
                rx.text("Una línea por préstamo: cédula, valor total, nº cuotas, fecha (AAAA-MM-DD).",
                        size="1", color_scheme="gray"),
                rx.text_area(value=_S.masiva_texto, on_change=_S.set_masiva_texto, rows="8", width="100%",
                             placeholder="0920116811, 600, 12, 2026-07-31\n1712345678, 300, 6, 2026-08-31"),
                rx.hstack(
                    rx.button("Previsualizar", on_click=_S.previsualizar_masiva, variant="soft"),
                    rx.cond(
                        _S.masiva_filas.length() > 0
                        & AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                        primary_button("Aplicar", on_click=_S.aplicar_masiva),
                    ),
                    spacing="2",
                ),
                rx.cond(
                    _S.masiva_filas.length() > 0,
                    _tabla(
                        ["Cédula", "Empleado", "Valor", "Cuotas", "Fecha"],
                        _S.masiva_filas,
                        lambda f: rx.table.row(
                            rx.table.cell(f["cedula"]),
                            rx.table.cell(f["nombre"]),
                            rx.table.cell(f["valor"]),
                            rx.table.cell(f["cuotas"]),
                            rx.table.cell(f["fecha"]),
                        ),
                    ),
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


# ── 4. Registro individual ─────────────────────────────────────────────
def _tab_individual() -> rx.Component:
    return rx.vstack(
        _buscador_empleado(),
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
        spacing="4", width="100%",
    )


# ── 5. BIESS ───────────────────────────────────────────────────────────
def _tab_biess() -> rx.Component:
    return rx.vstack(
        card(
            rx.vstack(
                rx.hstack(
                    rx.text("Período (AAAA-MM):", size="1", weight="bold"),
                    rx.input(value=_S.periodo, on_change=_S.set_periodo, width="120px", size="2"),
                    spacing="2",
                ),
                rx.upload(
                    rx.vstack(rx.icon("upload", size=24), rx.text("Arrastra o elige el Excel del BIESS")),
                    id="biess", accept={".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                    max_files=1, border="1px dashed var(--gray-6)", padding="1.5rem", width="100%",
                ),
                rx.button("Cargar", on_click=_S.subir_biess(rx.upload_files(upload_id="biess"))),
                rx.cond(_S.avisos.length() > 0, rx.callout(
                    rx.foreach(_S.avisos, lambda a: rx.text(a, size="1")), color_scheme="amber", size="1")),
                rx.cond(
                    _S.filas_biess.length() > 0,
                    rx.vstack(
                        rx.text(_S.filas_biess.length().to_string() + " filas leídas", weight="bold", size="2"),
                        rx.button("Previsualizar posteo", on_click=_S.preparar_biess, variant="soft"),
                        rx.cond(
                            _S.dry.contains("insertados"),
                            rx.callout(
                                "Se insertarían " + _S.dry["insertados"].to_string()
                                + " · duplicados " + _S.dry["omitidos_dedupe"].to_string()
                                + " · sin empleado " + _S.dry["sin_empleado"].to_string(),
                                size="1",
                            ),
                        ),
                        rx.cond(
                            _S.movs.length() > 0
                            & AuthState.permisos_flat.contains("registrador:registrar_rpingdes"),
                            primary_button("Confirmar y registrar", on_click=_S.postear_biess),
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
