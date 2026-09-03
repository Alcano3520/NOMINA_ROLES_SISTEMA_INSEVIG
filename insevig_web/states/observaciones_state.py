"""Estado del módulo Observaciones (Fase 2, solo lectura)."""

from __future__ import annotations

import asyncio
from dataclasses import asdict

import reflex as rx

from core.db.health import FUENTE_SQLSERVER
from core.repos import observaciones
from insevig_web.states.datasource_state import DataSourceState


class ObservacionesState(rx.State):
    texto_busqueda: str = ""
    resultados: list[dict] = []
    empleado_sel: str = ""
    nombre_sel: str = ""

    observaciones: list[dict] = []
    multas: list[dict] = []
    faltas: list[dict] = []
    faltas_hist: list[dict] = []
    cargando: bool = False

    @rx.event
    def set_texto(self, v: str):
        self.texto_busqueda = v

    async def _fuente(self) -> str:
        ds = await self.get_state(DataSourceState)
        return ds.fuente_por_modulo.get("observaciones", FUENTE_SQLSERVER)

    @rx.event
    async def buscar(self):
        if not self.texto_busqueda.strip():
            return
        fuente = await self._fuente()
        self.resultados = await asyncio.to_thread(
            observaciones.buscar_empleados, self.texto_busqueda, fuente
        )

    @rx.event
    async def seleccionar(self, empleado: str, nombre: str):
        self.empleado_sel = empleado
        self.nombre_sel = nombre
        self.cargando = True
        self.observaciones = self.multas = self.faltas = self.faltas_hist = []
        yield
        fuente = await self._fuente()

        def _cargar():
            obs = [
                {"fecha_ven": x.fecha_ven, "texto": " · ".join(x.textos)}
                for x in observaciones.observaciones(empleado, fuente)
                if x.textos
            ]
            return (
                obs,
                [asdict(x) for x in observaciones.multas(empleado, fuente)],
                [asdict(x) for x in observaciones.faltas(empleado, fuente)],
                [asdict(x) for x in observaciones.faltas(empleado, fuente, historicas=True)],
            )

        obs, mul, fal, falh = await asyncio.to_thread(_cargar)
        self.observaciones, self.multas, self.faltas, self.faltas_hist = obs, mul, fal, falh
        self.cargando = False
