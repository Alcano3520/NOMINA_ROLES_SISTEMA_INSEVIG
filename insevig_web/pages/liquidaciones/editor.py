"""Editor de Liquidaciones — pantalla dedicada maestro-detalle (la 4ta del
sidebar del `.pyw`). Ver docs/modulos/liquidaciones_editor_UI.md.

Solo capa de presentación: toda la lógica vive en
`insevig_web/states/liquidaciones_editor_state.py`.
"""

from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading
from insevig_web.pages.liquidaciones._nav import subnav
from insevig_web.states.auth_state import AuthState
from insevig_web.states.liquidaciones_editor_state import (
    CHIPS_ESTADO,
    ESTADOS,
    SEC_BENEFICIOS,
    SEC_DESCUENTOS,
    SEC_REMUNERACION,
    LiquidacionesEditorState,
)

_HORAS_KEYS = {
    "SOBT_25": ("horas_25_cant", "horas_25_vh"),
    "SOBT_50": ("horas_50_cant", "horas_50_vh"),
    "SOBT_100": ("horas_100_cant", "horas_100_vh"),
}

_S = LiquidacionesEditorState

# Tokens locales de esta pantalla (colores del sistema Radix, no nuevos).
_SURFACE = "var(--gray-2)"
_LINE = "1px solid var(--gray-5)"
_RADIUS = "10px"


# ── Panel izquierdo: lista ───────────────────────────────────────────────────

def _item_lista(f) -> rx.Component:
    seleccionado = _S.ed_id == f["id"]
    return rx.box(
        rx.flex(
            rx.vstack(
                rx.text(f["nombre"], size="2", weight="bold"),
                rx.hstack(
                    rx.text(f["fecha_salida"], size="1", color_scheme="gray"),
                    rx.badge(f["estado_label"], color_scheme=f["estado_color"], size="1"),
                    spacing="2", align="center", wrap="wrap",
                ),
                spacing="1", align="start", flex_grow="1", min_width="0",
            ),
            rx.text(f'${f["total_liquido"]}', size="2", weight="medium",
                    white_space="nowrap"),
            justify="between", align="center", gap="2", width="100%",
        ),
        on_click=lambda: _S.abrir(f["id"]),
        padding="10px 12px",
        border_radius="8px",
        cursor="pointer",
        border_left=rx.cond(seleccionado, f"3px solid {theme.PRIMARY}", "3px solid transparent"),
        background=rx.cond(seleccionado, "var(--blue-3)", "transparent"),
        _hover={"background": rx.cond(seleccionado, "var(--blue-3)", "var(--gray-3)")},
        transition="background 120ms ease",
        width="100%",
    )


def _chip(valor: str, etiqueta: str) -> rx.Component:
    activo = _S.ed_estado == valor
    return rx.button(
        etiqueta,
        size="2",
        variant=rx.cond(activo, "solid", "surface"),
        color_scheme=rx.cond(activo, "blue", "gray"),
        on_click=lambda: _S.set_ed_estado(valor),
        width="100%",
    )


def _lista() -> rx.Component:
    return card(
        rx.vstack(
            rx.vstack(
                rx.heading("Editor de liquidaciones", size="4"),
                rx.text(_S.ed_conteo, size="1", color_scheme="gray"),
                spacing="1", align="start", width="100%",
            ),
            rx.hstack(
                rx.input(
                    value=_S.ed_texto, on_change=_S.set_ed_texto,
                    placeholder="Cédula o nombre…", size="2", width="100%",
                ),
                rx.button(rx.icon("search", size=15), on_click=_S.cargar_lista, size="2"),
                spacing="2", width="100%",
            ),
            rx.grid(
                *[_chip(v, e) for v, e in CHIPS_ESTADO],
                columns="3", spacing="2", width="100%",
            ),
            rx.divider(),
            rx.cond(
                _S.ed_cargando_lista,
                rx.center(rx.spinner(), padding="2rem", width="100%"),
                rx.vstack(
                    rx.foreach(_S.ed_lista_ext, _item_lista),
                    spacing="1", width="100%", max_height="62vh", overflow_y="auto",
                    padding_right="4px",
                ),
            ),
            spacing="4", width="100%", align="start",
        ),
        width="100%",
    )


# ── Panel derecho: historial de ajustes de un concepto ──────────────────────

