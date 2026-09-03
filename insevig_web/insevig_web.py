"""App INSEVIG (Reflex). Interfaz principal de integración.

Este módulo solo: crea `app`, aplica el tema e importa las páginas (que se
auto-registran). Los módulos se descubren vía `registry.MODULES`.
"""

from __future__ import annotations

import reflex as rx

from insevig_web import models  # noqa: F401  (registra tablas en SQLModel.metadata)
from insevig_web.theme import global_style

app = rx.App(style=global_style, stylesheets=["/theme.css"])

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
