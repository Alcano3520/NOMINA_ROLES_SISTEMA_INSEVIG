"""Selector global de fuente de datos (SQL Server / Supabase) por módulo.

Las lecturas usan la fuente elegida; las escrituras siempre van a SQL Server.
Si el usuario no ha elegido, se usa la fuente autodetectada (`fuente_por_defecto`):
SQL Server si responde, si no Supabase — así los módulos de solo lectura funcionan
aunque el servidor SQL no esté en red (desarrollo fuera de la LAN).
"""

from __future__ import annotations

import asyncio

import reflex as rx

from core.db.health import FUENTE_SQLSERVER, fuente_por_defecto

ETIQUETA = {"sqlserver": "SQL Server", "supabase": "Supabase"}
CLAVE = {v: k for k, v in ETIQUETA.items()}


class DataSourceState(rx.State):
    # fuente elegida explícitamente por módulo; si falta, se usa `_auto`
    fuente_por_modulo: dict[str, str] = {}
    _auto: str = ""

    async def resolver(self, modulo: str) -> str:
        """Fuente efectiva para un módulo: la elegida, o la autodetectada."""
        if modulo in self.fuente_por_modulo:
            return self.fuente_por_modulo[modulo]
        if not self._auto:
            self._auto = await asyncio.to_thread(fuente_por_defecto)
        return self._auto

    @rx.event
    def set_fuente(self, modulo: str, etiqueta: str):
        clave = CLAVE.get(etiqueta, FUENTE_SQLSERVER)
        self.fuente_por_modulo[modulo] = clave
        # TODO Fase 1: persistir en AppConfig(scope='user')

    @rx.var
    def etiquetas_por_modulo(self) -> dict[str, str]:
        return {m: ETIQUETA.get(f, "SQL Server") for m, f in self.fuente_por_modulo.items()}
