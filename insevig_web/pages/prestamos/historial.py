"""Consultor de Historial de Préstamos — paridad con `HISTORIAL_PRESTAMOS_10.pyw`.

Layout del `.pyw`: banda de búsqueda + acciones (NOMBRES / BUSCAR / SALDOS /
EXCEL / IA) · banda de filtros (Tipo / Origen / Obs / Num / Desde / Hasta /
Min / Max / X) · banda "Información del Empleado" · dos paneles lado a lado —
izquierda el árbol de movimientos (# / FECHA / INGRESO / EGRESO / NÚMERO /
OBSERVACIONES / TIPO / SALDO) con colores de fila, derecha "Empleados con Saldo".
"""

from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.employee_search import employee_search
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.prestamos_state import PrestamosState

_S = PrestamosState

# Colores de fila — paleta de `configurar_tags_tree` del .pyw
_BG_ING = "var(--gray-1)"     # ingreso sistema  → blanco
_BG_EGR = "var(--red-3)"      # egreso sistema   → rojo claro
_BG_ING_H = "var(--blue-3)"   # ingreso histórico → azul
_BG_EGR_H = "var(--amber-3)"  # egreso histórico  → naranja

_SEL = {"padding": "5px", "borderRadius": "6px", "border": "1px solid var(--gray-6)",
        "background": "var(--color-panel-solid)", "fontSize": "13px"}
_INP = {"size": "1"}


# ── Panel izquierdo: árbol de movimientos ───────────────────────────────────

def _bg_fila(f) -> rx.Var:
    return rx.cond(
        f["historico"],
        rx.cond(f["tipo"] == "INGRESO", _BG_ING_H, _BG_EGR_H),
        rx.cond(f["tipo"] == "INGRESO", _BG_ING, _BG_EGR),
    )


def _money(v) -> rx.Component:
    return rx.cond(v.to(float) > 0, "$" + v.to_string(), "")


def _fila(f) -> rx.Component:
    return rx.table.row(
        rx.table.cell(f["posicion"], style={"textAlign": "center"}),
        rx.table.cell(f["fecha_fmt"], style={"textAlign": "center"}),
        rx.table.cell(_money(f["ingreso"]), style={"textAlign": "right"}),
        rx.table.cell(_money(f["egreso"]), style={"textAlign": "right"}),
        rx.table.cell(f["numero"], style={"textAlign": "center"}),
        rx.table.cell(f["observacion"]),
        rx.table.cell(f["tipo"], style={"textAlign": "center"}),
        rx.table.cell("$" + f["saldo"].to_string(), style={"textAlign": "right", "fontWeight": "bold"}),
        on_click=lambda: _S.ver_mov_detalle(f),
        style={
            "cursor": "pointer",
            "background": _bg_fila(f),
            "color": rx.cond(f["tipo"] == "EGRESO", "var(--red-11)", "inherit"),
        },
    )


def _tabla_movimientos() -> rx.Component:
    return scroll_x(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    *[
                        rx.table.column_header_cell(c)
                        for c in ("#", "FECHA", "INGRESO ($)", "EGRESO ($)", "NÚMERO",
                                  "OBSERVACIONES", "TIPO", "SALDO ($)")
                    ]
                )
            ),
            rx.table.body(rx.foreach(_S.filas_historial, _fila)),
            variant="surface", size="1", width="100%",
        )
    )


def _dialog_detalle() -> rx.Component:
    _M = _S.mov_detalle
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Detalle del movimiento #" + _M["posicion"], size="4"),
            rx.vstack(
                *[
                    rx.hstack(
                        rx.text(etq, weight="bold", size="2", width="12em"),
                        rx.text(_M[campo], size="2"),
                        spacing="2", align="start",
                    )
                    for etq, campo in (
                        ("📅 Fecha", "fecha"), ("🔢 Número", "numero"),
                        ("📊 Posición", "posicion"), ("💰 Valor", "valor"),
                        ("📈 Saldo resultante", "saldo"), ("🏷️ Tipo", "tipo"),
                        ("📍 Origen", "origen"),
                    )
                ],
                rx.text("📝 Observación completa", weight="bold", size="2", margin_top="0.5rem"),
                rx.box(
                    rx.text(_M["concepto"], size="2"),
                    padding="0.5rem", border="1px solid var(--gray-6)",
                    border_radius="6px", width="100%", white_space="pre-wrap",
                    max_height="220px", overflow_y="auto",
                ),
                rx.hstack(
                    rx.button(
                        "📋 Copiar observación",
                        on_click=rx.set_clipboard(_M["concepto"]),
                        variant="soft", size="1",
                    ),
                    rx.spacer(),
                    rx.dialog.close(rx.button("Cerrar", variant="soft")),
                    width="100%", margin_top="1rem",
                ),
                spacing="2", width="100%",
            ),
            max_width="640px",
        ),
        open=_S.mov_detalle_abierto,
        on_open_change=_S.cerrar_mov_detalle,
    )


