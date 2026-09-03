"""Estado del módulo Roles de pago (Fase 4)."""

from __future__ import annotations

import asyncio
import datetime as dt

import reflex as rx

from core.datos.service import datos_empleado
from core.db.health import FUENTE_SQLSERVER
from core.jobs.runner import JobRunner, get_runner, leer_job
from core.pdf.layout import FORMATOS
from core.pdf.rol_pago import OpcionesRol, rol_pago_pdf
from insevig_web.states.auth_state import AuthState
from insevig_web.states.datasource_state import DataSourceState

_TERMINALES = {"ok", "error", "cancelado"}
FORMATOS_LISTA = list(FORMATOS)


def _periodo_actual() -> str:
    return dt.date.today().strftime("%Y-%m")


def _rango(periodo: str) -> tuple[str, str]:
    anio, mes = periodo.split("-")
    fin = "31" if mes in ("01", "03", "05", "07", "08", "10", "12") else ("28" if mes == "02" else "30")
    return f"01/{mes}/{anio}", f"{fin}/{mes}/{anio}"


class RolesState(rx.State):
    periodo: str = ""
    identificador: str = ""  # para rol individual
    dos_por_hoja: bool = False
    formato: str = "cedula-nombre"

    # rol individual
    pdf_listo: bool = False
    _pdf_bytes: bytes = b""
    error: str = ""

    # lote
    lista_texto: str = ""  # una identificación por línea
    lote_job: int = 0
    lote_status: str = ""
    lote_msg: str = ""
    lote_path: str = ""

    @rx.event
    def on_load(self):
        if not self.periodo:
            self.periodo = _periodo_actual()

    @rx.event
    def set_periodo(self, v: str):
        self.periodo = v.strip()

    @rx.event
    def set_identificador(self, v: str):
        self.identificador = v

    @rx.event
    def set_lista(self, v: str):
        self.lista_texto = v

    @rx.event
    def set_formato(self, v: str):
        self.formato = v

    @rx.event
    def toggle_doble(self, v: bool):
        self.dos_por_hoja = v

    async def _fuente(self) -> str:
        ds = await self.get_state(DataSourceState)
        return ds.fuente_por_modulo.get("roles", FUENTE_SQLSERVER)

    @rx.event
    async def generar_individual(self):
        auth = await self.get_state(AuthState)
        if "roles:generar_pdf" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        if not self.identificador.strip():
            self.error = "Indica un empleado."
            return
        self.error = ""
        self.pdf_listo = False
        fuente = await self._fuente()
        periodo = self.periodo or _periodo_actual()
        desde, hasta = _rango(periodo)
        ident, doble = self.identificador, self.dos_por_hoja

        def _gen() -> bytes | None:
            emp = datos_empleado(periodo, ident, fuente)
            if emp is None:
                return None
            return rol_pago_pdf(emp, OpcionesRol(fecha_desde=desde, fecha_hasta=hasta, dos_por_hoja=doble))

        data = await asyncio.to_thread(_gen)
        if data is None:
            self.error = "Empleado no encontrado para ese período."
            return
        self._pdf_bytes = data
        self.pdf_listo = True

    @rx.event
    def descargar_individual(self):
        if not self._pdf_bytes:
            return
        return rx.download(data=self._pdf_bytes, filename=f"rol_{self.identificador}_{self.periodo}.pdf")

    @rx.event
    async def generar_lote(self):
        auth = await self.get_state(AuthState)
        if "roles:generar_pdf" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        ids = [x.strip() for x in self.lista_texto.replace(",", "\n").splitlines() if x.strip()]
        if not ids:
            return rx.toast.error("Pega al menos una identificación.")
        fuente = await self._fuente()
        periodo = self.periodo or _periodo_actual()
        desde, hasta = _rango(periodo)
        formato, doble = self.formato, self.dos_por_hoja

        def _fn(ctx):
            from core.pdf.batch import job_lote_roles

            job_lote_roles(
                ctx, periodo, ids, fuente, formato,
                OpcionesRol(fecha_desde=desde, fecha_hasta=hasta, dos_por_hoja=doble),
            )

        self.lote_path = ""
        self.lote_job = get_runner().encolar(
            "roles_lote", {"periodo": periodo, "n": len(ids)}, creado_por=auth.username, fn=_fn
        )
        self.lote_status = "pendiente"
        return RolesState.vigilar_lote

    @rx.event(background=True)
    async def vigilar_lote(self):
        for _ in range(3600):
            async with self:
                jid = self.lote_job
            j = leer_job(jid)
            if j is None:
                return
            async with self:
                self.lote_status = j.status
                self.lote_msg = j.message
                self.lote_path = j.result_path
            if j.status in _TERMINALES:
                return
            await asyncio.sleep(1)

    @rx.event
    def cancelar_lote(self):
        if self.lote_job:
            JobRunner.cancelar(self.lote_job)

    @rx.event
    def descargar_lote(self):
        if not self.lote_path:
            return
        from pathlib import Path

        p = Path(self.lote_path)
        return rx.download(data=p.read_bytes(), filename=p.name)
