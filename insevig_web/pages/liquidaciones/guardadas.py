"""Gestión de Liquidaciones — paridad con la pantalla `_abrir_pantalla_pagos`
del `.pyw` (ver docs/modulos/liquidaciones_gestion_UI.md): filtros, tabla con
resaltado por color/estado, acción por estado (flujo de aprobación completo),
panel de detalle rico (color, seguimiento de firma/cobro, observaciones,
historial de estados), y barra de acciones (Excel, Bot MRL, eliminar, PDF)."""

from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, scroll_x
from insevig_web.pages.liquidaciones._nav import subnav
from insevig_web.states.auth_state import AuthState
from insevig_web.states.liquidaciones_guardadas_state import (
    COLORES_ETIQUETA,
    ESTADOS,
    FORMAS_PAGO,
    LUGARES_FIRMA,
    LiquidacionesGuardadasState,
)

_S = LiquidacionesGuardadasState
_SEL = {
    "padding": "6px 8px", "borderRadius": "6px", "border": "1px solid var(--gray-6)",
    "background": "var(--color-panel-solid)", "color": "var(--gray-12)", "fontSize": "13px",
}
_ESTADO_COLOR = (
    ("generada", "blue"), ("aprobado", "cyan"), ("registrado_mrl", "cyan"),
    ("cheque_listo", "amber"), ("consignada", "orange"), ("pagado", "green"),
    ("legalizada_mrl", "green"), ("cancelado", "red"), ("borrador", "gray"),
)


def _badge_estado(estado: rx.Var) -> rx.Component:
    return rx.badge(estado, color_scheme=rx.match(estado, *_ESTADO_COLOR, "gray"))


# ── Fila de la tabla ─────────────────────────────────────────────────────────

def _accion_fila(f) -> rx.Component:
    """Botón de acción según el estado de la fila (uno solo, o nada)."""
    e = f["estado"]
    ids = rx.Var.create([f["id"]])
    return rx.match(
        e,
        ("generada", rx.button("Autorizar", size="1", variant="soft", color_scheme="cyan",
                               on_click=lambda: _S.abrir_accion("autorizar", ids))),
        ("aprobado", rx.button("Registrar MRL", size="1", variant="soft",
                               on_click=lambda: _S.abrir_accion("avance", ids, "registrado_mrl"))),
        ("registrado_mrl", rx.button("Cheque listo", size="1", variant="soft",
                                     on_click=lambda: _S.abrir_accion("cheque", ids))),
        ("cheque_listo", rx.button("Pagar/Consignar", size="1", variant="soft", color_scheme="amber",
                                   on_click=lambda: _S.abrir_accion("pago", ids))),
        ("pagado", rx.button("Legalizar MRL", size="1", variant="soft",
                             on_click=lambda: _S.abrir_accion("avance", ids, "legalizada_mrl"))),
        ("consignada", rx.button("Legalizar MRL", size="1", variant="soft",
                                 on_click=lambda: _S.abrir_accion("avance", ids, "legalizada_mrl"))),
        rx.fragment(),
    )


def _fila(f) -> rx.Component:
    color = f["color_etiqueta"].to(str)
    neg = f["total_liquido"].to(float) < 0
    return rx.table.row(
        rx.table.cell(rx.checkbox(
            checked=_S.seleccion.contains(f["id"]),
            on_change=lambda _v: _S.toggle_seleccion(f["id"]),
        )),
        rx.table.cell(f["empleado_cedula"]),
        rx.table.cell(f["nombre"]),
        rx.table.cell(f["codigo_lote"]),
        rx.table.cell(_badge_estado(f["estado"])),
        rx.table.cell(f["fecha_salida"]),
        rx.table.cell(f["created_at"].to(str).split("T")[0]),
        rx.table.cell(
            rx.text("$" + f["total_liquido"].to_string(),
                    color=rx.cond(neg, "var(--red-11)", "inherit"),
                    weight=rx.cond(neg, "bold", "regular")),
        ),
        rx.table.cell(rx.text(
            rx.cond(
                (f["forma_pago"].to(str) == "") | (f["forma_pago"].to(str) == "null"),
                "", f["forma_pago"].to(str),
            )
            + rx.cond(
                (f["comprobante_pago"].to(str) != "") & (f["comprobante_pago"].to(str) != "null"),
                " · " + f["comprobante_pago"].to(str), "",
            ),
            size="1",
        )),
        rx.table.cell(rx.hstack(
            rx.button("Ver", on_click=lambda: _S.ver_detalle(f["id"]), size="1", variant="soft"),
            _accion_fila(f),
            spacing="1", wrap="wrap",
        )),
        style=rx.cond(
            color != "",
            {"background": color, "backgroundBlendMode": "lighten"},
            rx.cond(f["estado"] == "generada", {"background": "var(--amber-2)"}, {}),
        ),
    )


