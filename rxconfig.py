import reflex as rx

from core.config import get_settings
from insevig_web.theme import theme

_s = get_settings()

config = rx.Config(
    app_name="insevig_web",
    app_module_import="insevig_web.insevig_web",
    db_url=_s.app_db_url,
    show_built_with_reflex=False,
    # Claro por defecto para quien entra sin preferencia guardada (el
    # sistema anterior era claro); el botón del encabezado puede cambiarlo
    # a oscuro libremente y queda persistido (ver `insevig_web/theme.py`,
    # `color_mode="inherit"` -- antes "light" fijo rompía el toggle).
    default_color_mode="light",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(theme=theme),
    ],
)