def _fila_ajuste(a) -> rx.Component:
    en_edicion = _S.hist_edit_id == a["id"]
    return rx.box(
        rx.cond(
            en_edicion,
            rx.flex(
                rx.input(value=_S.hist_edit_monto, on_change=lambda v: _S.set_hist_edit("monto", v),
                         type="number", size="1", width="110px"),
                rx.input(value=_S.hist_edit_motivo, on_change=lambda v: _S.set_hist_edit("motivo", v),
                         placeholder="Motivo", size="1", flex_grow="1"),
                rx.button("Guardar", size="1", on_click=_S.confirmar_edit_ajuste),
                rx.button("Cancelar", size="1", variant="soft", on_click=_S.cancelar_edit_ajuste),
                gap="2", width="100%", align="center", wrap="wrap",
            ),
            rx.flex(
                rx.text(a["fecha"], size="1", color_scheme="gray", width="10em",
                        flex_shrink="0"),
                rx.text(a["monto"], size="1", weight="bold", width="5em", flex_shrink="0"),
                rx.text(a["motivo"], size="1", flex_grow="1", min_width="0"),
                rx.text(a["usuario"], size="1", color_scheme="gray", flex_shrink="0"),
                rx.button(rx.icon("pencil", size=13), size="1", variant="ghost",
                          on_click=lambda: _S.iniciar_edit_ajuste(a)),
                rx.button(rx.icon("trash-2", size=13), size="1", variant="ghost",
                          color_scheme="red", on_click=lambda: _S.borrar_ajuste(a["id"])),
                gap="2", width="100%", align="center", wrap="wrap",
            ),
        ),
        padding="6px 0",
        border_bottom=_LINE,
    )


def _indicador_ajustes(cod: str) -> rx.Component:
    return rx.cond(
        _S.ed_ajustes_conteo[cod].to(int) > 0,
        rx.vstack(
            rx.button(
                rx.cond(
                    _S.hist_abierto == cod,
                    rx.icon("chevron-down", size=13),
                    rx.icon("chevron-right", size=13),
                ),
                _S.ed_ajustes_conteo[cod].to_string() + " ajuste(s) registrado(s)",
                size="1", variant="ghost", color_scheme="blue",
                on_click=lambda: _S.ver_ajustes(cod),
            ),
            rx.cond(
                _S.hist_abierto == cod,
                rx.box(
                    rx.foreach(_S.hist_ajustes, _fila_ajuste),
                    padding="4px 12px",
                    border=_LINE,
                    border_radius="8px",
                    width="100%",
                    background=_SURFACE,
                ),
            ),
            spacing="1", width="100%", align="start",
        ),
    )


def _campo_concepto(cod: str, label: str) -> rx.Component:
    total = rx.input(
        value=_S.ed_campos[cod], on_change=lambda v: _S.set_ed_campo(cod, v),
        size="2", width="150px", type="number",
    )
    mas = rx.button(
        rx.icon("plus", size=14), size="1", variant="ghost",
        on_click=lambda: _S.abrir_ajuste(cod),
        title="Ajuste incremental con motivo", flex_shrink="0",
    )

    if cod in _HORAS_KEYS:
        kc, kv = _HORAS_KEYS[cod]
        etiqueta = rx.vstack(
            rx.text(label, size="2"),
            rx.text(
                _S.ed_datos[kc] + " h  ×  $" + _S.ed_datos[kv] + " /hora",
                size="1", color_scheme="gray",
            ),
            spacing="0", align="start", flex_grow="1", min_width="0",
        )
    else:
        etiqueta = rx.text(label, size="2", flex_grow="1", min_width="0")

    return rx.vstack(
        rx.flex(
            etiqueta, total, mas,
            align="center", gap="3", width="100%",
            padding="5px 8px", border_radius="6px",
            _hover={"background": "var(--gray-3)"},
        ),
        _indicador_ajustes(cod),
        spacing="1", width="100%", align="start",
    )


def _seccion(titulo: str, campos: list, *, acento: str) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.box(width="8px", height="8px", border_radius="9999px",
                   background=f"var(--{acento}-9)"),
            rx.text(titulo, size="3", weight="bold"),
            spacing="2", align="center", margin_bottom="6px",
        ),
        rx.vstack(
            *[_campo_concepto(cod, lbl) for cod, lbl in campos],
            spacing="1", width="100%",
        ),
        padding="14px 16px",
        border=_LINE,
        border_left=f"3px solid var(--{acento}-8)",
        border_radius=_RADIUS,
        background=_SURFACE,
        width="100%",
    )


