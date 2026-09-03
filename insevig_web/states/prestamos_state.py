"""Estado del módulo Préstamos (Fase 2). Solo lectura."""

from __future__ import annotations

import asyncio
from dataclasses import asdict

import reflex as rx

from core.db.health import FUENTE_SQLSERVER
from core.jobs.runner import JobRunner, get_runner, leer_job
from core.repos import prestamos
from insevig_web.states.datasource_state import DataSourceState

_TERMINALES = {"ok", "error", "cancelado"}


class PrestamosState(rx.State):
    # búsqueda de empleado
    texto_busqueda: str = ""
    resultados: list[dict] = []
    empleado_sel: str = ""
    nombre_sel: str = ""

    # historial del empleado seleccionado
    movimientos: list[dict] = []
    saldo_empleado: float = 0.0
    cargando_hist: bool = False

    # narrativa IA (Job)
    narrativa: str = ""
    narrativa_job: int = 0
    narrativa_status: str = ""

    # saldos de todos (Job)
    saldos_job: int = 0
    saldos_status: str = ""
    saldos_msg: str = ""
    saldos_path: str = ""

    @rx.event
    def set_texto(self, v: str):
        self.texto_busqueda = v

    async def _fuente(self) -> str:
        ds = await self.get_state(DataSourceState)
        return ds.fuente_por_modulo.get("prestamos", FUENTE_SQLSERVER)

    @rx.event
    async def buscar(self):
        if not self.texto_busqueda.strip():
            return
        fuente = await self._fuente()
        from core.repos import observaciones

        self.resultados = observaciones.buscar_empleados(self.texto_busqueda, fuente)

    @rx.event
    async def seleccionar(self, empleado: str, nombre: str):
        self.empleado_sel = empleado
        self.nombre_sel = nombre
        self.movimientos = []
        self.narrativa = ""
        self.cargando_hist = True
        yield
        fuente = await self._fuente()
        movs = await asyncio.to_thread(prestamos.historial_empleado, empleado, fuente)
        self.movimientos = [asdict(m) for m in movs]
        self.saldo_empleado = round(sum(m["valor"] for m in self.movimientos), 2)
        self.cargando_hist = False

    @rx.event
    async def generar_narrativa(self):
        if not self.movimientos:
            return rx.toast.error("Primero selecciona un empleado.")
        movs = await asyncio.to_thread(
            prestamos.historial_empleado, self.empleado_sel, await self._fuente()
        )
        deuda = self.saldo_empleado

        def _fn(ctx):
            from core.narrativa import narrar_prestamos

            ctx.progreso(0, 1, "Consultando IA…")
            texto = narrar_prestamos(movs, deuda)
            ctx.progreso(1, 1, texto)

        self.narrativa = ""
        self.narrativa_job = get_runner().encolar(
            "narrativa_prestamos", {"empleado": self.empleado_sel}, creado_por="", fn=_fn
        )
        self.narrativa_status = "pendiente"
        return PrestamosState.vigilar_narrativa

    @rx.event(background=True)
    async def vigilar_narrativa(self):
        for _ in range(120):
            async with self:
                jid = self.narrativa_job
            j = leer_job(jid)
            if j is None:
                return
            async with self:
                self.narrativa_status = j.status
                if j.status == "ok":
                    self.narrativa = j.message
                elif j.status == "error":
                    self.narrativa = f"No se pudo generar: {j.error[:300]}"
            if j.status in _TERMINALES:
                return
            await asyncio.sleep(1)

    # ── Saldos de todos (Job -> Excel) ──────────────────────────────────────
    @rx.event
    async def generar_saldos(self):
        fuente = await self._fuente()

        def _fn(ctx):
            from core import storage
            from core.excel.prestamos_builders import saldos_xlsx

            ctx.progreso(0, 1, "Consultando saldos…")
            data = saldos_xlsx(prestamos.saldos(fuente))
            ruta = storage.guardar(ctx.job_id, f"SALDOS_PRESTAMOS_{fuente}.xlsx", data)
            ctx.set_resultado(str(ruta))
            ctx.progreso(1, 1, "Listo")

        self.saldos_path = ""
        self.saldos_job = get_runner().encolar("saldos_prestamos", {}, creado_por="", fn=_fn)
        self.saldos_status = "pendiente"
        return PrestamosState.vigilar_saldos

    @rx.event(background=True)
    async def vigilar_saldos(self):
        for _ in range(600):
            async with self:
                jid = self.saldos_job
            j = leer_job(jid)
            if j is None:
                return
            async with self:
                self.saldos_status = j.status
                self.saldos_msg = j.message
                self.saldos_path = j.result_path
            if j.status in _TERMINALES:
                return
            await asyncio.sleep(1)

    @rx.event
    def cancelar_saldos(self):
        if self.saldos_job:
            JobRunner.cancelar(self.saldos_job)

    @rx.event
    def descargar_saldos(self):
        if not self.saldos_path:
            return rx.toast.error("Aún no hay archivo.")
        from pathlib import Path

        p = Path(self.saldos_path)
        return rx.download(data=p.read_bytes(), filename=p.name)
