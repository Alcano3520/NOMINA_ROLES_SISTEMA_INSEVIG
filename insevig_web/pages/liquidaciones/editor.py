"""Editor de Liquidaciones — pantalla dedicada maestro-detalle (la 4ta del
sidebar del `.pyw`). Ver docs/modulos/liquidaciones_editor_UI.md."""

from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, scroll_x
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


# ── Panel izquierdo: lista ───────────────────────────────────────────────────

def _item_lista(f) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(f["nombre"], size="1", weight="bold"),
                rx.hstack(
                    rx.text(f["fecha_salida"], size="1", color_scheme="gray"),
                    rx.badge(f["estado_label"], color_scheme=f["estado_color"], size="1"),
                    spacing="1", align="center",
                ),
                spacing="0", align="start",
            ),
            rx.spacer(),
            rx.text(f'${f["total_liquido"]}', size="1"),
            width="100%", align="center",
        ),
        on_click=lambda: _S.abrir(f["id"]),
        padding="6px 8px", border_radius="6px", cursor="pointer",
        background=rx.cond(_S.ed_id == f["id"], theme.HOVER, "transparent"),
        _hover={"background": theme.BG}, width="100%",
    )


def _chip(valor: str, etiqueta: str) -> rx.Component:
    return rx.button(
        etiqueta, size="1",
        variant=rx.cond(_S.ed_estado == valor, "solid", "soft"),
        color_scheme=rx.cond(_S.ed_estado == valor, "blue", "gray"),
        on_click=lambda: _S.set_ed_estado(valor),
    )


def _lista() -> rx.Component:
    return card(
        rx.vstack(
            rx.hstack(
                rx.heading("Editor de Liquidaciones", size="3"),
                rx.spacer(),
                rx.badge(_S.ed_conteo, color_scheme="gray"),
                width="100%", align="center",
            ),
            rx.hstack(
                rx.input(value=_S.ed_texto, on_change=_S.set_ed_texto,
                         placeholder="cédula o nombre…", size="1", width="100%"),
                rx.button("Buscar", on_click=_S.cargar_lista, size="1"),
                spacing="1", width="100%",
            ),
            rx.grid(
                *[_chip(v, e) for v, e in CHIPS_ESTADO],
                columns="3", spacing="1", width="100%",
            ),
            rx.cond(
                _S.ed_cargando_lista,
                rx.center(rx.spinner(), padding="1rem"),
                rx.vstack(
                    rx.foreach(_S.ed_lista_ext, _item_lista),
                    spacing="1", width="100%", max_height="60vh", overflow_y="auto",
                ),
            ),
            spacing="2", width="100%",
        ),
        width="100%",
    )


# ── Panel derecho: formulario ────────────────────────────────────────────────

def _fila_ajuste(a) -> rx.Component:
    en_edicion = _S.hist_edit_id == a["id"]
    return rx.box(
        rx.cond(
            en_edicion,
            rx.hstack(
                rx.input(value=_S.hist_edit_monto, on_change=lambda v: _S.set_hist_edit("monto", v),
                         type="number", size="1", width="100px"),
                rx.input(value=_S.hist_edit_motivo, on_change=lambda v: _S.set_hist_edit("motivo", v),
                         placeholder="motivo", size="1", width="100%"),
                rx.button("Guardar", size="1", on_click=_S.confirmar_edit_ajuste),
                rx.button("Cancelar", size="1", variant="soft", on_click=_S.cancelar_edit_ajuste),
                spacing="1", width="100%", align="center",
            ),
            rx.hstack(
                rx.text(a["fecha"], size="1", color_scheme="gray", width="9em"),
                rx.text(a["monto"], size="1", weight="bold", width="6em"),
                rx.text(a["motivo"], size="1", flex_grow="1"),
                rx.text(a["usuario"], size="1", color_scheme="gray"),
                rx.button("Editar", size="1", variant="ghost",
                          on_click=lambda: _S.iniciar_edit_ajuste(a)),
                rx.button("Eliminar", size="1", variant="ghost", color_scheme="red",
                          on_click=lambda: _S.borrar_ajuste(a["id"])),
                spacing="1", width="100%", align="center",
            ),
        ),
        padding="2px 0",
    )


