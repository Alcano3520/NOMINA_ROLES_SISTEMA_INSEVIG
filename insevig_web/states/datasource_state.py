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


_MODULOS = (
    "reportes", "prestamos", "observaciones", "empleados", "roles", "registrador",
    "bitacora", "liquidaciones",
)


class DataSourceState(rx.State):
    # fuente elegida explícitamente por módulo; si falta, se usa `auto`
    fuente_por_modulo: dict[str, str] = {}
    auto: str = ""  # fuente autodetectada (sqlserver si responde, si no supabase)

    @rx.event(background=True)
    async def detectar(self):
        async with self:
            if self.auto:
                return
        fuente = await asyncio.to_thread(fuente_por_defecto)
        async with self:
            self.auto = fuente

    async def resolver(self, modulo: str) -> str:
        """Fuente efectiva para un módulo: la elegida, o la autodetectada."""
        if modulo in self.fuente_por_modulo:
            return self.fuente_por_modulo[modulo]
        if not self.auto:
            self.auto = await asyncio.to_thread(fuente_por_defecto)
        return self.auto

    @rx.event
    def set_fuente(self, modulo: str, etiqueta: str):
        clave = CLAVE.get(etiqueta, FUENTE_SQLSERVER)
        self.fuente_por_modulo[modulo] = clave
        # TODO Fase 1: persistir en AppConfig(scope='user')

    @rx.var
    def etiquetas_efectivas(self) -> dict[str, str]:
        """Etiqueta a mostrar por módulo: la elección explícita, o la autodetectada."""
        base = ETIQUETA.get(self.auto, "SQL Server")
        return {
            m: ETIQUETA.get(self.fuente_por_modulo.get(m, ""), base) for m in _MODULOS
        }
