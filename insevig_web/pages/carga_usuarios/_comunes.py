"""Piezas compartidas de las páginas de carga_usuarios."""

from __future__ import annotations

import reflex as rx

_TABS = [
    ("Usuario individual", "/carga-usuarios/individual"),
    ("Ver usuarios", "/carga-usuarios/listado"),
    ("Resetear contraseñas", "/carga-usuarios/reset"),
    ("Carga masiva", "/carga-usuarios/masivo"),
]


def tabs_nav(activo: str) -> rx.Component:
    return rx.flex(
        *[
            rx.link(
                rx.text(txt, size="2", weight=rx.cond(ruta == activo, "bold", "regular")),
                href=ruta,
                padding="6px 12px",
                border_bottom=rx.cond(ruta == activo, "2px solid var(--accent-9)", "2px solid transparent"),
                color=rx.cond(ruta == activo, "var(--accent-11)", "var(--gray-11)"),
            )
            for txt, ruta in _TABS
        ],
        gap="1", wrap="wrap", border_bottom="1px solid var(--gray-4)", margin_bottom="1rem",
    )


def aviso_service_key() -> rx.Component:
    return rx.callout(
        "Estas son las cuentas de los supervisores de la app de sanciones. La clave "
        "de servicio vive solo en el servidor. Las contraseñas generadas se muestran "
        "una sola vez para copiarlas — no se guardan ni se descargan.",
        icon="shield", size="1", color_scheme="gray",
    )
