"""Estado base compartido. ★ NO IMPORTA NADA del proyecto (ni core, ni states,
ni pages, ni components). Solo primitivas. Evita ciclos de import.

Los states de feature viven en `insevig_web/states/<mod>_state.py` y se
comunican con `get_state()` / `yield OtherState.metodo`.
"""

from __future__ import annotations

import reflex as rx


class AppState(rx.State):
    """Primitivas de UI transversales."""

    cargando: bool = False
    sidebar_abierto: bool = False  # drawer en móvil

    @rx.event
    def toggle_sidebar(self):
        self.sidebar_abierto = not self.sidebar_abierto

    @rx.event
    def cerrar_sidebar(self):
        self.sidebar_abierto = False

    @rx.event
    def set_sidebar(self, abierto: bool):
        self.sidebar_abierto = abierto
