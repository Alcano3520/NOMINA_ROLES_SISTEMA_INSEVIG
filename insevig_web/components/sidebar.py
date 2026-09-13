"""Menú lateral. Se arma desde `registry.MODULES`, filtrado por permisos y
agrupado en secciones lógicas, con estado activo según la ruta actual.

★ CONGELADO: para añadir una entrada, registra un `ModuleSpec`, no edites esto.
"""

from __future__ import annotations

import reflex as rx

from insevig_web import theme
from insevig_web.registry import MODULES, ModuleSpec, NavItem
from insevig_web.state import AppState
from insevig_web.states.auth_state import AuthState

# ── Constantes de estilo del sidebar ────────────────────────────────────────
_BG = theme.SIDEBAR
_FG = "rgba(255,255,255,.78)"          # texto normal
_FG_ACTIVE = "#ffffff"                 # texto activo
_HOVER_BG = "rgba(255,255,255,.08)"
_ACTIVE_BG = "rgba(74,158,255,.20)"    # acento azul suave
_ACTIVE_BAR = theme.SECONDARY          # barrita amarilla corporativa

# Agrupación de módulos en secciones (por id de módulo).
_SECCIONES: list[tuple[str, tuple[str, ...]]] = [
    ("Personal", ("empleados", "observaciones", "vacaciones", "prestamos")),
    ("Nómina", ("roles", "reportes", "registrador")),
    ("Liquidaciones", ("liquidaciones", "bitacora")),
    ("Sanciones · Maniobras · Faltas", ("sanciones", "maniobras", "faltas")),
    ("Sistema", ("admin", "carga_usuarios")),
]
_TITULOS_SECCIONES = [t for t, _ in _SECCIONES]


def _toggle_todo() -> rx.Component:
    """Colapsa/expande TODAS las secciones de un golpe -- pedido del
    usuario junto con el colapso por sección de arriba."""
    todo_colapsado = AppState.secciones_colapsadas.length() >= len(_TITULOS_SECCIONES)
    return rx.hstack(
        rx.icon(
            rx.cond(todo_colapsado, "chevrons-down-up", "chevrons-up-down"),
            size=13, color="rgba(255,255,255,.55)", flex_shrink="0",
        ),
        rx.text(
            rx.cond(todo_colapsado, "Expandir todo", "Colapsar todo"),
            size="1", weight="bold", color="rgba(255,255,255,.55)",
        ),
        spacing="2", align="center", width="100%",
        padding="0.4rem 0.85rem",
        cursor="pointer",
        on_click=lambda: AppState.alternar_todas_las_secciones(_TITULOS_SECCIONES),
    )


def _seccion_label(texto: str) -> rx.Component:
    """Título de sección, cliqueable para colapsar/expandir SOLO esa
    sección (persistido en `localStorage`, sobrevive a un F5) -- con un
    chevron que refleja el estado, igual que "Colapsar todo" de abajo."""
    colapsada = AppState.secciones_colapsadas.contains(texto)
    return rx.hstack(
        rx.icon(
            rx.cond(colapsada, "chevron-right", "chevron-down"),
            size=11, color="rgba(255,255,255,.38)", flex_shrink="0",
        ),
        rx.text(
            texto.upper(), size="1", weight="bold", letter_spacing="0.08em",
            color="rgba(255,255,255,.38)",
        ),
        spacing="1", align="center", width="100%",
        padding="0.9rem 0.85rem 0.35rem",
        cursor="pointer",
        on_click=lambda: AppState.toggle_seccion(texto),
    )


def _entrada(icono: str, etiqueta: str, ruta: str, permiso: str,
            *, indentado: bool = False, disponible: bool = True) -> rx.Component:
    """Una fila cliqueable del sidebar (un `NavItem` puntual, no todo el módulo
    -- BUG REAL corregido 2026-09-12: antes se renderizaba solo UNA fila por
    módulo, usando `spec.ruta_principal` (el primer `NavItem`); el resto de
    las páginas de un módulo con 2+ items (ej. `sanciones` con 5, `faltas`
    con 4, `empleados` con 4, `liquidaciones` con 4) quedaban solo
    alcanzables tecleando la URL a mano -- invisibles en la navegación real."""
    activo = AppState.router.page.path == ruta
    fila = rx.hstack(
        rx.box(
            width="3px", height="18px", border_radius="9999px",
            background=rx.cond(activo, _ACTIVE_BAR, "transparent"), flex_shrink="0",
        ),
        rx.icon(
            icono, size=16 if indentado else 18,
            color=rx.cond(activo, _FG_ACTIVE, "rgba(255,255,255,.6)"),
        ),
        rx.text(
            etiqueta, size="2",
            weight=rx.cond(activo, "bold", "regular"),
            color=rx.cond(activo, _FG_ACTIVE, _FG),
        ),
        *([] if disponible else [rx.badge("pronto", color_scheme="gray", size="1")]),
        spacing="2",
        align="center",
        width="100%",
        padding=("0.45rem 0.7rem 0.45rem 0.9rem" if indentado else "0.55rem 0.7rem 0.55rem 0.35rem"),
        border_radius="8px",
        background=rx.cond(activo, _ACTIVE_BG, "transparent"),
        _hover={"background": rx.cond(activo, _ACTIVE_BG, _HOVER_BG)},
        transition="background 120ms ease",
        cursor="pointer",
    )
    enlace = rx.link(
        fila,
        href=ruta,
        width="100%",
        _hover={"text_decoration": "none"},
        on_click=AppState.cerrar_sidebar,
    )
    return rx.cond(AuthState.permisos_flat.contains(permiso), enlace)


