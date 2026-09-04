"""Estado del módulo Observaciones (Fase 2, solo lectura)."""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import asdict

import reflex as rx

from core.repos import observaciones
from insevig_web.states.auth_state import AuthState
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
        return await ds.resolver("observaciones")

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
        await self._cargar_todo()

    datos_emp: dict = {}

    async def _cargar_todo(self):
        empleado = self.empleado_sel
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
                observaciones.datos_basicos_empleado(empleado, fuente),
            )

        obs, mul, fal, falh, datos = await asyncio.to_thread(_cargar)
        self.observaciones, self.multas, self.faltas, self.faltas_hist = obs, mul, fal, falh
        self.datos_emp = datos
        self.cargando = False

    # ── Nueva observación (primer slot libre) ─────────────────────────────
    nueva_periodo: str = ""
    nueva_texto: str = ""
    nueva_msg: str = ""

    @rx.event
    def set_nueva_periodo(self, v: str):
        self.nueva_periodo = v.strip()

    @rx.event
    def set_nueva_texto(self, v: str):
        self.nueva_texto = v

    @rx.event
    async def guardar_nueva(self):
        auth = await self.get_state(AuthState)
        if "observaciones:crear" not in auth.permisos_flat:
            self.nueva_msg = "Sin permiso."
            return
        if not self.empleado_sel or not self.nueva_texto.strip():
            self.nueva_msg = "Selecciona empleado y escribe el texto."
            return
        per = self.nueva_periodo or dt.date.today().strftime("%Y-%m")
        try:
            slot = await asyncio.to_thread(
                observaciones.guardar_observacion, self.empleado_sel, per, self.nueva_texto,
                usuario=auth.username, roles=set(auth.roles),
            )
            self.nueva_msg = f"Guardado ({slot})." if slot != "duplicado" else "Ya existía esa observación."
            self.nueva_texto = ""
        except Exception as e:  # noqa: BLE001
            self.nueva_msg = str(e)
        await self._cargar_todo()

    @rx.event
    def descargar_reporte(self):
        if not self.empleado_sel:
            return
        html = observaciones.reporte_html(
            self.empleado_sel, self.nombre_sel,
            list(self.observaciones), list(self.multas), list(self.faltas),
        )
        return rx.download(
            data=html.encode("utf-8"),
            filename=f"observaciones_{self.empleado_sel}.html",
        )
