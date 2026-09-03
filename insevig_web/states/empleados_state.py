"""Estado del módulo Gestión de Empleados.

Fase 2: historial de nómina (solo lectura). Fase 3 añade CRUD y carga masiva.
"""

from __future__ import annotations

import asyncio
import datetime as dt

import reflex as rx

from core.datos.service import datos_empleado
from core.db.health import FUENTE_SQLSERVER
from core.repos import observaciones
from insevig_web.states.datasource_state import DataSourceState


def _periodo_actual() -> str:
    return dt.date.today().strftime("%Y-%m")


class EmpleadosState(rx.State):
    texto_busqueda: str = ""
    resultados: list[dict] = []
    empleado_sel: str = ""
    nombre_sel: str = ""

    periodo: str = ""
    fila: dict = {}
    conceptos: list[dict] = []  # [{'concepto','valor'}]
    cargando: bool = False
    sin_datos: bool = False

    @rx.event
    def on_load(self):
        if not self.periodo:
            self.periodo = _periodo_actual()

    @rx.event
    def set_texto(self, v: str):
        self.texto_busqueda = v

    @rx.event
    def set_periodo(self, v: str):
        self.periodo = v.strip()

    async def _fuente(self) -> str:
        ds = await self.get_state(DataSourceState)
        return ds.fuente_por_modulo.get("empleados", FUENTE_SQLSERVER)

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
        yield
        await self._cargar_periodo()

    @rx.event
    async def recargar(self):
        if self.empleado_sel:
            await self._cargar_periodo()

    async def _cargar_periodo(self):
        self.cargando = True
        self.sin_datos = False
        self.conceptos = []
        self.fila = {}
        yield
        fuente = await self._fuente()
        emp = await asyncio.to_thread(
            datos_empleado, self.periodo or _periodo_actual(), self.empleado_sel, fuente
        )
        self.cargando = False
        if emp is None:
            self.sin_datos = True
            return
        self.fila = {
            "cargo": emp.cargo,
            "depto": emp.depto,
            "dias": emp.dias,
            "ingresos": emp.total_ingresos,
            "egresos": emp.total_egresos,
            "recibir": emp.total_recibir,
        }
        self.conceptos = [
            {"concepto": k, "valor": round(v, 2)} for k, v in sorted(emp.conceptos.items())
        ]
