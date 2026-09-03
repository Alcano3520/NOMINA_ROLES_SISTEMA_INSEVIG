from __future__ import annotations

import reflex as rx

from core.repos.empleados import (
    CAMPOS_CATALOGO,
    CAMPOS_COMBO,
    CAMPOS_FLAG_INT,
    CAMPOS_FLAG_TXT,
    CAMPOS_NUMERICOS,
    CAMPOS_SN,
    ETIQUETAS,
    GRUPOS,
)
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.empleados_state import EmpleadosState

_S = EmpleadosState


def _bloqueado() -> rx.Var:
    return ~_S.es_nuevo & ~_S.modo_edicion


def _label(nombre: str) -> str:
    return ETIQUETAS.get(nombre, nombre.replace("_", " ").capitalize())


def _campo(nombre: str) -> rx.Component:
    val = _S.edit_campos[nombre]
    if nombre in CAMPOS_FLAG_TXT or nombre in CAMPOS_FLAG_INT or nombre in CAMPOS_SN:
        marcado = (val == "1") | (val == "S") | (val == "true")
        return rx.hstack(
            rx.checkbox(
                checked=marcado,
                on_change=lambda _v: _S.toggle_campo(nombre),
                disabled=_bloqueado(),
            ),
            rx.text(_label(nombre), size="1"),
            spacing="2",
            align="center",
            width="100%",
        )
    if nombre in CAMPOS_COMBO:
        opts = CAMPOS_COMBO[nombre]
        control = rx.el.select(
            rx.el.option("—", value=""),
            *[rx.el.option(f"{c} — {t}", value=c) for c, t in opts],
            value=val,
            on_change=lambda v: _S.set_campo(nombre, v),
            disabled=_bloqueado(),
            style={"width": "100%", "padding": "6px", "borderRadius": "6px",
                   "border": "1px solid var(--gray-6)", "background": "var(--color-panel-solid)"},
        )
    elif nombre in CAMPOS_CATALOGO:
        tipo = CAMPOS_CATALOGO[nombre]
        control = rx.el.select(
            rx.el.option("—", value=""),
            rx.foreach(
                _S.edit_catalogos[tipo],
                lambda o: rx.el.option(f"{o['codigo']} — {o['nombre']}", value=o["codigo"]),
            ),
            value=val,
            on_change=lambda v: _S.set_campo(nombre, v),
            disabled=_bloqueado(),
            style={"width": "100%", "padding": "6px", "borderRadius": "6px",
                   "border": "1px solid var(--gray-6)", "background": "var(--color-panel-solid)"},
        )
    else:
        control = rx.input(
            value=val,
            on_change=lambda v: _S.set_campo(nombre, v),
            size="2",
            width="100%",
            type=rx.cond(nombre in CAMPOS_NUMERICOS, "number", "text"),
            disabled=_bloqueado(),
        )
    return rx.vstack(
        rx.text(_label(nombre), size="1", weight="bold"),
        control,
        spacing="1",
        width="100%",
    )


def _grupo(titulo: str, campos: tuple[str, ...]) -> rx.Component:
    return rx.accordion.item(
        header=titulo,
        content=rx.grid(
            *[_campo(c) for c in campos],
            columns=rx.breakpoints(initial="1", sm="2", lg="3"),
            spacing="3",
            width="100%",
            padding_y="3",
        ),
        value=titulo,
    )


