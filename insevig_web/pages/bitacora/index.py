from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button, scroll_x
from insevig_web.states.auth_state import AuthState
from insevig_web.states.bitacora_state import (
    CAMPOS,
    CAMPOS_FECHA,
    ESTADOS,
    ETIQUETAS,
    FORMAS_PAGO,
    BitacoraState,
)

_S = BitacoraState

_COLS = [
    ("apellidos_nombres", "Empleado"),
    ("cedula", "Cédula"),
    ("cargo", "Puesto"),
    ("fecha_salida", "Fecha salida"),
    ("fecha_cobro", "Fecha cobro"),
    ("hora", "Hora"),
    ("estado", "Estado"),
    ("periodo", "Período"),
]
_TEXTAREA = {"observacion", "en_sistema"}


def _campo(c: str) -> rx.Component:
    etq = ETIQUETAS.get(c, c)
    if c == "qap":
        return rx.hstack(
            rx.checkbox(checked=_S.form["qap"] != "", on_change=lambda _v: _S.toggle_qap()),
            rx.text(etq, size="1"),
            spacing="2", align="center", width="100%",
        )
    if c == "estado":
        control = rx.select(ESTADOS, value=_S.form["estado"],
                            on_change=lambda v: _S.set_campo("estado", v))
    elif c == "forma_pago":
        control = rx.select(FORMAS_PAGO, value=_S.form["forma_pago"],
                            on_change=lambda v: _S.set_campo("forma_pago", v))
    elif c in _TEXTAREA:
        control = rx.text_area(value=_S.form[c], on_change=lambda v: _S.set_campo(c, v),
                               rows="2", width="100%")
    else:
        control = rx.input(
            value=_S.form[c],
            on_change=lambda v, c=c: _S.set_campo(c, v),
            type="date" if c in CAMPOS_FECHA else "text",
            size="2", width="100%",
        )
    extra = (
        rx.cond(_S.cedula_aviso != "", rx.text(_S.cedula_aviso, size="1", color_scheme="amber"))
        if c == "cedula" else rx.fragment()
    )
    boton = (
        rx.button("Generar", on_click=_S.generar_en_sistema, size="1", variant="soft", type="button")
        if c == "en_sistema" else rx.fragment()
    )
    return rx.vstack(
        rx.hstack(rx.text(etq, size="1", weight="bold"), rx.spacer(), boton, width="100%"),
        control, extra,
        spacing="1", width="100%",
    )


def _form() -> rx.Component:
    return card(
        rx.vstack(
            rx.heading(rx.cond(_S.editando_id > 0, "Editar registro", "Nuevo registro"), size="3"),
            rx.grid(
                *[_campo(c) for c in CAMPOS],
                columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                spacing="3", width="100%",
            ),
            rx.hstack(
                primary_button("Guardar", on_click=_S.guardar),
                rx.button("Cancelar", on_click=_S.cerrar_form, variant="soft"),
                spacing="2",
            ),
            rx.cond(_S.msg != "", rx.callout(_S.msg, size="1")),
            spacing="3", width="100%",
        ),
        width="100%",
    )


