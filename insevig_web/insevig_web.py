"""App INSEVIG (Reflex). Interfaz principal de integración.

Este módulo solo: crea `app`, aplica el tema e importa las páginas (que se
auto-registran). Los módulos se descubren vía `registry.MODULES`.
"""

from __future__ import annotations

import reflex as rx

from insevig_web import models  # noqa: F401  (registra tablas en SQLModel.metadata)
from insevig_web.theme import global_style

# `darkreader-lock`: la app tiene su propio modo claro/oscuro (botón sol/luna).
# Esta meta le dice a la extensión Dark Reader que NO reprocese la página — si
# no, aplasta las superficies y los acentos del diseño con su gris plano.
app = rx.App(
    style=global_style,
    stylesheets=["/theme.css"],
    head_components=[
        rx.el.meta(name="darkreader-lock"),
        rx.el.meta(name="color-scheme", content="light dark"),
    ],
)

# Dev (SQLite): crea las tablas que falten. En prod (Postgres) manda alembic.
try:
    from core.config import get_settings
    from core.db import appdb

    if get_settings().app_db_url.startswith("sqlite"):
        appdb.crear_tablas()
except Exception as e:  # noqa: BLE001
    import logging

    logging.getLogger(__name__).warning("No se pudieron crear tablas de la app: %s", e)

# Importar después de crear `app`: las páginas usan `@rx.page` para registrarse.
from insevig_web import pages  # noqa: E402, F401