# ── Banda de filtros ───────────────────────────────────────────────────────

def _filtros() -> rx.Component:
    return rx.hstack(
        rx.text("Tipo:", size="1", weight="bold"),
        rx.el.select(
            rx.el.option("Todos", value=""),
            rx.el.option("Ingresos", value="INGRESO"),
            rx.el.option("Egresos", value="EGRESO"),
            value=_S.filtro_tipo, on_change=lambda v: _S.set_filtro("tipo", v), style=_SEL,
        ),
        rx.text("Origen:", size="1", weight="bold"),
        rx.el.select(
            rx.el.option("Todos", value=""),
            rx.el.option("Sistema Actual", value="SISTEMA"),
            rx.el.option("Histórico", value="HISTORICO"),
            value=_S.filtro_origen, on_change=lambda v: _S.set_filtro("origen", v), style=_SEL,
        ),
        rx.input(value=_S.filtro_texto, on_change=lambda v: _S.set_filtro("texto", v),
                 placeholder="Obs.", width="120px", **_INP),
        rx.input(value=_S.filtro_numero, on_change=lambda v: _S.set_filtro("numero", v),
                 placeholder="Núm.", width="80px", **_INP),
        rx.input(value=_S.filtro_desde, on_change=lambda v: _S.set_filtro("desde", v),
                 type="date", placeholder="Desde", width="150px", **_INP),
        rx.input(value=_S.filtro_hasta, on_change=lambda v: _S.set_filtro("hasta", v),
                 type="date", placeholder="Hasta", width="150px", **_INP),
        rx.input(value=_S.filtro_monto_min, on_change=lambda v: _S.set_filtro("monto_min", v),
                 placeholder="Min", width="80px", **_INP),
        rx.input(value=_S.filtro_monto_max, on_change=lambda v: _S.set_filtro("monto_max", v),
                 placeholder="Max", width="80px", **_INP),
        rx.cond(_S.hay_filtros,
                rx.button("X", on_click=_S.limpiar_filtros, variant="soft", size="1", color_scheme="amber")),
        spacing="2", align="center", wrap="wrap",
    )


# ── Panel derecho: empleados con saldo ─────────────────────────────────────

def _panel_saldos() -> rx.Component:
    return card(
        rx.vstack(
            rx.hstack(
                rx.heading("👥 Empleados con Saldo", size="3"),
                rx.spacer(),
                rx.button("Actualizar", on_click=_S.cargar_panel_saldos, variant="ghost", size="1"),
                width="100%", align="center", wrap="wrap",
            ),
            rx.badge(_S.panel_saldos_resumen, color_scheme="blue"),
            rx.hstack(
                rx.input(placeholder="Buscar…", value=_S.panel_filtro,
                         on_change=_S.set_panel_filtro, size="1", width="100%"),
                rx.checkbox("Act.", checked=_S.panel_solo_activos,
                            on_change=_S.toggle_panel_activos, size="1"),
                spacing="2", align="center", width="100%",
            ),
            rx.cond(
                _S.panel_cargando,
                rx.spinner(),
                rx.box(
                    scroll_x(
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("CÓD."),
                                    rx.table.column_header_cell("NOMBRE"),
                                    rx.table.column_header_cell("SALDO ($)"),
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    _S.panel_saldos_filtrado,
                                    lambda f: rx.table.row(
                                        rx.table.cell(f["empleado"]),
                                        rx.table.cell(f["nombre"]),
                                        rx.table.cell("$" + f["saldo"].to_string(),
                                                      style={"textAlign": "right"}),
                                        on_click=lambda: _S.seleccionar(f["empleado"], f["nombre"]),
                                        style={"cursor": "pointer"},
                                        _hover={"background": theme.BG},
                                    ),
                                )
                            ),
                            variant="surface", size="1", width="100%",
                        )
                    ),
                    max_height="70vh", overflow_y="auto", width="100%",
                ),
            ),
            spacing="2", width="100%",
        ),
        width="100%",
    )


