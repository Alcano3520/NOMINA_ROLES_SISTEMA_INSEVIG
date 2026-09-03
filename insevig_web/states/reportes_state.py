"""Estado del módulo Reportes (Fase 1). Solo lectura; salida = Excel vía Job."""

from __future__ import annotations

import asyncio
import datetime as dt

import reflex as rx

from core.audit.writer import registrar_evento
from core.db.health import FUENTE_SQLSERVER
from core.jobs.runner import JobRunner, get_runner, leer_job
from core.repos import nomina
from insevig_web.states.auth_state import AuthState
from insevig_web.states.datasource_state import DataSourceState

_TERMINALES = {"ok", "error", "cancelado"}


def _periodo_actual() -> str:
    return dt.date.today().strftime("%Y-%m")


class ReportesState(rx.State):
    periodo: str = ""
    historico: bool = False

    job_id: int = 0
    job_status: str = ""
    job_progress: int = 0
    job_total: int = 0
    job_message: str = ""
    job_error: str = ""
    result_path: str = ""

    @rx.var
    def corriendo(self) -> bool:
        return self.job_status in ("pendiente", "corriendo")

    @rx.var
    def periodo_efectivo(self) -> str:
        return self.periodo or _periodo_actual()

    @rx.event
    def on_load(self):
        if not self.periodo:
            self.periodo = _periodo_actual()

    @rx.event
    def set_alcance(self, etiqueta: str):
        self.historico = etiqueta.startswith("Histórico")

    async def _fuente(self) -> str:
        ds = await self.get_state(DataSourceState)
        return ds.fuente_por_modulo.get("reportes", FUENTE_SQLSERVER)

    @rx.event
    async def generar(self):
        auth = await self.get_state(AuthState)
        if "reportes:ver" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso para generar reportes.")
        fuente = await self._fuente()
        self._reset_job()
        runner = get_runner()
        job_id = runner.encolar(
            "reporte_consolidado",
            {"periodo": self.periodo_efectivo, "historico": self.historico, "fuente": fuente},
            creado_por=auth.username,
            fn=lambda ctx: nomina.job_consolidado(
                ctx, self.periodo_efectivo, self.historico, fuente
            ),
        )
        registrar_evento("reportes", "generar", usuario=auth.username, roles=set(auth.roles), fuente=fuente)
        self.job_id = job_id
        self.job_status = "pendiente"
        return ReportesState.vigilar

    @rx.event
    async def generar_comparador(self):
        auth = await self.get_state(AuthState)
        if "reportes:exportar" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        self._reset_job()
        job_id = get_runner().encolar(
            "reporte_comparador",
            {"periodo": self.periodo_efectivo, "historico": self.historico},
            creado_por=auth.username,
            fn=lambda ctx: nomina.job_comparador(ctx, self.periodo_efectivo, self.historico),
        )
        self.job_id = job_id
        self.job_status = "pendiente"
        return ReportesState.vigilar

    @rx.event(background=True)
    async def vigilar(self):
        while True:
            j = leer_job(self.job_id)
            if j is None:
                return
            async with self:
                self.job_status = j.status
                self.job_progress = j.progress
                self.job_total = j.total
                self.job_message = j.message
                self.job_error = j.error
                self.result_path = j.result_path
            if j.status in _TERMINALES:
                return
            await asyncio.sleep(1)

    @rx.event
    def cancelar(self):
        if self.job_id:
            JobRunner.cancelar(self.job_id)

    @rx.event
    def descargar(self):
        if not self.result_path:
            return rx.toast.error("Aún no hay archivo.")
        from pathlib import Path

        p = Path(self.result_path)
        return rx.download(data=p.read_bytes(), filename=p.name)

    def _reset_job(self):
        self.job_id = 0
        self.job_status = ""
        self.job_progress = 0
        self.job_total = 0
        self.job_message = ""
        self.job_error = ""
        self.result_path = ""