def _dato(label: str, k: str, *, tipo: str = "text", opciones=None) -> rx.Component:
    if opciones is not None:
        ctrl = rx.select(opciones, value=_S.ed_datos[k], size="2", width="100%",
                         on_change=lambda v: _S.set_ed_dato(k, v))
    else:
        ctrl = rx.input(value=_S.ed_datos[k], on_change=lambda v: _S.set_ed_dato(k, v),
                        type=tipo, size="2", width="100%")
    return rx.vstack(
        rx.text(label, size="1", weight="bold", color_scheme="gray"),
        ctrl, spacing="1", width="100%",
    )


def _dialogo_ajuste() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Ajuste de concepto — " + _S.aj_abierto),
            rx.vstack(
                rx.text("Valor actual: $" + _S.ed_campos[_S.aj_abierto], size="2",
                        color_scheme="gray"),
                rx.text("Monto a agregar (no puede ser 0; admite negativo en Ajuste Cuadre)",
                        size="1", weight="bold"),
                rx.input(value=_S.aj_monto, on_change=lambda v: _S.set_aj("monto", v),
                         type="number", width="100%"),
                rx.text("Motivo (opcional)", size="1", weight="bold"),
                rx.input(value=_S.aj_motivo, on_change=lambda v: _S.set_aj("motivo", v), width="100%"),
                rx.flex(
                    rx.dialog.close(rx.button("Cancelar", variant="soft", on_click=_S.cerrar_ajuste)),
                    rx.button("Aplicar", on_click=_S.confirmar_ajuste),
                    justify="end", gap="2", margin_top="1rem", width="100%",
                ),
                spacing="3",
            ),
            max_width="460px",
        ),
        open=_S.aj_abierto != "", on_open_change=_S.cerrar_ajuste,
    )


def _totales() -> rx.Component:
    def celda(caption: str, valor: rx.Var, *, color: str, grande: bool = False) -> rx.Component:
        return rx.vstack(
            rx.text(caption, size="1", color_scheme="gray", weight="bold"),
            rx.text("$" + valor.to_string(), size=("6" if grande else "4"),
                    weight="bold", color=color),
            spacing="1", align="start", min_width="8em",
        )

    return rx.flex(
        celda("Ingresos", _S.ed_total_ingresos, color="var(--grass-11)"),
        celda("Descuentos", _S.ed_total_descuentos, color="var(--red-11)"),
        rx.divider(orientation="vertical", height="2.5rem"),
        celda("Líquido a recibir", _S.ed_total_liquido, grande=True,
              color=rx.cond(_S.ed_total_liquido < 0, "var(--red-11)", "var(--blue-11)")),
        gap="5", align="center", wrap="wrap",
        padding="14px 18px", border=_LINE, border_radius=_RADIUS, background=_SURFACE,
        width="100%",
    )


def _cabecera() -> rx.Component:
    return rx.flex(
        rx.heading(_S.ed_datos["nombre"], size="5", flex_grow="1", min_width="0"),
        rx.flex(
            rx.button(
                rx.icon("refresh-cw", size=15), "Recalcular liquidación",
                on_click=_S.recalcular, size="2", variant="solid", color_scheme="blue",
            ),
            rx.button(rx.icon("x", size=15), on_click=_S.cerrar, size="2", variant="soft",
                      color_scheme="gray", title="Cerrar"),
            gap="2", align="center", flex_shrink="0",
        ),
        justify="between", align="center", gap="3", wrap="wrap", width="100%",
    )