def _indicador_ajustes(cod: str) -> rx.Component:
    return rx.cond(
        _S.ed_ajustes_conteo[cod].to(int) > 0,
        rx.vstack(
            rx.button(
                _S.ed_ajustes_conteo[cod].to_string() + " ajuste(s) registrado(s) ▾",
                size="1", variant="ghost", color_scheme="blue",
                on_click=lambda: _S.ver_ajustes(cod),
            ),
            rx.cond(
                _S.hist_abierto == cod,
                rx.box(
                    rx.foreach(_S.hist_ajustes, _fila_ajuste),
                    padding="6px 10px", border="1px solid var(--gray-5)",
                    border_radius="6px", width="100%", background=theme.BG,
                ),
            ),
            spacing="1", width="100%", align="start",
        ),
    )


def _campo_concepto(cod: str, label: str) -> rx.Component:
    etiqueta = rx.text(label, size="1", width="16em", flex_shrink="0")
    total = rx.input(
        value=_S.ed_campos[cod], on_change=lambda v: _S.set_ed_campo(cod, v),
        size="1", width="120px", type="number",
    )
    mas = rx.button("+", size="1", variant="soft", on_click=lambda: _S.abrir_ajuste(cod),
                    title="Ajuste incremental con motivo")
    if cod in _HORAS_KEYS:
        kc, kv = _HORAS_KEYS[cod]
        fila = rx.hstack(
            etiqueta,
            rx.vstack(rx.text("cant.", size="1", color_scheme="gray"),
                      rx.input(value=_S.ed_datos[kc], size="1", width="70px", read_only=True),
                      spacing="0"),
            rx.vstack(rx.text("$/hora", size="1", color_scheme="gray"),
                      rx.input(value=_S.ed_datos[kv], size="1", width="80px", read_only=True),
                      spacing="0"),
            rx.vstack(rx.text("total", size="1", color_scheme="gray"), total, spacing="0"),
            mas,
            spacing="2", align="end",
        )
    else:
        fila = rx.hstack(etiqueta, total, mas, spacing="2", align="center")
    return rx.vstack(fila, _indicador_ajustes(cod), spacing="1", width="100%", align="start")


def _seccion(titulo: str, campos: list) -> rx.Component:
    return rx.vstack(
        rx.text(titulo, size="1", weight="bold", color_scheme="blue"),
        rx.divider(margin_y="4px"),
        *[_campo_concepto(cod, lbl) for cod, lbl in campos],
        spacing="1", width="100%",
        border="1px solid var(--gray-5)", border_radius="8px", padding="10px 12px",
    )


def _dato(label: str, k: str, *, tipo: str = "text", opciones=None) -> rx.Component:
    if opciones is not None:
        ctrl = rx.select(opciones, value=_S.ed_datos[k], size="1",
                         on_change=lambda v: _S.set_ed_dato(k, v))
    else:
        ctrl = rx.input(value=_S.ed_datos[k], on_change=lambda v: _S.set_ed_dato(k, v),
                        type=tipo, size="1", width="100%")
    return rx.vstack(rx.text(label, size="1", weight="bold"), ctrl, spacing="0", width="100%")


def _dialogo_ajuste() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Ajuste de concepto — " + _S.aj_abierto),
            rx.vstack(
                rx.text("Valor actual: $" + _S.ed_campos[_S.aj_abierto], size="1", color_scheme="gray"),
                rx.text("Monto a agregar (no puede ser 0; admite negativo en Ajuste Cuadre)",
                        size="1", weight="bold"),
                rx.input(value=_S.aj_monto, on_change=lambda v: _S.set_aj("monto", v),
                         type="number", width="100%"),
                rx.text("Motivo (opcional)", size="1", weight="bold"),
                rx.input(value=_S.aj_motivo, on_change=lambda v: _S.set_aj("motivo", v), width="100%"),
                rx.hstack(
                    rx.dialog.close(rx.button("Cancelar", variant="soft", on_click=_S.cerrar_ajuste)),
                    rx.button("Aplicar", on_click=_S.confirmar_ajuste),
                    justify="end", spacing="2", margin_top="1rem",
                ),
                spacing="2",
            ),
            max_width="460px",
        ),
        open=_S.aj_abierto != "", on_open_change=_S.cerrar_ajuste,
    )


