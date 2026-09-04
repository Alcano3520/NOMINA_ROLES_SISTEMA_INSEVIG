"""Panel de detalle/edición de un empleado (las 5 secciones del sistema anterior
+ observaciones + borrado). Se usa embebido en /empleados y a pantalla completa
en /empleados/editar.
"""

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
    SECCIONES,
)
from insevig_web.components.ui import card, primary_button
from insevig_web.states.auth_state import AuthState
from insevig_web.states.empleados_state import EmpleadosState

_S = EmpleadosState

_SELECT_STYLE = {
    "width": "100%", "padding": "6px", "borderRadius": "6px",
    "border": "1px solid var(--gray-6)", "background": "#ffffff", "color": "#1f2937",
}


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
        control = rx.el.select(
            rx.el.option("—", value=""),
            *[rx.el.option(f"{c} — {t}", value=c) for c, t in CAMPOS_COMBO[nombre]],
            value=val,
            on_change=lambda v: _S.set_campo(nombre, v),
            disabled=_bloqueado(),
            style=_SELECT_STYLE,
        )
    elif nombre in CAMPOS_CATALOGO:
        # Catálogos (DEPTO/CARGO/SECCION/BANCO): se escribe el código y debajo se
        # muestra el NOMBRE que corresponde.
        return rx.vstack(
            rx.text(_label(nombre), size="1", weight="bold"),
            rx.input(
                value=val,
                on_change=lambda v: _S.set_campo_catalogo(nombre, v),
                disabled=_bloqueado(),
                placeholder="código",
                size="2",
                width="100%",
            ),
            rx.cond(
                _S.edit_nombres_cat[nombre] != "",
                rx.text("→ " + _S.edit_nombres_cat[nombre], size="1", color_scheme="blue", weight="medium"),
            ),
            spacing="1",
            width="100%",
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


# Etiqueta corta de pestaña por grupo (como el Notebook del sistema anterior).
_TABS = {
    "Datos generales": "Datos generales",
    "Ingresos / descuentos": "Ingresos / Dctos.",
    "Otros datos": "Otros datos",
    "Certificados / familiares": "Certificados",
    "Referencias": "Referencias",
}


_JS_CAMARA = """
(async () => {
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'}}); }
  catch (e) { alert('No se pudo abrir la cámara: ' + e.message); return ''; }
  return await new Promise((resolve) => {
    const ov = document.createElement('div');
    ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px';
    const v = document.createElement('video'); v.autoplay=true; v.playsInline=true; v.srcObject=stream;
    v.style.cssText='max-width:90vw;max-height:68vh;border-radius:8px';
    const bar = document.createElement('div'); bar.style.cssText='display:flex;gap:10px';
    const cap = document.createElement('button'); cap.textContent='Capturar';
    const can = document.createElement('button'); can.textContent='Cancelar';
    for (const b of [cap,can]) b.style.cssText='padding:8px 18px;border-radius:6px;border:0;font-weight:bold;cursor:pointer';
    cap.style.background='#1a4d8f'; cap.style.color='#fff'; can.style.background='#ddd';
    bar.append(cap, can); ov.append(v, bar); document.body.append(ov);
    const cleanup = () => { stream.getTracks().forEach(t=>t.stop()); ov.remove(); };
    cap.onclick = () => {
      const c = document.createElement('canvas');
      c.width = v.videoWidth || 640; c.height = v.videoHeight || 480;
      c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
      const url = c.toDataURL('image/jpeg', 0.85);
      cleanup(); resolve(url);
    };
    can.onclick = () => { cleanup(); resolve(''); };
  });
})()
"""


def _foto_y_documentos() -> rx.Component:
    puede_editar = AuthState.permisos_flat.contains("empleados:editar")
    foto = rx.cond(
        _S.foto_uri != "",
        rx.image(
            src=_S.foto_uri,
            width="120px",
            height="150px",
            object_fit="cover",
            border_radius="8px",
            border="1px solid var(--gray-6)",
        ),
        rx.center(
            rx.icon("user", size=48, color="var(--gray-8)"),
            width="120px",
            height="150px",
            border_radius="8px",
            border="1px dashed var(--gray-6)",
        ),
    )
    docs = [
        ("hoja_vida", "Hoja de vida"),
        ("certificado", "Certificado de trabajo"),
        ("contrato", "Contrato"),
        ("renuncia", "Carta de renuncia"),
    ]
    return card(
        rx.hstack(
            rx.vstack(
                foto,
                rx.cond(
                    puede_editar,
                    rx.vstack(
                        rx.upload(
                            rx.button("Subir foto", size="1", variant="soft", type="button"),
                            id="foto_emp",
                            accept={"image/*": [".jpg", ".jpeg", ".png", ".webp"]},
                            max_files=1,
                            on_drop=_S.subir_foto(rx.upload_files(upload_id="foto_emp")),
                            border="0",
                            padding="0",
                        ),
                        rx.button(
                            rx.icon("camera", size=14), "Tomar foto",
                            size="1", variant="soft", type="button",
                            on_click=rx.call_script(
                                _JS_CAMARA, callback=_S.guardar_foto_datauri
                            ),
                        ),
                        rx.cond(
                            _S.foto_uri != "",
                            rx.button("Quitar foto", size="1", variant="ghost", color_scheme="red",
                                      on_click=_S.quitar_foto),
                        ),
                        spacing="1",
                    ),
                ),
                rx.cond(_S.foto_msg != "", rx.text(_S.foto_msg, size="1", color_scheme="gray")),
                spacing="2",
                align="center",
            ),
            rx.vstack(
                rx.text("Documentos", weight="bold", size="2"),
                rx.text("Se generan con los datos de la ficha.", size="1", color_scheme="gray"),
                rx.grid(
                    *[
                        rx.button(
                            etq,
                            on_click=lambda tipo=tipo: _S.generar_documento(tipo),
                            variant="soft",
                            size="1",
                        )
                        for tipo, etq in docs
                    ],
                    rx.button("Imprimir ficha", on_click=_S.imprimir_ficha, variant="soft", size="1"),
                    columns="2",
                    spacing="2",
                    width="100%",
                ),
                spacing="1",
                align="start",
                width="100%",
            ),
            spacing="4",
            align="start",
            width="100%",
            wrap="wrap",
        ),
        width="100%",
    )


def _fdr_checkbox() -> rx.Component:
    return rx.hstack(
        rx.checkbox(
            checked=_S.fdr_marcado,
            on_change=lambda _v: _S.toggle_fdr(),
            disabled=_bloqueado(),
        ),
        rx.vstack(
            rx.text("Fondo de Reserva", size="1", weight="bold"),
            rx.text(
                "Marca al empleado como afiliado al IESS para que el rol calcule el fondo de reserva.",
                size="1", color_scheme="gray",
            ),
            spacing="0",
        ),
        spacing="2",
        align="center",
        width="100%",
    )


def _subseccion(titulo: str, campos: tuple[str, ...]) -> rx.Component:
    """Un recuadro con título (como los LabelFrame del sistema anterior)."""
    extra = [_fdr_checkbox()] if titulo == "Parámetros de nómina" else []
    return rx.box(
        rx.text(titulo.upper(), size="1", weight="bold", color_scheme="blue", letter_spacing="0.04em"),
        rx.divider(margin_y="6px"),
        rx.grid(
            *[_campo(c) for c in campos],
            *extra,
            columns=rx.breakpoints(initial="1", sm="2", lg="3"),
            spacing="3",
            width="100%",
        ),
        border="1px solid var(--gray-5)",
        border_radius="8px",
        padding="12px 14px",
        width="100%",
        background="var(--gray-1)",
    )


def _tab_secciones(tab: str) -> rx.Component:
    return rx.vstack(
        *[_subseccion(tit, campos) for tit, campos in SECCIONES[tab]],
        spacing="3",
        width="100%",
        padding_y="3",
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


def editor_panel() -> rx.Component:
    """El detalle del empleado seleccionado (o el alta de uno nuevo)."""
    return rx.cond(
        _S.edit_empleado != "",
        rx.cond(
            _S.cargando_editor,
            rx.center(rx.spinner(size="3"), padding="3rem", width="100%"),
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        rx.cond(_S.es_nuevo, "Nuevo empleado", _S.nombre_editor),
                        size="4",
                    ),
                    rx.spacer(),
                    rx.cond(
                        _S.es_nuevo,
                        rx.fragment(),
                        rx.cond(
                            AuthState.permisos_flat.contains("empleados:editar"),
                            rx.button(
                                rx.cond(_S.modo_edicion, "Bloquear", "Modificar"),
                                on_click=_S.toggle_modo_edicion,
                                color_scheme=rx.cond(_S.modo_edicion, "amber", "blue"),
                                size="2",
                            ),
                        ),
                    ),
                    rx.button("Cerrar", on_click=_S.cerrar_editor, variant="soft", size="2"),
                    width="100%",
                    align="center",
                ),
                rx.cond(_S.edit_audit != "", rx.text(_S.edit_audit, size="1", color_scheme="gray")),
                rx.cond(_S.edit_error != "", rx.callout(_S.edit_error, color_scheme="red", size="1")),
                rx.cond(_S.edit_ok != "", rx.callout(_S.edit_ok, color_scheme="green", size="1")),
                rx.cond(~_S.es_nuevo, _foto_y_documentos()),
                rx.cond(
                    _S.es_nuevo,
                    rx.vstack(
                        rx.text("Código de empleado", size="1", weight="bold"),
                        rx.input(
                            value=_S.edit_campos["EMPLEADO"],
                            on_change=lambda v: _S.set_campo("EMPLEADO", v),
                            width="200px",
                        ),
                        spacing="1",
                    ),
                ),
                rx.tabs.root(
                    rx.tabs.list(
                        *[
                            rx.tabs.trigger(_TABS[g], value=str(i))
                            for i, g in enumerate(SECCIONES)
                        ],
                        rx.tabs.trigger("Observaciones", value="obs"),
                        wrap="wrap",
                    ),
                    # Solo se monta el contenido de la pestaña activa (rápido).
                    *[
                        rx.tabs.content(
                            rx.cond(_S.edit_tab == str(i), _tab_secciones(tab), rx.box()),
                            value=str(i),
                        )
                        for i, tab in enumerate(SECCIONES)
                    ],
                    rx.tabs.content(
                        rx.cond(
                            _S.edit_tab == "obs",
                            rx.cond(
                                _S.es_nuevo,
                                rx.text("Disponible al guardar el empleado."),
                                _observaciones(),
                            ),
                            rx.box(),
                        ),
                        value="obs",
                    ),
                    value=_S.edit_tab,
                    on_change=_S.set_edit_tab,
                    default_value="0",
                    width="100%",
                ),
                rx.hstack(
                    rx.cond(
                        AuthState.permisos_flat.contains("empleados:editar")
                        | AuthState.permisos_flat.contains("empleados:crear"),
                        rx.alert_dialog.root(
                            rx.alert_dialog.trigger(primary_button("Guardar")),
                            rx.alert_dialog.content(
                                rx.alert_dialog.title("Confirmar"),
                                rx.alert_dialog.description(
                                    rx.cond(
                                        _S.es_nuevo,
                                        "Se creará un nuevo empleado en el sistema.",
                                        "Se modificarán los datos de " + _S.nombre_editor
                                        + ". El cambio es permanente y queda registrado.",
                                    ),
                                ),
                                rx.hstack(
                                    rx.alert_dialog.cancel(rx.button("Cancelar", variant="soft")),
                                    rx.alert_dialog.action(
                                        rx.button("Sí, guardar", on_click=_S.guardar, color_scheme="blue")
                                    ),
                                    spacing="3",
                                    justify="end",
                                    margin_top="1rem",
                                ),
                            ),
                        ),
                    ),
                    rx.cond(
                        ~_S.es_nuevo & _S.modo_edicion,
                        rx.button("Cancelar", on_click=_S.cancelar_edicion, variant="soft", color_scheme="gray"),
                    ),
                    spacing="3",
                    wrap="wrap",
                ),
                rx.cond(
                    ~_S.es_nuevo & AuthState.permisos_flat.contains("empleados:eliminar"),
                    card(
                        rx.vstack(
                            rx.heading("Eliminar empleado", size="3", color_scheme="red"),
                            rx.text(
                                "Escribe el código exacto (" + _S.edit_empleado + ") y confirma dos veces.",
                                size="1",
                            ),
                            rx.hstack(
                                rx.input(
                                    value=_S.confirmar_borrado,
                                    on_change=_S.set_confirmar_borrado,
                                    placeholder="código",
                                    width="140px",
                                ),
                                rx.alert_dialog.root(
                                    rx.alert_dialog.trigger(
                                        rx.button("Eliminar", color_scheme="red")
                                    ),
                                    rx.alert_dialog.content(
                                        rx.alert_dialog.title("¿Eliminar a " + _S.nombre_editor + "?"),
                                        rx.alert_dialog.description(
                                            "Se borrará el registro del empleado de forma permanente. "
                                            "Esta acción no se puede deshacer."
                                        ),
                                        rx.hstack(
                                            rx.alert_dialog.cancel(rx.button("No", variant="soft")),
                                            rx.alert_dialog.action(
                                                rx.button(
                                                    "Sí, eliminar definitivamente",
                                                    on_click=_S.eliminar,
                                                    color_scheme="red",
                                                )
                                            ),
                                            spacing="3",
                                            justify="end",
                                            margin_top="1rem",
                                        ),
                                    ),
                                ),
                                spacing="2",
                            ),
                            spacing="2",
                        ),
                        width="100%",
                    ),
                ),
                spacing="3",
                width="100%",
            ),
        ),
        rx.center(
            rx.text("Selecciona un empleado de la lista para ver su ficha.", color_scheme="gray"),
            padding="3rem",
            width="100%",
        ),
    )
