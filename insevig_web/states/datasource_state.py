"""Selector global de fuente de datos (SQL Server / Supabase) por módulo.

Las lecturas usan la fuente elegida; las escrituras siempre van a SQL Server.
"""

from __future__ import annotations

import reflex as rx

from core.db.health import FUENTE_SQLSERVER

ETIQUETA = {"sqlserver": "SQL Server", "supabase": "Supabase"}
CLAVE = {v: k for k, v in ETIQUETA.items()}


class DataSourceState(rx.State):
    # fuente elegida por módulo; ausente => sqlserver
    fuente_por_modulo: dict[str, str] = {}

    @rx.event
    def set_fuente(self, modulo: str, etiqueta: str):
        clave = CLAVE.get(etiqueta, FUENTE_SQLSERVER)
        self.fuente_por_modulo[modulo] = clave
        # TODO Fase 1: persistir en AppConfig(scope='user')

    @rx.var
    def etiquetas_por_modulo(self) -> dict[str, str]:
        return {m: ETIQUETA.get(f, "SQL Server") for m, f in self.fuente_por_modulo.items()}