# ── Panel de detalle ─────────────────────────────────────────────────────────

def _campo_seg(label: str, campo: str, *, tipo: str = "text", opciones=None) -> rx.Component:
    if opciones is not None:
        control = rx.select(
            opciones, value=_S.seg[campo], placeholder=label, size="1", width="100%",
            on_change=lambda v: _S.set_seg(campo, v),
        )
    else:
        control = rx.input(
            value=_S.seg[campo], on_change=lambda v: _S.set_seg(campo, v),
            type=tipo, size="1", width="100%",
        )
    return rx.vstack(rx.text(label, size="1", weight="bold"), control, spacing="1", width="100%")


def _swatch(nombre: str, hexv: str) -> rx.Component:
    return rx.box(
        width="22px", height="22px", border_radius="4px", background=hexv,
        border=rx.cond(_S.seg["color_etiqueta"] == hexv, "3px solid var(--gray-12)", "1px solid var(--gray-7)"),
        cursor="pointer", title=nombre,
        on_click=lambda: _S.set_color(hexv),
    )


def _tabla_conceptos(titulo: str, filas, total: rx.Var) -> rx.Component:
    return rx.vstack(
        rx.text(titulo, size="1", weight="bold"),
        scroll_x(rx.table.root(
            rx.table.body(rx.foreach(filas, lambda c: rx.table.row(
                rx.table.cell(c["concepto_nombre"], padding_y="2px"),
                rx.table.cell("$" + c["valor_total"].to_string(), padding_y="2px"),
            ))),
            variant="surface", size="1", width="100%",
        )),
        rx.text("Total: $" + total.to_string(), size="1", weight="bold", align_self="end"),
        spacing="1", width="100%",
    )


