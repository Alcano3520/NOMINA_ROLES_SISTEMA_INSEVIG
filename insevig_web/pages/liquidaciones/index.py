from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.job_progress import job_progress
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x, stat_card
from insevig_web.states.auth_state import AuthState
from insevig_web.states.liquidaciones_state import MOTIVOS_SALIDA, LiquidacionesState

_SEL = {
    "padding": "6px", "borderRadius": "6px", "border": "1px solid var(--gray-6)",
    "background": "#fff", "color": "#1f2937",
}
_S = LiquidacionesState


def _resumen() -> rx.Component:
    return rx.grid(
        stat_card("Borrador", "Sin confirmar", _S.resumen["borrador"].to_string(), "file-pen"),
        stat_card("Generada", "Lista para pagar", _S.resumen["generada"].to_string(), "file-check"),
        stat_card("Pagada", "Ya liquidada", _S.resumen["pagada"].to_string(), "circle-dollar-sign"),
        stat_card("Anulada", "Sin efecto", _S.resumen["anulada"].to_string(), "file-x"),
        columns=rx.breakpoints(initial="2", md="4"),
        spacing="3", width="100%",
    )


def _selector_formato() -> rx.Component:
    return card(
        rx.text("1. Formato de Salida", weight="bold", size="3", margin_bottom="0.5rem"),
        rx.el.label(
            rx.el.input(
                type="radio", name="formato", value="MASIVO",
                checked=_S.formato == "MASIVO",
                on_change=lambda _v: _S.set_formato("MASIVO"),
            ),
            rx.text(
                " 📊 Masivo (por Plantilla) — Excel, varios empleados a la vez",
                as_="span", size="2",
            ),
            display="flex", align_items="center", gap="0.4rem", padding_y="4px",
        ),
        rx.el.label(
            rx.el.input(
                type="radio", name="formato", value="INDIVIDUAL",
                checked=_S.formato == "INDIVIDUAL",
                on_change=lambda _v: _S.set_formato("INDIVIDUAL"),
            ),
            rx.text(
                " 📄 Individual (Borrador) — PDF de simulación, 1 empleado, con vista previa",
                as_="span", size="2",
            ),
            display="flex", align_items="center", gap="0.4rem", padding_y="4px",
        ),
        width="100%",
    )


def _panel_masivo() -> rx.Component:
    return card(
        rx.vstack(
            rx.hstack(
                rx.text("Región:", weight="bold", size="2"),
                rx.select(["COSTA", "SIERRA"], default_value="COSTA", on_change=_S.set_region),
                spacing="3", wrap="wrap", align="center",
            ),
            rx.text(
                "Una línea por empleado: cédula, dd/mm/aaaa (fecha salida), motivo.",
                size="2", color_scheme="gray",
            ),
            rx.text_area(
                value=_S.entrada,
                on_change=_S.set_entrada,
                placeholder="0920116811, 15/02/2026, RENUNCIA VOLUNTARIA\n1712345678, 28/02/2026, DESPIDO INTEMPESTIVO",
                rows="6", width="100%",
            ),
            rx.hstack(
                rx.button("Previsualizar", on_click=_S.previsualizar, variant="soft"),
                primary_button("Generar Excel", on_click=_S.generar_excel),
                spacing="2",
            ),
            spacing="3", width="100%",
        ),
        width="100%",
    )


def _fila_previa(q, i) -> rx.Component:
    return rx.table.row(
        rx.table.cell(q["empleado"]),
        rx.table.cell(q["nombre"]),
        rx.table.cell(q["motivo"]),
        rx.table.cell(q["dias"].to_string()),
        rx.table.cell(q["ingresos"].to_string()),
        rx.table.cell(q["descuentos"].to_string()),
        rx.table.cell(q["recibir"].to_string()),
        rx.table.cell(q["error"]),
        rx.table.cell(
            rx.cond(
                q["error"] == "",
                rx.vstack(
                    rx.hstack(
                        rx.button("PDF", on_click=lambda: _S.generar_pdf_fila(i), size="1", variant="soft"),
                        rx.cond(
                            AuthState.permisos_flat.contains("liquidaciones:editar"),
                            rx.button("Guardar", on_click=lambda: _S.guardar_fila(i), size="1", color_scheme="blue"),
                        ),
                        spacing="1",
                    ),
                    rx.cond(
                        _S.fila_msg.contains(i.to_string()),
                        rx.text(_S.fila_msg[i.to_string()], size="1", color_scheme="gray"),
                    ),
                    spacing="1", align="start",
                ),
            )
        ),
    )


