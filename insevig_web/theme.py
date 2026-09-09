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
    # Claro por defecto (el sistema anterior era claro); el usuario cambia a
    # oscuro con el botón del encabezado.
    color_mode="light",
    accent_color="blue",
    gray_color="slate",
    radius="large",
    scaling="100%",
    panel_background="solid",
)

# Sombras del sistema de diseño (elevación de tarjetas / paneles).
SHADOW_SM = "0 1px 2px rgba(15,23,42,.06), 0 1px 3px rgba(15,23,42,.08)"
SHADOW_MD = "0 2px 4px rgba(15,23,42,.06), 0 4px 12px rgba(15,23,42,.10)"

# El estilo global (fondo claro, modo claro forzado, superficies Radix) vive en
# `assets/theme.css`: da control fino sobre las clases .rt-* de Radix y evita el
# problema de anidado que produce `rx.App(style=...)` con claves como "body".
global_style: dict = {}