def _detalle() -> rx.Component:
    return rx.cond(
        _S.detalle_id != "",
        card(
            rx.vstack(
                rx.flex(
                    rx.vstack(
                        rx.heading(
                            f'{_S.detalle["empleado_apellidos"]} {_S.detalle["empleado_nombres"]}',
                            size="5",
                        ),
                        rx.text(
                            f'{_S.detalle["empleado_cedula"]}  ·  lote '
                            f'{_S.detalle["codigo_lote"]}  ·  salida {_S.detalle["fecha_salida"]}',
                            size="1", color_scheme="gray",
                        ),
                        spacing="1", align="start", flex_grow="1", min_width="0",
                    ),
                    rx.vstack(
                        rx.heading(f'${_S.detalle["total_liquido"]}', size="6"),
                        _badge_estado(_S.detalle["estado"]),
                        spacing="1", align="end", flex_shrink="0",
                    ),
                    rx.button(rx.icon("x", size=14), on_click=_S.cerrar_detalle,
                              variant="soft", size="1", color_scheme="gray"),
                    justify="between", align="start", gap="3", width="100%", wrap="wrap",
                ),
                rx.cond(_S.detalle_msg != "", rx.callout(_S.detalle_msg, color_scheme="red", size="1")),
                rx.cond(
                    _S.detalle.contains("id"),
                    rx.vstack(
                        # ── Desglose ingresos / egresos ──
                        rx.text("DESGLOSE", size="1", weight="bold"),
                        rx.grid(
                            _tabla_conceptos("Ingresos", _S.conceptos_ingreso, _S.total_ingresos_detalle),
                            _tabla_conceptos("Egresos", _S.conceptos_egreso, _S.total_egresos_detalle),
                            columns=rx.breakpoints(initial="1", md="2"), spacing="3", width="100%",
                        ),
                        rx.hstack(
                            rx.cond(
                                AuthState.permisos_flat.contains("liquidaciones:editar"),
                                rx.cond(
                                    _S.editando,
                                    rx.hstack(
                                        rx.button("Guardar cambios", on_click=_S.guardar_edicion, size="1"),
                                        rx.button("Cancelar", on_click=_S.cancelar_edicion, size="1", variant="soft"),
                                        spacing="2",
                                    ),
                                    rx.button("Editar valores", on_click=_S.abrir_edicion, size="1", variant="ghost"),
                                ),
                            ),
                            rx.cond(_S.edit_msg != "", rx.text(_S.edit_msg, color_scheme="amber", size="1")),
                            spacing="2", align="center",
                        ),
                        rx.cond(
                            _S.editando,
                            scroll_x(rx.table.root(
                                rx.table.body(rx.foreach(_S.conceptos_editables, lambda c: rx.table.row(
                                    rx.table.cell(c["concepto_nombre"]),
                                    rx.table.cell(rx.input(
                                        value=c["edit_valor"], size="1", width="110px",
                                        on_change=lambda v: _S.set_edit_valor(c["concepto_codigo"], v),
                                    )),
                                ))),
                                variant="surface", size="1",
                            )),
                        ),
                        rx.divider(),
                        # ── Color ──
                        rx.hstack(
                            rx.text("COLOR", size="1", weight="bold"),
                            *[_swatch(n, h) for n, h in COLORES_ETIQUETA],
                            rx.button("✕", size="1", variant="ghost", on_click=lambda: _S.set_color("")),
                            spacing="2", align="center", wrap="wrap",
                        ),
                        rx.divider(),
                        # ── Seguimiento de firma y cobro ──
                        rx.text("SEGUIMIENTO DE FIRMA Y COBRO", size="1", weight="bold"),
                        rx.grid(
                            _campo_seg("Lugar donde firma", "lugar_firma", opciones=LUGARES_FIRMA),
                            _campo_seg("N° de acta", "numero_acta"),
                            _campo_seg("Fecha firma de acuerdo", "fecha_firma_acuerdo", tipo="date"),
                            _campo_seg("Fecha lista para cobro", "fecha_lista_cobro", tipo="date"),
                            _campo_seg("Fecha citado para cobro", "fecha_citado_cobro", tipo="date"),
                            _campo_seg("Fecha consignación / acercamiento", "fecha_consignacion", tipo="date"),
                            columns=rx.breakpoints(initial="1", sm="2", lg="3"), spacing="2", width="100%",
                        ),
                        rx.vstack(
                            rx.text("OBSERVACIONES", size="1", weight="bold"),
                            rx.text_area(
                                value=_S.seg["observaciones"], rows="4", width="100%",
                                on_change=lambda v: _S.set_seg("observaciones", v),
                            ),
                            spacing="1", width="100%",
                        ),
                        rx.hstack(
                            rx.button("💾 Guardar todo (color, seguimiento y observaciones)",
                                      on_click=_S.guardar_seguimiento, size="1"),
                            rx.cond(_S.seg_msg != "", rx.text(_S.seg_msg, size="1", color_scheme="green")),
                            spacing="2", align="center",
                        ),
                        rx.divider(),
                        # ── Historial de estados ──
                        rx.text("HISTORIAL DE ESTADOS", size="1", weight="bold"),
                        rx.cond(
                            _S.historial.length() > 0,
                            rx.vstack(
                                rx.foreach(_S.historial, lambda h: rx.text(
                                    f'{h["created_at"].to(str).split("T")[0]}  —  {h["estado"]}'
                                    f'  ·  {h["usuario"]}',
                                    size="1",
                                )),
                                spacing="0", align="start",
                            ),
                            rx.text("Sin cambios de estado registrados.", size="1", color_scheme="gray"),
                        ),
                        rx.divider(),
                        # ── Acciones ──
                        rx.hstack(
                            rx.button("PDF", on_click=lambda: _S.generar_pdf(_S.detalle_id),
                                      size="1", variant="soft"),
                            rx.cond(
                                AuthState.es_admin,
                                rx.alert_dialog.root(
                                    rx.alert_dialog.trigger(
                                        rx.button("Eliminar", size="1", color_scheme="red", variant="soft")),
                                    rx.alert_dialog.content(
                                        rx.alert_dialog.title("Eliminar liquidación"),
                                        rx.alert_dialog.description(
                                            "Se eliminará esta liquidación. No se puede deshacer, "
                                            "pero queda un respaldo interno."
                                        ),
                                        rx.hstack(
                                            rx.alert_dialog.cancel(rx.button("Cancelar", variant="soft")),
                                            rx.alert_dialog.action(rx.button(
                                                "Sí, eliminar", color_scheme="red",
                                                on_click=lambda: _S.eliminar(_S.detalle_id))),
                                            spacing="3", justify="end", margin_top="1rem",
                                        ),
                                    ),
                                ),
                            ),
                            spacing="2", align="center", wrap="wrap",
                        ),
                        spacing="3", width="100%",
                    ),
                ),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
    )


# ── Diálogos de acción (flujo de estados) ────────────────────────────────────

def _dialogos_accion() -> rx.Component:
    n = _S.accion_ids.length()
    return rx.fragment(
        # Autorizar
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("Confirmar autorización"),
                rx.vstack(
                    rx.text("Aplica a " + n.to_string() + " liquidación(es).", size="1", color_scheme="gray"),
                    rx.text("Autorizado por", size="1", weight="bold"),
                    rx.input(value=_S.f_autorizado_por,
                             on_change=lambda v: _S.set_accion_campo("autorizado_por", v), width="100%"),
                    rx.hstack(
                        rx.dialog.close(rx.button("Cancelar", variant="soft")),
                        rx.button("Confirmar autorización", on_click=_S.confirmar_autorizar),
                        justify="end", spacing="2", margin_top="1rem",
                    ),
                    spacing="2",
                ),
            ),
            open=_S.accion_abierta == "autorizar", on_open_change=_S.cerrar_accion,
        ),
        # Avance genérico (Registrar MRL / Legalizar MRL)
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("Confirmar avance de estado"),
                rx.vstack(
                    rx.text("Aplica a " + n.to_string() + " liquidación(es) → "
                            + _S.accion_estado, size="1", color_scheme="gray"),
                    rx.text("Responsable", size="1", weight="bold"),
                    rx.input(value=_S.f_responsable,
                             on_change=lambda v: _S.set_accion_campo("responsable", v), width="100%"),
                    rx.hstack(
                        rx.dialog.close(rx.button("Cancelar", variant="soft")),
                        rx.button("Confirmar", on_click=_S.confirmar_avance),
                        justify="end", spacing="2", margin_top="1rem",
                    ),
                    spacing="2",
                ),
            ),
            open=_S.accion_abierta == "avance", on_open_change=_S.cerrar_accion,
        ),
        # Cheque listo
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("Marcar cheque listo"),
                rx.vstack(
                    rx.text("Aplica a " + n.to_string() + " liquidación(es).", size="1", color_scheme="gray"),
                    rx.text("Forma de pago", size="1", weight="bold"),
                    rx.select(FORMAS_PAGO, value=_S.f_forma_pago, width="100%",
                              on_change=lambda v: _S.set_accion_campo("forma_pago", v)),
                    rx.cond(
                        n == 1,
                        rx.fragment(
                            rx.text("N° de cheque / comprobante", size="1", weight="bold"),
                            rx.input(value=_S.f_comprobante,
                                     on_change=lambda v: _S.set_accion_campo("comprobante", v), width="100%"),
                        ),
                        rx.text("En lote, el número de cada cheque se completa después "
                                "desde el panel de detalle.", size="1", color_scheme="gray"),
                    ),
                    rx.hstack(
                        rx.dialog.close(rx.button("Cancelar", variant="soft")),
                        rx.button("Confirmar", on_click=_S.confirmar_cheque),
                        justify="end", spacing="2", margin_top="1rem",
                    ),
                    spacing="2",
                ),
            ),
            open=_S.accion_abierta == "cheque", on_open_change=_S.cerrar_accion,
        ),
        # Pagar / Consignar
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("Marcar como pagada o consignada"),
                rx.vstack(
                    rx.text("Aplica a " + n.to_string() + " liquidación(es).", size="1", color_scheme="gray"),
                    rx.text("Fecha", size="1", weight="bold"),
                    rx.input(value=_S.f_fecha, type="date",
                             on_change=lambda v: _S.set_accion_campo("fecha", v), width="100%"),
                    rx.hstack(
                        rx.dialog.close(rx.button("Cancelar", variant="soft")),
                        rx.button("Consignada", color_scheme="orange",
                                  on_click=lambda: _S.confirmar_pago("consignada")),
                        rx.button("Pagada", on_click=lambda: _S.confirmar_pago("pagado")),
                        justify="end", spacing="2", margin_top="1rem",
                    ),
                    spacing="2",
                ),
            ),
            open=_S.accion_abierta == "pago", on_open_change=_S.cerrar_accion,
        ),
    )