def _tabla_masivo() -> rx.Component:
    return rx.cond(
        _S.previsualizacion.length() > 0,
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(*[
                        rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                        for c in ("Empleado", "Nombre", "Motivo", "Días", "Ingresos", "Descuentos", "A recibir", "Error", "")
                    ])
                ),
                rx.table.body(rx.foreach(_S.previsualizacion, _fila_previa)),
                variant="surface", size="1", width="100%",
            )
        ),
    )


def _checkbox_ind(texto: str, valor: rx.Var, on_change) -> rx.Component:
    return rx.text(
        rx.checkbox(checked=valor, on_change=on_change, margin_right="0.4rem"),
        texto,
        size="1", as_="label", display="flex", align_items="start", padding_y="4px",
    )


def _panel_individual() -> rx.Component:
    return card(
        rx.vstack(
            rx.text("2. Datos del Empleado y Fecha de Salida", weight="bold", size="3"),
            rx.hstack(
                rx.text("Buscar por:", size="2"),
                rx.el.select(
                    rx.el.option("Cédula", value="cedula"),
                    rx.el.option("Código", value="codigo"),
                    rx.el.option("Nombre", value="nombre"),
                    value=_S.busqueda_modo, on_change=_S.set_busqueda_modo, style=_SEL,
                ),
                rx.input(
                    value=_S.ind_identificador, on_change=_S.set_ind_identificador,
                    placeholder="cédula, código o nombre…", width="220px",
                ),
                rx.button(
                    rx.icon("search", size=14), "Buscar",
                    on_click=_S.buscar_empleado_individual, loading=_S.ind_buscando, size="2", variant="soft",
                ),
                spacing="2", wrap="wrap", align="center",
            ),
            rx.hstack(
                rx.vstack(
                    rx.text("Fecha de salida:", size="2", weight="bold"),
                    rx.input(value=_S.ind_fecha, on_change=_S.set_ind_fecha, placeholder="dd/mm/aaaa", width="140px"),
                    spacing="1", align_items="start",
                ),
                rx.vstack(
                    rx.text("Motivo de salida:", size="2", weight="bold"),
                    rx.hstack(
                        rx.input(value=_S.ind_motivo, on_change=_S.set_ind_motivo,
                                  placeholder="escriba o elija abajo", width="220px"),
                        rx.el.select(
                            rx.el.option("(elegir)", value=""),
                            *[rx.el.option(m, value=m) for m in MOTIVOS_SALIDA],
                            value="", on_change=_S.set_ind_motivo, style=_SEL,
                        ),
                        spacing="2",
                    ),
                    spacing="1", align_items="start",
                ),
                spacing="4", wrap="wrap",
            ),
            rx.cond(_S.ind_msg != "", rx.callout(_S.ind_msg, size="1", color_scheme="red")),
            rx.cond(
                _S.ind_emp.contains("cedula"),
                card(
                    rx.text("Datos del Empleado", weight="bold", size="2", margin_bottom="0.3rem"),
                    rx.grid(
                        rx.text("Nombre: " + _S.ind_emp["nombre"], size="2"),
                        rx.text("Cargo: " + _S.ind_emp["cargo"], size="2"),
                        rx.text("Sección: " + _S.ind_emp["seccion"], size="2"),
                        rx.text("Fecha ingreso: " + _S.ind_emp["fecha_ingreso"], size="2"),
                        rx.text("Sueldo: $" + _S.ind_emp["sueldo"], size="2"),
                        columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                        spacing="2", width="100%",
                    ),
                    width="100%", variant="surface",
                ),
            ),
            rx.divider(),
            _checkbox_ind(
                "Incluir Décima TERCERA anterior (ya pagada) en la vista previa — por defecto "
                "solo se muestra/cuenta la actual",
                _S.ind_incluir_dec13_ant, _S.set_ind_incluir_dec13_ant,
            ),
            _checkbox_ind(
                "Incluir Décima CUARTA anterior (ya pagada) en la vista previa — por defecto "
                "solo se muestra/cuenta la actual",
                _S.ind_incluir_dec14_ant, _S.set_ind_incluir_dec14_ant,
            ),
            _checkbox_ind(
                "Mostrar insumos del cálculo (períodos y sumatorias intermedias)",
                _S.ind_mostrar_insumos, _S.set_ind_mostrar_insumos,
            ),
            rx.hstack(
                primary_button("Calcular / Generar Liquidación", on_click=_S.calcular_individual),
                rx.button(rx.icon("file-text", size=14), "PDF", on_click=_S.generar_pdf_individual,
                          variant="soft", size="2"),
                rx.cond(
                    AuthState.permisos_flat.contains("liquidaciones:editar"),
                    rx.button("💾 Guardar Liquidación", on_click=_S.guardar_individual, size="2", color_scheme="blue"),
                ),
                spacing="2", wrap="wrap",
            ),
            _panel_preview_individual(),
            spacing="3", width="100%",
        ),
        width="100%",
    )


