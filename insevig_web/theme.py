"""Paleta corporativa y tema. Único lugar donde se definen colores base.

Los módulos NO definen estilos propios: usan `components/ui/*`, que consumen esto.
"""

from __future__ import annotations

import reflex as rx

# Paleta INSEVIG (heredada de Sistema_INSEVIG.pyw)
SIDEBAR = "#0d1b2a"
PRIMARY = "#1a4d8f"
SECONDARY = "#ffd700"
HOVER = "#2a5caa"
OK = "#2ed573"
DANGER = "#ff6b6b"
BG = "#f5f7fa"

# Breakpoint por debajo del cual el sidebar colapsa a drawer.
SIDEBAR_BREAKPOINT = "1024px"

theme = rx.theme(
    color_mode="light",  # fuerza modo claro
    accent_color="blue",
    gray_color="slate",
    radius="medium",
    scaling="100%",
    # reflex-components-radix elimina el prop `appearance` al renderizar; forzamos
    # la escala clara de Radix con el data-attribute directamente.
    custom_attrs={"data-appearance": "light"},
)

# Estilo global mínimo: fondo claro y sin scroll horizontal del body.
global_style = {
    "body": {"background_color": BG, "color": "#1f2937"},
    ":root": {"color_scheme": "light"},
}