# ── Acciones (SALDOS / EXCEL / IA) ─────────────────────────────────────────

def _acciones() -> rx.Component:
    return rx.hstack(
        rx.button("SALDOS (Excel de todos)", on_click=_S.generar_saldos,
                  variant="soft", size="1", color_scheme="green"),
        rx.cond(_S.saldos_path != "",
                rx.button("Descargar saldos", on_click=_S.descargar_saldos, size="1")),
        rx.cond(_S.saldos_status.contains("pendiente") | _S.saldos_status.contains("corriendo"),
                rx.badge("Generando saldos…")),
        rx.cond(
            _S.empleado_sel != "",
            rx.fragment(
                rx.button("EXCEL (empleado)", on_click=_S.exportar_empleado, variant="soft", size="1"),
                rx.cond(_S.exportar_path != "",
                        rx.button("Descargar", on_click=_S.descargar_exportar, size="1")),
            ),
        ),
        spacing="2", align="center", wrap="wrap",
    )


def _seccion_ia() -> rx.Component:
    return rx.cond(
        _S.empleado_sel != "",
        rx.hstack(
            rx.text("IA — período:", size="1", weight="bold"),
            rx.select(
                ["Todo el historial", "Año actual", "Último año", "Último semestre"],
                value=_S.ia_rango_label, on_change=_S.set_ia_rango, size="1",
            ),
            rx.button("Analizar con IA", on_click=_S.generar_narrativa, variant="soft", size="1"),
            rx.cond(
                _S.narrativa != "",
                rx.fragment(
                    rx.button("🔊 Leer", on_click=_S.leer_en_voz_alta, variant="soft", size="1"),
                    rx.button("■ Detener", on_click=_S.detener_voz, variant="ghost", size="1"),
                ),
            ),
            rx.cond(_S.narrativa_status != "", rx.badge(_S.narrativa_status)),
            spacing="2", align="center", wrap="wrap",
        ),
    )


@rx.page(
    route="/prestamos/historial",
    title="INSEVIG — Consultor de Préstamos",
    on_load=[AuthState.cargar_sesion, PrestamosState.cargar_panel_saldos],
)
def historial() -> rx.Component:
    return pagina(
        page_heading("Consultor de Préstamos",
                     "Historial de préstamos y saldo del empleado, incluido el histórico. "
                     "DD/MM/AAAA en los filtros de fecha."),
        rx.vstack(
            # búsqueda + acciones
            employee_search(
                texto=PrestamosState.texto_busqueda,
                resultados=PrestamosState.resultados,
                on_set_texto=PrestamosState.set_texto,
                on_buscar=PrestamosState.buscar,
                on_seleccionar=PrestamosState.seleccionar,
            ),
            _acciones(),
            # filtros
            rx.cond(_S.empleado_sel != "", card(_filtros(), width="100%")),
            # banda de información del empleado
            rx.cond(
                _S.info_empleado_txt != "",
                card(rx.text(_S.info_empleado_txt, weight="bold", size="2"), width="100%"),
            ),
            # dos paneles: movimientos | empleados con saldo
            rx.grid(
                rx.cond(
                    _S.empleado_sel != "",
                    card(
                        rx.vstack(
                            rx.hstack(
                                rx.heading("📋 Historial de Movimientos", size="3"),
                                rx.spacer(),
                                rx.badge(_S.hist_mostrando),
                                width="100%", align="center", wrap="wrap",
                            ),
                            rx.text("Clic en una fila para ver el detalle.", size="1", color_scheme="gray"),
                            rx.cond(_S.cargando_hist, rx.spinner(), _tabla_movimientos()),
                            _dialog_detalle(),
                            _seccion_ia(),
                            rx.cond(_S.narrativa != "", rx.callout(_S.narrativa, size="1")),
                            spacing="2", width="100%",
                        ),
                        width="100%",
                    ),
                    card(rx.text("Elegí un empleado de la lista de la derecha o buscá arriba.",
                                 color_scheme="gray"), width="100%"),
                ),
                _panel_saldos(),
                columns=rx.breakpoints(initial="1", lg="2fr 1fr"),
                spacing="3", width="100%", align="start",
            ),
            spacing="3", width="100%",
        ),
        requiere=("prestamos", "ver"),
    )
