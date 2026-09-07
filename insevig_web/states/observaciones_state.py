"""Estado del módulo Observaciones (Fase 2, solo lectura)."""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import asdict

import reflex as rx

from core.jobs.runner import JobRunner, get_runner, leer_job
from core.repos import observaciones
from insevig_web.states.auth_state import AuthState
from insevig_web.states.datasource_state import DataSourceState

_TERMINALES = {"ok", "error", "cancelado"}


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
    _obs_slots: list = []  # los 7 slots de cada fila (para el detalle)

    async def _cargar_todo(self):
        empleado = self.empleado_sel
        fuente = await self._fuente()

        def _cargar():
            filas_obs = [x for x in observaciones.observaciones(empleado, fuente) if x.textos]
            obs = [{"fecha_ven": x.fecha_ven, "texto": " · ".join(x.textos)} for x in filas_obs]
            slots = [list(x.slots7) for x in filas_obs]
            return (
                obs,
                slots,
                [asdict(x) for x in observaciones.multas(empleado, fuente)],
                [asdict(x) for x in observaciones.faltas(empleado, fuente)],
                [asdict(x) for x in observaciones.faltas(empleado, fuente, historicas=True)],
                observaciones.datos_basicos_empleado(empleado, fuente),
            )

        obs, slots, mul, fal, falh, datos = await asyncio.to_thread(_cargar)
        self.observaciones, self.multas, self.faltas, self.faltas_hist = obs, mul, fal, falh
        self._obs_slots = slots
        self.datos_emp = datos
        self.cargando = False

    # ── Detalle de una observación (los 7 slots por separado) ─────────
    detalle_abierto: bool = False
    detalle_fecha: str = ""
    detalle_slots: list[str] = []

    @rx.event
    def ver_detalle(self, idx: int):
        if 0 <= idx < len(self._obs_slots):
            self.detalle_slots = list(self._obs_slots[idx])
            self.detalle_fecha = str(self.observaciones[idx].get("fecha_ven", ""))
            self.detalle_abierto = True

    @rx.event
    def cerrar_detalle(self):
        self.detalle_abierto = False

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

    # ── "Mostrar todos": empleados con observaciones ──────────────────
    todos: list[dict] = []
    todos_cargando: bool = False
    todos_sel: list[str] = []

    @rx.event
    async def cargar_todos(self):
        self.todos_cargando = True
        yield
        fuente = await self._fuente()
        self.todos = await asyncio.to_thread(
            observaciones.empleados_con_observaciones, fuente
        )
        self.todos_cargando = False

    @rx.event
    def toggle_todo_sel(self, cod: str):
        self.todos_sel = (
            [c for c in self.todos_sel if c != cod]
            if cod in self.todos_sel
            else [*self.todos_sel, cod]
        )

    @rx.event
    async def descargar_reporte_varios(self):
        codigos = self.todos_sel or [x["empleado"] for x in self.todos]
        if not codigos:
            return
        fuente = await self._fuente()
        html = await asyncio.to_thread(
            observaciones.reporte_html_varios, fuente, codigos
        )
        return rx.download(
            data=html.encode("utf-8"), filename="observaciones_varios.html"
        )

    # ── Carga masiva de observaciones ────────────────────────────────────
    masiva_filas: list[dict] = []
    masiva_errores: list[str] = []
    masiva_job: int = 0
    masiva_status: str = ""
    masiva_msg: str = ""
    masiva_path: str = ""

    @rx.event
    async def subir_masiva(self, files: list[rx.UploadFile]):
        from core.excel.parsers import parse_carga_masiva_observaciones

        if not files:
            return
        datos = await files[0].read()
        filas, errores = parse_carga_masiva_observaciones(datos)
        self.masiva_filas = filas[:1000]
        self.masiva_errores = errores[:50]
        self.masiva_msg = ""

    @rx.event
    async def aplicar_masiva(self):
        auth = await self.get_state(AuthState)
        if "observaciones:crear" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso para crear observaciones.")
        if not self.masiva_filas:
            return rx.toast.error("Primero sube y previsualiza un archivo.")
        filas = [dict(f) for f in self.masiva_filas]
        usuario, roles = auth.username, set(auth.roles)

        def _fn(ctx):
            observaciones.job_carga_masiva_observaciones(ctx, filas, usuario=usuario, roles=roles)

        self.masiva_path = ""
        self.masiva_job = get_runner().encolar(
            "carga_masiva_observaciones", {"n": len(filas)}, creado_por=usuario, fn=_fn
        )
        self.masiva_status = "pendiente"
        return ObservacionesState.vigilar_masiva

    @rx.event(background=True)
    async def vigilar_masiva(self):
        for _ in range(3600):
            async with self:
                jid = self.masiva_job
            j = leer_job(jid)
            if j is None:
                return
            async with self:
                self.masiva_status = j.status
                self.masiva_msg = j.message
                self.masiva_path = j.result_path
            if j.status in _TERMINALES:
                return
            await asyncio.sleep(1)

    @rx.event
    def cancelar_masiva(self):
        if self.masiva_job:
            JobRunner.cancelar(self.masiva_job)

    @rx.event
    def descargar_masiva(self):
        from pathlib import Path

        if not self.masiva_path:
            return
        p = Path(self.masiva_path)
        return rx.download(data=p.read_bytes(), filename=p.name)

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