def _dialogo_grid() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Editar en cuadrícula"),
            rx.text("Los cambios se guardan como ajustes (suma/resta) sobre el valor actual, "
                    "con el motivo indicado. No revierte el trámite, solo corrige montos.",
                    size="1", color_scheme="gray"),
            rx.hstack(
                rx.input(placeholder="Motivo del ajuste", value=_S.grid_motivo,
                         on_change=_S.set_grid_motivo, width="100%", size="2"),
                rx.button("Guardar todos los cambios", on_click=_S.guardar_grid, size="2"),
                spacing="2", width="100%", margin_y="0.5rem",
            ),
            rx.cond(_S.grid_msg != "", rx.callout(_S.grid_msg, size="1")),
            rx.scroll_area(
                rx.table.root(
                    rx.table.header(rx.table.row(
                        rx.table.column_header_cell("Concepto"),
                        rx.foreach(_S.grid_liqs, lambda lq: rx.table.column_header_cell(lq["nombre"])),
                    )),
                    rx.table.body(rx.foreach(_S.grid_matriz, lambda fila: rx.table.row(
                        rx.table.cell(fila.label, style={"whiteSpace": "nowrap"}),
                        rx.foreach(fila.celdas, lambda celda: rx.table.cell(rx.input(
                            value=celda.valor,
                            on_change=lambda v: _S.set_grid_valor(celda.clave, v),
                            size="1", width="90px",
                        ))),
                    ))),
                    variant="surface", size="1",
                ),
                type="auto", scrollbars="both", style={"maxHeight": "60vh"},
            ),
            rx.hstack(
                rx.dialog.close(rx.button("Cerrar", variant="soft", on_click=_S.cerrar_grid)),
                justify="end", width="100%", margin_top="1rem",
            ),
            max_width="900px",
        ),
        open=_S.grid_abierta, on_open_change=_S.cerrar_grid,
    )


