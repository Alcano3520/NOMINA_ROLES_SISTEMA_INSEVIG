"""Páginas placeholder para cada ruta de módulo registrada.

Cada módulo real reemplazará su(s) página(s) con las de `pages/<mod>/`. Mientras
tanto, estas dejan el enrutado y la navegación completos y verificables.
"""

from __future__ import annotations

import reflex as rx

from insevig_web.components.layout import pagina
from insevig_web.components.ui import page_heading, placeholder
from insevig_web.registry import MODULES
from insevig_web.states.auth_state import AuthState


def _hacer_pagina(titulo_item: str, modulo: str, accion: str, titulo_mod: str):
    def _p() -> rx.Component:
        return pagina(
            page_heading(titulo_mod, titulo_item),
            placeholder(titulo_item, "en migración"),
            requiere=(modulo, accion),
        )

    return _p


# Módulos con páginas reales (no generar placeholder para sus rutas).
_YA_MIGRADOS = {"reportes"}

for _spec in MODULES:
    if _spec.nombre in _YA_MIGRADOS:
        continue
    for _item in _spec.items:
        _fn = _hacer_pagina(_item.label, _spec.nombre, _item.permiso, _spec.titulo)
        _fn.__name__ = "pg_" + _item.ruta.strip("/").replace("/", "_").replace("-", "_")
        rx.page(
            route=_item.ruta,
            title=f"INSEVIG — {_item.label}",
            on_load=AuthState.cargar_sesion,
        )(_fn)