def _tab_agenda() -> rx.Component:
    return rx.vstack(
        card(
            rx.hstack(
                rx.select(["(todos)", *ESTADOS], default_value="(todos)",
                          on_change=_S.set_filtro_estado),
                rx.select(_S.periodos, default_value="(todos)", on_change=_S.set_filtro_periodo),
                rx.input(value=_S.filtro_texto, on_change=_S.set_filtro_texto,
                         placeholder="nombre o cédula…", width="200px"),
                rx.button("Buscar", on_click=_S.cargar),
                rx.cond(
                    AuthState.permisos_flat.contains("bitacora:crear"),
                    primary_button("Nuevo", on_click=_S.nuevo),
                ),
                spacing="2", wrap="wrap",
            ),
            width="100%",
        ),
        rx.cond(_S.error != "", rx.callout(_S.error, color_scheme="red", size="1")),
        rx.cond(_S.mostrar_form, _form()),
        rx.cond(
            _S.cargando,
            rx.spinner(),
            scroll_x(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            *[
                                rx.table.column_header_cell(
                                    lbl, style={"background": theme.PRIMARY, "color": "white"}
                                )
                                for _k, lbl in [*_COLS, ("", "")]
                            ]
                        )
                    ),
                    rx.table.body(
                        rx.foreach(
                            _S.registros,
                            lambda r: rx.table.row(
                                *[rx.table.cell(r[k].to_string()) for k, _lbl in _COLS],
                                rx.table.cell(
                                    rx.hstack(
                                        rx.button("Editar", on_click=lambda: _S.editar(r),
                                                  size="1", variant="soft"),
                                        rx.cond(
                                            AuthState.permisos_flat.contains("bitacora:editar"),
                                            rx.button("Pagado",
                                                      on_click=lambda: _S.cambiar_estado(r["id"], "PAGADO"),
                                                      size="1", color_scheme="green"),
                                        ),
                                        rx.cond(
                                            AuthState.permisos_flat.contains("bitacora:eliminar"),
                                            rx.button("Eliminar",
                                                      on_click=lambda: _S.eliminar(r["id"]),
                                                      size="1", color_scheme="red", variant="ghost"),
                                        ),
                                        spacing="1",
                                    )
                                ),
                            ),
                        )
                    ),
                    variant="surface", size="1", width="100%",
                )
            ),
        ),
        spacing="4", width="100%",
    )


def _tab_atencion() -> rx.Component:
    af = _S.at_form
    return rx.vstack(
        rx.cond(
            AuthState.permisos_flat.contains("bitacora:crear"),
            card(
                rx.vstack(
                    rx.hstack(
                        rx.heading("Registrar atención", size="3"),
                        rx.spacer(),
                        rx.button("Limpiar", on_click=_S.nueva_atencion, size="1", variant="soft"),
                        width="100%",
                    ),
                    rx.grid(
                        rx.vstack(rx.text("Apellidos y nombres", size="1", weight="bold"),
                                  rx.input(value=af["apellidos_nombres"],
                                           on_change=lambda v: _S.set_at_campo("apellidos_nombres", v)),
                                  spacing="1"),
                        rx.vstack(rx.text("Cédula", size="1", weight="bold"),
                                  rx.input(value=af["cedula"],
                                           on_change=lambda v: _S.set_at_campo("cedula", v)),
                                  spacing="1"),
                        rx.vstack(rx.text("Motivo", size="1", weight="bold"),
                                  rx.select(_S.at_motivos, value=af["motivo"],
                                            on_change=lambda v: _S.set_at_campo("motivo", v)),
                                  spacing="1"),
                        rx.vstack(rx.text("Fecha", size="1", weight="bold"),
                                  rx.input(value=af["fecha"], type="date",
                                           on_change=lambda v: _S.set_at_campo("fecha", v)),
                                  spacing="1"),
                        rx.vstack(rx.text("Hora", size="1", weight="bold"),
                                  rx.input(value=af["hora"],
                                           on_change=lambda v: _S.set_at_campo("hora", v)),
                                  spacing="1"),
                        columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                        spacing="3", width="100%",
                    ),
                    rx.text("Observación", size="1", weight="bold"),
                    rx.text_area(value=af["observacion"],
                                 on_change=lambda v: _S.set_at_campo("observacion", v),
                                 rows="2", width="100%"),
                    rx.hstack(
                        primary_button("Guardar atención", on_click=_S.guardar_atencion),
                        rx.cond(_S.at_msg != "", rx.badge(_S.at_msg)),
                        spacing="2",
                    ),
                    spacing="2", width="100%",
                ),
                width="100%",
            ),
        ),
        card(
            rx.vstack(
                rx.hstack(
                    rx.heading("Historial de atenciones", size="3"),
                    rx.spacer(),
                    rx.input(value=_S.at_texto, on_change=_S.set_at_texto,
                             placeholder="nombre o cédula…", width="200px"),
                    rx.button("Buscar", on_click=_S.cargar_atenciones, size="1"),
                    width="100%", wrap="wrap",
                ),
                rx.cond(
                    _S.at_cargando,
                    rx.spinner(),
                    scroll_x(
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    *[
                                        rx.table.column_header_cell(
                                            c, style={"background": theme.PRIMARY, "color": "white"}
                                        )
                                        for c in ("Atendió", "Empleado", "Cédula", "Motivo",
                                                  "Fecha", "Hora", "Observación", "")
                                    ]
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    _S.atenciones,
                                    lambda a: rx.table.row(
                                        rx.table.cell(a["atendido_por"]),
                                        rx.table.cell(a["apellidos_nombres"]),
                                        rx.table.cell(a["cedula"]),
                                        rx.table.cell(a["motivo"]),
                                        rx.table.cell(a["fecha_atencion"]),
                                        rx.table.cell(a["hora"]),
                                        rx.table.cell(a["observacion"]),
                                        rx.table.cell(
                                            rx.cond(
                                                AuthState.es_admin,
                                                rx.button("Eliminar",
                                                          on_click=lambda: _S.eliminar_atencion(a["id"]),
                                                          size="1", color_scheme="red", variant="ghost"),
                                            )
                                        ),
                                    ),
                                )
                            ),
                            variant="surface", size="1", width="100%",
                        )
                    ),
                ),
                spacing="2", width="100%",
            ),
            width="100%",
        ),
        spacing="4", width="100%",
    )