def _dialogo_cuadre() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Cuadre masivo (MRL)"),
            rx.text("Una línea por liquidación: cédula, fecha de salida (dd/mm/aaaa), monto. "
                    "El monto se SUMA al ajuste de cuadre existente (admite negativo).",
                    size="1", color_scheme="gray"),
            rx.text_area(
                value=_S.cuadre_texto, on_change=_S.set_cuadre_texto, rows="8", width="100%",
                placeholder="0704090805, 31/07/2026, 0.01\n0921509527, 15/08/2026, -0.02",
            ),
            rx.cond(_S.cuadre_msg != "", rx.callout(_S.cuadre_msg, size="1")),
            rx.hstack(
                rx.dialog.close(rx.button("Cerrar", variant="soft", on_click=_S.cerrar_cuadre)),
                rx.button("Aplicar cuadre", on_click=_S.aplicar_cuadre),
                justify="end", width="100%", margin_top="1rem", spacing="2",
            ),
            max_width="560px",
        ),
        open=_S.cuadre_abierto, on_open_change=_S.cerrar_cuadre,
    )


# ── Página ───────────────────────────────────────────────────────────────────

def _chip(label: str, valor: str) -> rx.Component:
    return rx.button(
        label, size="1",
        variant=rx.cond(_S.estado_filtro == valor, "solid", "soft"),
        on_click=lambda: [_S.set_estado_filtro(valor), _S.buscar()],
    )