def _formulario() -> rx.Component:
    return rx.cond(
        _S.ed_id != "",
        card(
            rx.vstack(
                rx.hstack(
                    rx.heading(_S.ed_datos["nombre"], size="4"),
                    rx.spacer(),
                    rx.button("🔄 Recalcular Liquidación", on_click=_S.recalcular,
                              size="1", variant="soft"),
                    rx.button("Cerrar", on_click=_S.cerrar, size="1", variant="ghost"),
                    width="100%", align="center", wrap="wrap",
                ),
                rx.cond(_S.ed_msg != "", rx.callout(_S.ed_msg, size="1")),
                rx.cond(
                    _S.ed_fecha_desalineada,
                    rx.callout(
                        "La fecha de salida cambió y los valores en pantalla NO se recalcularon. "
                        "Pulsá 'Recalcular Liquidación' antes de guardar.",
                        color_scheme="amber", size="1",
                    ),
                ),
                # ── DATOS DEL EMPLEADO ──
                rx.text("DATOS DEL EMPLEADO", size="1", weight="bold", color_scheme="blue"),
                rx.grid(
                    _dato("Cédula", "cedula"),
                    _dato("Cargo", "cargo"),
                    _dato("Sección", "seccion"),
                    _dato("Fecha de ingreso", "fecha_ingreso", tipo="date"),
                    _dato("Fecha de salida", "fecha_salida", tipo="date"),
                    _dato("Motivo", "motivo", opciones=_S.ed_motivo_opciones),
                    _dato("Estado", "estado", opciones=ESTADOS),
                    columns=rx.breakpoints(initial="1", sm="2", lg="3"), spacing="2", width="100%",
                ),
                _seccion("CONCEPTOS DE REMUNERACIÓN", SEC_REMUNERACION),
                _seccion("CONCEPTOS DE BENEFICIOS", SEC_BENEFICIOS),
                _seccion("DESCUENTOS", SEC_DESCUENTOS),
                # ── Totales en vivo ──
                rx.hstack(
                    rx.text("Ingresos: $" + _S.ed_total_ingresos.to_string(), size="2", weight="bold"),
                    rx.text("Descuentos: $" + _S.ed_total_descuentos.to_string(), size="2", weight="bold"),
                    rx.text("Líquido: $" + _S.ed_total_liquido.to_string(), size="3", weight="bold",
                            color=rx.cond(_S.ed_total_liquido < 0, "var(--red-11)", "inherit")),
                    spacing="4", wrap="wrap",
                ),
                rx.hstack(
                    rx.button("Guardar cambios", on_click=_S.guardar, size="2",
                              disabled=_S.ed_fecha_desalineada),
                    rx.button("Generar PDF", on_click=_S.generar_pdf, size="2", variant="soft"),
                    rx.button("Generar Excel", on_click=_S.generar_excel, size="2", variant="soft"),
                    rx.cond(
                        AuthState.es_admin,
                        rx.alert_dialog.root(
                            rx.alert_dialog.trigger(
                                rx.button("Eliminar", size="2", color_scheme="red", variant="soft")),
                            rx.alert_dialog.content(
                                rx.alert_dialog.title("Eliminar liquidación"),
                                rx.alert_dialog.description(
                                    "No se puede deshacer, pero queda un respaldo interno."),
                                rx.hstack(
                                    rx.alert_dialog.cancel(rx.button("Cancelar", variant="soft")),
                                    rx.alert_dialog.action(
                                        rx.button("Sí, eliminar", color_scheme="red",
                                                  on_click=_S.eliminar)),
                                    spacing="3", justify="end", margin_top="1rem",
                                ),
                            ),
                        ),
                    ),
                    spacing="2", wrap="wrap",
                ),
                _dialogo_ajuste(),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
        card(rx.text("Seleccioná una liquidación de la lista para editarla.", color_scheme="gray"),
             width="100%"),
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
        rx.hstack(
            rx.link(rx.button("← Gestión", variant="soft", size="2"),
                    href="/liquidaciones/guardadas"),
            spacing="2",
        ),
        scroll_x(rx.grid(
            _lista(),
            _formulario(),
            columns=rx.breakpoints(initial="1", lg="320px 1fr"),
            spacing="3", width="100%",
        )),
        requiere=("liquidaciones", "ver"),
    )