def _observaciones() -> rx.Component:
    slots = [
        rx.vstack(
            rx.text(f"Campo {i + 1}", size="1", weight="bold"),
            rx.text_area(
                value=_S.edit_obs_slots[i],
                on_change=lambda v, i=i: _S.set_obs_slot(i, v),
                rows="2",
                width="100%",
            ),
            spacing="1",
            width="100%",
        )
        for i in range(7)
    ]
    return card(
        rx.vstack(
            rx.heading("Observaciones por período", size="3"),
            rx.hstack(
                rx.input(
                    value=_S.edit_obs_periodo,
                    on_change=_S.set_obs_periodo,
                    placeholder="AAAA-MM",
                    width="120px",
                ),
                rx.button("Mostrar", on_click=_S.cargar_obs_editor, variant="soft"),
                rx.cond(
                    AuthState.permisos_flat.contains("empleados:editar"),
                    primary_button("Guardar obs.", on_click=_S.guardar_obs_editor),
                ),
                rx.button("Ver historial completo", on_click=_S.cargar_historial_obs, variant="ghost"),
                spacing="2",
                wrap="wrap",
            ),
            rx.cond(_S.edit_obs_msg != "", rx.callout(_S.edit_obs_msg, size="1")),
            rx.grid(*slots, columns=rx.breakpoints(initial="1", sm="2"), spacing="3", width="100%"),
            rx.cond(
                _S.obs_historial.length() > 0,
                rx.vstack(
                    rx.heading("Historial", size="2"),
                    rx.foreach(
                        _S.obs_historial,
                        lambda h: rx.box(
                            rx.text(h["fecha_ven"], weight="bold", size="1"),
                            rx.text(h["texto"], size="1"),
                            padding="6px",
                            border_bottom="1px solid var(--gray-4)",
                        ),
                    ),
                    spacing="2",
                    width="100%",
                ),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


@rx.page(route="/empleados/editar", title="INSEVIG — Editar empleado", on_load=AuthState.cargar_sesion)
def editar() -> rx.Component:
    return pagina(
        page_heading(
            rx.cond(_S.es_nuevo, "Nuevo empleado", "Editar empleado " + _S.edit_empleado),
            "Escrituras a SQL Server (RPEMPLEA / RPEMPOBSERV) con auditoría.",
        ),
        rx.vstack(
            rx.cond(_S.edit_error != "", rx.callout(_S.edit_error, color_scheme="red", size="1")),
            rx.cond(_S.edit_ok != "", rx.callout(_S.edit_ok, color_scheme="green", size="1")),
            rx.cond(_S.edit_audit != "", rx.text(_S.edit_audit, size="1", color_scheme="gray")),
            rx.hstack(
                rx.cond(
                    _S.es_nuevo,
                    rx.vstack(
                        rx.text("Código de empleado (EMPLEADO)", size="1", weight="bold"),
                        rx.input(
                            value=_S.edit_campos["EMPLEADO"],
                            on_change=lambda v: _S.set_campo("EMPLEADO", v),
                            width="200px",
                        ),
                        spacing="1",
                    ),
                    rx.cond(
                        AuthState.permisos_flat.contains("empleados:editar"),
                        rx.button(
                            rx.cond(_S.modo_edicion, "Bloquear edición", "Modificar"),
                            on_click=_S.toggle_modo_edicion,
                            color_scheme=rx.cond(_S.modo_edicion, "amber", "blue"),
                        ),
                    ),
                ),
                width="100%",
            ),
            rx.accordion.root(
                *[_grupo(g, cs) for g, cs in GRUPOS.items()],
                type="multiple",
                default_value=[next(iter(GRUPOS))],
                collapsible=True,
                width="100%",
            ),
            rx.hstack(
                primary_button("Guardar", on_click=_S.guardar),
                rx.link(rx.button("Volver", variant="soft"), href="/empleados/buscar"),
                spacing="3",
            ),
            rx.cond(~_S.es_nuevo, _observaciones()),
            rx.cond(
                ~_S.es_nuevo & AuthState.permisos_flat.contains("empleados:eliminar"),
                card(
                    rx.vstack(
                        rx.heading("Eliminar empleado", size="3", color_scheme="red"),
                        rx.text(
                            "Escribe el código exacto (" + _S.edit_empleado + ") para confirmar.",
                            size="1",
                        ),
                        rx.hstack(
                            rx.input(
                                value=_S.confirmar_borrado,
                                on_change=_S.set_confirmar_borrado,
                                width="160px",
                            ),
                            rx.button("Eliminar", on_click=_S.eliminar, color_scheme="red"),
                            spacing="2",
                        ),
                        spacing="2",
                    ),
                    width="100%",
                ),
            ),
            spacing="4",
            width="100%",
        ),
        requiere=("empleados", "ver"),
    )