@rx.page(
    route="/liquidaciones/guardadas",
    title="INSEVIG — Gestión de liquidaciones",
    on_load=[AuthState.cargar_sesion, LiquidacionesGuardadasState.buscar],
)
def guardadas() -> rx.Component:
    return pagina(
        subnav("/liquidaciones/guardadas"),
        page_heading("Gestión de liquidaciones", _S.conteo),
        rx.hstack(
            rx.link(rx.button(rx.icon("arrow-left", size=14), "Generar", variant="soft", size="2"),
                    href="/liquidaciones"),
            rx.link(rx.button(rx.icon("pencil", size=14), "Editor", variant="soft", size="2"),
                    href="/liquidaciones/editor"),
            rx.link(rx.button(rx.icon("wallet", size=14), "Descuentos pendientes", variant="soft", size="2"),
                    href="/liquidaciones/descuentos-pendientes"),
            spacing="2", wrap="wrap",
        ),
        rx.vstack(
            card(
                rx.vstack(
                    rx.hstack(
                        rx.text("Filtrar por:", size="1", weight="bold"),
                        _chip("Todos", ""),
                        *[_chip(e.replace("_", " ").capitalize(), e) for e in ESTADOS],
                        spacing="1", wrap="wrap", align="center",
                    ),
                    rx.hstack(
                        rx.input(value=_S.texto, on_change=_S.set_texto,
                                 placeholder="cédula, nombre o código de lote…", width="240px", size="2"),
                        rx.select(_S.lote_opciones, placeholder="Lote", size="2",
                                  on_change=lambda v: _S.set_filtro("lote", v)),
                        rx.input(value=_S.f_desde, on_change=lambda v: _S.set_filtro("desde", v),
                                 type="date", size="2", placeholder="Desde"),
                        rx.input(value=_S.f_hasta, on_change=lambda v: _S.set_filtro("hasta", v),
                                 type="date", size="2", placeholder="Hasta"),
                        rx.select(
                            ["-created_at", "created_at", "-fecha_salida", "fecha_salida",
                             "empleado_apellidos", "-total_liquido", "estado", "codigo_lote"],
                            placeholder="Ordenar por", size="2",
                            on_change=lambda v: _S.set_filtro("orden", v),
                        ),
                        rx.button("Aplicar filtro", on_click=_S.buscar, size="2"),
                        rx.button("Limpiar", on_click=lambda: [_S.limpiar_filtros(), _S.buscar()],
                                  size="2", variant="ghost"),
                        spacing="2", wrap="wrap", align="center",
                    ),
                    rx.hstack(
                        rx.button(rx.icon("refresh-cw", size=14), "Actualizar",
                                  on_click=_S.buscar, size="1", variant="soft"),
                        rx.button(rx.icon("download", size=14), "Exportar a Excel",
                                  on_click=_S.exportar_listado, size="1", variant="soft"),
                        rx.button(rx.icon("bot", size=14),
                                  "Bot MRL (" + _S.seleccion.length().to_string() + ")",
                                  on_click=_S.generar_bot_mrl, size="1", variant="soft",
                                  disabled=_S.seleccion.length() == 0),
                        rx.button(rx.icon("grid-3x3", size=14),
                                  "Editar en cuadrícula (" + _S.seleccion.length().to_string() + ")",
                                  on_click=_S.abrir_grid, size="1", variant="soft",
                                  disabled=_S.seleccion.length() == 0),
                        rx.button(rx.icon("calculator", size=14), "Cuadre masivo",
                                  on_click=_S.abrir_cuadre, size="1", variant="soft"),
                        spacing="2", wrap="wrap",
                    ),
                    spacing="2", width="100%",
                ),
                width="100%",
            ),
            rx.cond(_S.msg != "", rx.callout(_S.msg, size="1")),
            _detalle(),
            _dialogos_accion(),
            _dialogo_grid(),
            _dialogo_cuadre(),
            rx.cond(
                _S.cargando,
                rx.center(rx.spinner(), padding="1rem"),
                scroll_x(rx.table.root(
                    rx.table.header(rx.table.row(*[
                        rx.table.column_header_cell(c, style={"background": theme.PRIMARY, "color": "white"})
                        for c in ("", "Cédula", "Nombres", "Lote", "Estado", "Fecha salida",
                                  "Registro", "Total", "Info de pago", "")
                    ])),
                    rx.table.body(rx.foreach(_S.filas, _fila)),
                    variant="surface", size="1", width="100%",
                )),
            ),
            spacing="3", width="100%",
        ),
        requiere=("liquidaciones", "ver"),
    )