def _barra_acciones() -> rx.Component:
    return rx.box(
        rx.divider(margin_bottom="14px"),
        rx.flex(
            rx.flex(
                rx.button("Guardar cambios", on_click=_S.guardar, size="3",
                          color_scheme="blue", disabled=_S.ed_fecha_desalineada),
                rx.button(rx.icon("file-text", size=15), "PDF", on_click=_S.generar_pdf,
                          size="3", variant="soft"),
                rx.button(rx.icon("sheet", size=15), "Excel", on_click=_S.generar_excel,
                          size="3", variant="soft"),
                gap="2", align="center", wrap="wrap",
            ),
            rx.cond(
                AuthState.es_admin,
                rx.alert_dialog.root(
                    rx.alert_dialog.trigger(
                        rx.button(rx.icon("trash-2", size=15), "Eliminar", size="3",
                                  color_scheme="red", variant="ghost")),
                    rx.alert_dialog.content(
                        rx.alert_dialog.title("Eliminar liquidación"),
                        rx.alert_dialog.description(
                            "No se puede deshacer, pero queda un respaldo interno."),
                        rx.flex(
                            rx.alert_dialog.cancel(rx.button("Cancelar", variant="soft")),
                            rx.alert_dialog.action(
                                rx.button("Sí, eliminar", color_scheme="red",
                                          on_click=_S.eliminar)),
                            gap="3", justify="end", margin_top="1rem",
                        ),
                    ),
                ),
            ),
            justify="between", align="center", gap="3", wrap="wrap", width="100%",
        ),
        width="100%",
    )


def _vacio() -> rx.Component:
    return card(
        rx.center(
            rx.vstack(
                rx.icon("file-pen", size=40, color="var(--gray-8)"),
                rx.heading("Ninguna liquidación seleccionada", size="4", color_scheme="gray"),
                rx.text("Elegí una liquidación de la lista para corregirla campo por campo.",
                        size="2", color_scheme="gray", text_align="center"),
                spacing="3", align="center", max_width="26em",
            ),
            min_height="320px", width="100%",
        ),
        width="100%",
    )


def _formulario() -> rx.Component:
    return rx.cond(
        _S.ed_id != "",
        card(
            rx.vstack(
                _cabecera(),
                rx.cond(_S.ed_msg != "", rx.callout(_S.ed_msg, size="1")),
                rx.cond(
                    _S.ed_fecha_desalineada,
                    rx.callout(
                        "La fecha de salida cambió y los valores en pantalla NO se "
                        "recalcularon. Pulsá «Recalcular liquidación» antes de guardar.",
                        color_scheme="amber", size="1",
                    ),
                ),
                rx.box(
                    rx.hstack(
                        rx.box(width="8px", height="8px", border_radius="9999px",
                               background="var(--blue-9)"),
                        rx.text("DATOS DEL EMPLEADO", size="3", weight="bold"),
                        spacing="2", align="center", margin_bottom="10px",
                    ),
                    rx.grid(
                        _dato("Cédula", "cedula"),
                        _dato("Cargo", "cargo"),
                        _dato("Sección", "seccion"),
                        _dato("Fecha de ingreso", "fecha_ingreso", tipo="date"),
                        _dato("Fecha de salida", "fecha_salida", tipo="date"),
                        _dato("Motivo", "motivo", opciones=_S.ed_motivo_opciones),
                        _dato("Estado", "estado", opciones=ESTADOS),
                        columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                        spacing="4", width="100%",
                    ),
                    padding="14px 16px", border=_LINE, border_radius=_RADIUS,
                    background=_SURFACE, width="100%",
                ),
                _seccion("CONCEPTOS DE REMUNERACIÓN", SEC_REMUNERACION, acento="grass"),
                _seccion("CONCEPTOS DE BENEFICIOS", SEC_BENEFICIOS, acento="grass"),
                _seccion("DESCUENTOS", SEC_DESCUENTOS, acento="red"),
                _totales(),
                _barra_acciones(),
                _dialogo_ajuste(),
                spacing="5", width="100%",
            ),
            width="100%",
        ),
        _vacio(),
    )


@rx.page(
    route="/liquidaciones/editor",
    title="INSEVIG — Editor de liquidaciones",
    on_load=[AuthState.cargar_sesion, LiquidacionesEditorState.cargar_lista],
)
def editor() -> rx.Component:
    return pagina(
        subnav("/liquidaciones/editor"),
        page_heading("Editor de liquidaciones",
                     "Corregir una liquidación guardada campo por campo, con ajustes y recálculo."),
        rx.grid(
            _lista(),
            _formulario(),
            columns=rx.breakpoints(initial="1", lg="340px minmax(0, 1fr)"),
            spacing="4", width="100%", align="start",
        ),
        requiere=("liquidaciones", "ver"),
    )