def _panel_preview_individual() -> rx.Component:
    return rx.cond(
        _S.ind_conceptos.length() > 0,
        card(
            rx.text("👁 VISTA PREVIA", weight="bold", size="3", margin_bottom="0.5rem"),
            scroll_x(
                rx.table.root(
                    rx.table.header(rx.table.row(*[
                        rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                        for c in ("Concepto", "Tipo", "Valor")
                    ])),
                    rx.table.body(
                        rx.foreach(
                            _S.ind_conceptos,
                            lambda c: rx.table.row(
                                rx.table.cell(c["concepto_nombre"]),
                                rx.table.cell(c["concepto_tipo"]),
                                rx.table.cell("$" + c["valor_total"].to_string()),
                            ),
                        )
                    ),
                    variant="surface", size="1", width="100%",
                )
            ),
            rx.divider(),
            rx.hstack(
                rx.text("Ingresos: $" + _S.ind_totales["ingresos"].to_string(), size="2"),
                rx.text("Descuentos: $" + _S.ind_totales["descuentos"].to_string(), size="2"),
                rx.text("A recibir: $" + _S.ind_totales["recibir"].to_string(), weight="bold", size="3"),
                spacing="4", wrap="wrap",
            ),
            width="100%",
        ),
    )


@rx.page(
    route="/liquidaciones", title="INSEVIG — Liquidaciones",
    on_load=[AuthState.cargar_sesion, LiquidacionesState.cargar_pantalla],
)
def index() -> rx.Component:
    return pagina(
        page_heading(
            "Generador de liquidaciones (finiquitos)",
            "Cálculo legal: vacaciones (TODOS los periodos pendientes), décimo 13/14, desahucio, "
            "indemnización por despido, IESS, fondo de reserva, split de anticipos.",
        ),
        rx.link(
            rx.button(rx.icon("folder-open", size=14), "Ver liquidaciones guardadas", variant="soft", size="2"),
            href="/liquidaciones/guardadas",
        ),
        rx.vstack(
            _resumen(),
            _selector_formato(),
            rx.cond(_S.formato == "MASIVO", _panel_masivo(), _panel_individual()),
            rx.cond(_S.formato == "MASIVO", _tabla_masivo()),
            rx.cond(
                _S.job > 0,
                job_progress(
                    status=_S.status, progress=rx.Var.create(0), total=rx.Var.create(1),
                    message=_S.msg, error=rx.Var.create(""),
                    corriendo=_S.status.contains("corriendo") | _S.status.contains("pendiente"),
                    tiene_resultado=_S.path != "",
                    on_cancelar=_S.cancelar, on_descargar=_S.descargar,
                ),
            ),
            spacing="4", width="100%",
        ),
        requiere=("liquidaciones", "ver"),
    )