def _resumen_chip(label: str, valor: rx.Var) -> rx.Component:
    return rx.vstack(
        rx.text(valor, size="5", weight="bold"),
        rx.text(label, size="1", color_scheme="gray"),
        spacing="0", align="center",
        border="1px solid var(--gray-5)", border_radius="8px", padding="10px 16px",
    )


def _tab_reportes() -> rx.Component:
    return rx.vstack(
        card(
            rx.vstack(
                rx.hstack(
                    rx.select(["(todos)", *ESTADOS], default_value="(todos)",
                              on_change=_S.set_rep_estado),
                    rx.select(_S.periodos, default_value="(todos)", on_change=_S.set_rep_periodo),
                    rx.button("Actualizar", on_click=_S.cargar_reportes),
                    rx.button("Exportar Excel", on_click=_S.exportar_excel, color_scheme="green"),
                    spacing="2", wrap="wrap",
                ),
                rx.cond(
                    _S.rep_cargando,
                    rx.spinner(),
                    rx.hstack(
                        _resumen_chip("Registros", _S.resumen["total"].to_string()),
                        _resumen_chip("Horas de suspensión",
                                      _S.resumen["horas_suspension"].to_string()),
                        _resumen_chip("Con Q.A.P.", _S.resumen["con_qap"].to_string()),
                        spacing="3", wrap="wrap",
                    ),
                ),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
        card(
            rx.vstack(
                rx.heading("Trazabilidad de acciones", size="3"),
                scroll_x(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                *[
                                    rx.table.column_header_cell(
                                        c, style={"background": theme.PRIMARY, "color": "white"}
                                    )
                                    for c in ("Fecha", "Acción", "Usuario", "Detalle")
                                ]
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                _S.historial,
                                lambda h: rx.table.row(
                                    rx.table.cell(h["fecha"]),
                                    rx.table.cell(h["accion"]),
                                    rx.table.cell(h["usuario"]),
                                    rx.table.cell(h["detalle"]),
                                ),
                            )
                        ),
                        variant="surface", size="1", width="100%",
                    )
                ),
                spacing="2", width="100%",
            ),
            width="100%",
        ),
        spacing="4", width="100%",
    )


@rx.page(
    route="/bitacora",
    title="INSEVIG — Agenda de liquidaciones",
    on_load=[AuthState.cargar_sesion, BitacoraState.cargar],
)
def index() -> rx.Component:
    return pagina(
        page_heading(
            "Agenda de cobro de liquidación de haberes",
            "Programación de cuándo los empleados salientes cobran su liquidación.",
        ),
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("Agenda", value="agenda"),
                rx.tabs.trigger("Atención personal", value="atencion"),
                rx.tabs.trigger("Reportes", value="reportes"),
            ),
            rx.tabs.content(
                rx.cond(_S.tab == "agenda", _tab_agenda(), rx.box()), value="agenda"
            ),
            rx.tabs.content(
                rx.cond(_S.tab == "atencion", _tab_atencion(), rx.box()), value="atencion"
            ),
            rx.tabs.content(
                rx.cond(_S.tab == "reportes", _tab_reportes(), rx.box()), value="reportes"
            ),
            value=_S.tab,
            on_change=_S.set_tab,
            default_value="agenda",
            width="100%",
        ),
        requiere=("bitacora", "ver"),
    )
