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

    # ── Secciones del sidebar colapsadas por sección + un maestro arriba ──
    # `rx.LocalStorage`, no `rx.State` normal: sobrevive a un F5/cierre de
    # pestaña (persiste en el navegador, no en la sesión del server) --
    # guardado como texto separado por "|" (mismo criterio de tipo simple
    # que ya usa `AuthState.sesion` vía `rx.Cookie`, en vez de un
    # `list[str]` directo cuya serialización con LocalStorage no está
    # probada en este proyecto).
    secciones_colapsadas_csv: str = rx.LocalStorage("", name="sidebar_colapsado")

    @rx.var
    def secciones_colapsadas(self) -> list[str]:
        return [t for t in self.secciones_colapsadas_csv.split("|") if t]

    @rx.event
    def toggle_seccion(self, titulo: str):
        actuales = self.secciones_colapsadas
        nuevas = (
            [t for t in actuales if t != titulo] if titulo in actuales else [*actuales, titulo]
        )
        self.secciones_colapsadas_csv = "|".join(nuevas)

    @rx.event
    def alternar_todas_las_secciones(self, titulos: list[str]):
        """El botón maestro de arriba: si ya están todas colapsadas,
        expande todas; si no, colapsa todas."""
        if len(self.secciones_colapsadas) >= len(titulos):
            self.secciones_colapsadas_csv = ""
        else:
            self.secciones_colapsadas_csv = "|".join(titulos)

    # ── Buscador del sidebar (debajo de "Colapsar todo") ──────────────────
    # Pedido: "para cuando alguien no quiera navegar, solo ponga 'egreso' y
    # salga lo relacionado" -- filtra módulos/páginas por texto, sin pegarle
    # al server (el filtrado es puramente client-side, ver `sidebar.py`).
    sidebar_busqueda: str = ""

    @rx.event
    def set_sidebar_busqueda(self, v: str):
        self.sidebar_busqueda = v
