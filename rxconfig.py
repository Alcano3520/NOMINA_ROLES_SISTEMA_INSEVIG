import reflex as rx

from core.config import get_settings
from insevig_web.theme import theme

_s = get_settings()

config = rx.Config(
    app_name="insevig_web",
    app_module_import="insevig_web.insevig_web",
    db_url=_s.app_db_url,
    show_built_with_reflex=False,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(theme=theme),
    ],
)