def _modulo(spec: ModuleSpec) -> rx.Component:
    """Un módulo entero: una fila si tiene un solo `NavItem` (como antes),
    o el título del módulo + una fila indentada por cada `NavItem` si tiene
    varios -- así todas sus páginas quedan alcanzables, no solo la primera."""
    if len(spec.items) <= 1:
        item = spec.items[0] if spec.items else NavItem(spec.titulo, spec.ruta_principal)
        return _entrada(
            spec.icono, spec.titulo, item.ruta, f"{spec.nombre}:{item.permiso}",
            disponible=spec.disponible,
        )
    return rx.vstack(
        rx.text(
            spec.titulo, size="1", weight="bold", letter_spacing="0.02em",
            color="rgba(255,255,255,.5)", padding="0.5rem 0.7rem 0.1rem 0.35rem",
        ),
        *[
            _entrada(
                spec.icono, item.label, item.ruta, f"{spec.nombre}:{item.permiso}",
                indentado=True, disponible=spec.disponible,
            )
            for item in spec.items
        ],
        spacing="0", width="100%", align_items="start",
    )


def _grupo(titulo: str, ids: tuple[str, ...]) -> rx.Component:
    por_id = {m.nombre: m for m in MODULES}
    specs = [por_id[i] for i in ids if i in por_id]
    if not specs:
        return rx.fragment()
    return rx.vstack(
        _seccion_label(titulo),
        rx.cond(
            AppState.secciones_colapsadas.contains(titulo),
            rx.fragment(),
            rx.vstack(*[_modulo(s) for s in specs], spacing="1", width="100%", align_items="start"),
        ),
        spacing="1", width="100%", align_items="start",
    )


def sidebar_contenido() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading("INSEVIG", size="5", color=theme.SECONDARY, weight="bold"),
            rx.text("RRHH", size="1", color="rgba(255,255,255,.7)", weight="bold",
                    letter_spacing="0.1em"),
            spacing="2",
            align="baseline",
            padding="1.1rem 0.85rem 0.6rem",
        ),
        _toggle_todo(),
        rx.box(height="1px", background="rgba(255,255,255,.08)", width="100%",
               margin="0.3rem 0 0.15rem"),
        rx.box(
            *[_grupo(t, ids) for t, ids in _SECCIONES],
            width="100%", overflow_y="auto", flex_grow="1",
        ),
        rx.box(height="1px", background="rgba(255,255,255,.1)", width="100%",
               margin="0.6rem 0"),
        rx.link(
            rx.hstack(rx.icon("user", size=16), rx.text("Mi cuenta", size="2"),
                      spacing="2", align="center"),
            href="/mi-cuenta",
            color=_FG,
            width="100%",
            padding="0.5rem 0.7rem",
            border_radius="8px",
            _hover={"background": _HOVER_BG, "text_decoration": "none"},
        ),
        rx.button(
            rx.hstack(rx.icon("log-out", size=16), rx.text("Salir"), spacing="2",
                      align="center"),
            on_click=AuthState.logout,
            variant="soft",
            color_scheme="red",
            width="100%",
            cursor="pointer",
        ),
        spacing="1",
        height="100%",
        width="100%",
        padding="0.5rem 0.6rem 0.8rem",
        background=_BG,
        align_items="start",
    )


def sidebar_fijo() -> rx.Component:
    """Visible en escritorio (>= lg)."""
    return rx.box(
        sidebar_contenido(),
        display=rx.breakpoints(initial="none", lg="block"),
        width="256px",
        min_width="256px",
        height="100vh",
        position="sticky",
        top="0",
        box_shadow="1px 0 0 rgba(0,0,0,.15)",
    )


def sidebar_drawer() -> rx.Component:
    """Drawer para móvil/tablet (< lg)."""
    return rx.drawer.root(
        rx.drawer.overlay(),
        rx.drawer.portal(
            rx.drawer.content(
                sidebar_contenido(),
                width="256px",
                height="100%",
                background=_BG,
            )
        ),
        open=AppState.sidebar_abierto,
        on_open_change=AppState.set_sidebar,
        direction="left",
    )
