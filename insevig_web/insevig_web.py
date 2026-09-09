"""App INSEVIG (Reflex). Interfaz principal de integración.

Este módulo solo: crea `app`, aplica el tema e importa las páginas (que se
auto-registran). Los módulos se descubren vía `registry.MODULES`.
"""

from __future__ import annotations

import reflex as rx

from insevig_web import models  # noqa: F401  (registra tablas en SQLModel.metadata)
from insevig_web.theme import global_style


def _no_cache_html(asgi_app):
    """El servidor (granian) sirve los documentos HTML SIN `Cache-Control`,
    así que el navegador aplica 'heuristic caching' y puede quedarse pegado a
    una versión vieja tras un deploy. Este middleware ASGI fuerza
    `Cache-Control: no-cache` en las respuestas HTML (el navegador revalida
    con el `etag` en cada visita — barato) y deja los assets con hash como
    están (esos SÍ deben cachear fuerte)."""

    async def app(scope, receive, send):
        if scope["type"] != "http":
            await asgi_app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = [
                    (k, v) for (k, v) in message.get("headers", [])
                    if k.lower() != b"cache-control"
                ]
                ct = next(
                    (v.lower() for (k, v) in headers if k.lower() == b"content-type"), b""
                )
                if ct.startswith(b"text/html"):
                    headers.append((b"cache-control", b"no-cache, must-revalidate"))
                    message["headers"] = headers
            await send(message)

        await asgi_app(scope, receive, send_wrapper)

    return app


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
    api_transformer=_no_cache_html,
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
