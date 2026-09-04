"""Estado del módulo Liquidaciones (módulo 9)."""

from __future__ import annotations

import asyncio
from dataclasses import asdict

import reflex as rx

from core.db.health import FUENTE_SUPABASE
from core.jobs.runner import JobRunner, get_runner, leer_job
from core.repos import liquidaciones as repo
from insevig_web.states.auth_state import AuthState
from insevig_web.states.datasource_state import DataSourceState

_TERMINALES = {"ok", "error", "cancelado"}


class LiquidacionesState(rx.State):
    entrada: str = ""  # cédula, fecha (dd/mm/aaaa), motivo  — una por línea
    region: str = "COSTA"

    previsualizacion: list[dict] = []  # resumen por empleado
    job: int = 0
    status: str = ""
    msg: str = ""
    path: str = ""

    @rx.event
    def set_entrada(self, v: str):
        self.entrada = v

    @rx.event
    def set_region(self, v: str):
        self.region = v

    async def _fuente(self) -> str:
        ds = await self.get_state(DataSourceState)
        # las tablas históricas grandes están en Supabase; por defecto Supabase aquí
        return ds.fuente_por_modulo.get("liquidaciones", FUENTE_SUPABASE)

    @rx.event
    async def previsualizar(self):
        if not self.entrada.strip():
            return
        fuente = await self._fuente()
        from core.parametros import config_liquidacion
        cfg = config_liquidacion(self.region)
        texto = self.entrada

        def _run():
            liqs = repo.procesar_lote(texto, fuente, cfg)
            return [
                {
                    "empleado": q.empleado,
                    "nombre": q.nombre or q.cedula,
                    "motivo": q.motivo_salida,
                    "dias": q.dias_trabajados,
                    "ingresos": q.campos.get("TOTAL_INGRESOS", 0.0),
                    "descuentos": q.campos.get("TOTAL_DESCUENTOS", 0.0),
                    "recibir": q.campos.get("TOTAL_A_RECIBIR", 0.0),
                    "error": q.error,
                }
                for q in liqs
            ]

        self.previsualizacion = await asyncio.to_thread(_run)

    @rx.event
    async def generar_excel(self):
        auth = await self.get_state(AuthState)
        if "liquidaciones:generar_pdf" not in auth.permisos_flat and "liquidaciones:ver" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        fuente = await self._fuente()
        texto, region, usuario = self.entrada, self.region, auth.username

        def _fn(ctx):
            from core import storage
            from core.excel.liquidaciones_builders import liquidaciones_xlsx

            ctx.progreso(0, 1, "Calculando liquidaciones…")
            from core.parametros import config_liquidacion
            cfg = config_liquidacion(region)
            liqs = repo.procesar_lote(texto, fuente, cfg)
            data = liquidaciones_xlsx(liqs)
            ruta = storage.guardar(ctx.job_id, "LIQUIDACIONES.xlsx", data)
            ctx.set_resultado(str(ruta))
            ok = sum(1 for q in liqs if not q.error)
            ctx.progreso(1, 1, f"Listo: {ok} liquidaciones, {len(liqs) - ok} con error")

        self.path = ""
        self.job = get_runner().encolar("liquidaciones", {"n": len(self.entrada.splitlines())},
                                        creado_por=usuario, fn=_fn)
        self.status = "pendiente"
        return LiquidacionesState.vigilar

    @rx.event(background=True)
    async def vigilar(self):
        for _ in range(3600):
            async with self:
                jid = self.job
            j = leer_job(jid)
            if j is None:
                return
            async with self:
                self.status = j.status
                self.msg = j.message
                self.path = j.result_path
            if j.status in _TERMINALES:
                return
            await asyncio.sleep(1)

    @rx.event
    def cancelar(self):
        if self.job:
            JobRunner.cancelar(self.job)

    @rx.event
    def descargar(self):
        if not self.path:
            return
        from pathlib import Path

        p = Path(self.path)
        return rx.download(data=p.read_bytes(), filename=p.name)


_ = asdict  # (helper reservado para futuros usos)
