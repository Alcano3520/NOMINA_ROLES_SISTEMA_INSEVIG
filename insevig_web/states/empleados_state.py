"""Estado del módulo Gestión de Empleados.

Fase 2: historial de nómina (solo lectura). Fase 3 añade CRUD y carga masiva.
"""

from __future__ import annotations

import asyncio
import datetime as dt

import reflex as rx

from core.datos.service import datos_empleado
from core.db.health import FUENTE_SQLSERVER
from core.jobs.runner import get_runner, leer_job
from core.repos import empleados as repo_emp
from core.repos import observaciones
from insevig_web.states.auth_state import AuthState
from insevig_web.states.datasource_state import DataSourceState

GRUPOS = {g: list(cs) for g, cs in repo_emp.GRUPOS.items()}
_TERMINALES = {"ok", "error", "cancelado"}


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

    # ── Grid de búsqueda (página /empleados/buscar) ────────────────────────
    grid_texto: str = ""
    grid_solo_activos: bool = True
    grid: list[dict] = []
    grid_cargando: bool = False

    @rx.event
    def set_grid_texto(self, v: str):
        self.grid_texto = v

    @rx.event
    def toggle_solo_activos(self, v: bool):
        self.grid_solo_activos = v

    @rx.event
    async def buscar_grid(self):
        self.grid_cargando = True
        yield
        fuente = await self._fuente()
        self.grid = await asyncio.to_thread(
            repo_emp.buscar, self.grid_texto, fuente, solo_activos=self.grid_solo_activos
        )
        self.grid_cargando = False

    # ── Editor / CRUD (siempre SQL Server) ─────────────────────────────────
    edit_empleado: str = ""
    edit_campos: dict = {}
    edit_token: str = ""
    es_nuevo: bool = False
    edit_error: str = ""
    edit_ok: str = ""
    confirmar_borrado: str = ""  # el usuario reescribe el código para confirmar

    @rx.event
    async def abrir_editor(self, empleado: str):
        e = await asyncio.to_thread(repo_emp.obtener, empleado, "sqlserver")
        if e is None:
            self.edit_error = "Empleado no encontrado."
            return
        self.edit_empleado = e.empleado
        self.edit_campos = {k: ("" if v is None else str(v)) for k, v in e.campos.items()}
        self.edit_token = e.token
        self.es_nuevo = False
        self.edit_error = self.edit_ok = ""
        return rx.redirect("/empleados/editar")

    @rx.event
    def nuevo(self):
        self.edit_empleado = ""
        self.edit_campos = {c: "" for cs in GRUPOS.values() for c in cs}
        self.edit_campos["EMPLEADO"] = ""
        self.edit_token = ""
        self.es_nuevo = True
        self.edit_error = self.edit_ok = ""
        return rx.redirect("/empleados/editar")

    @rx.event
    def set_campo(self, campo: str, valor: str):
        self.edit_campos[campo] = valor

    @rx.event
    async def guardar(self):
        auth = await self.get_state(AuthState)
        accion = "crear" if self.es_nuevo else "editar"
        if f"empleados:{accion}" not in auth.permisos_flat:
            self.edit_error = "Sin permiso."
            return
        campos, token = dict(self.edit_campos), self.edit_token
        usuario, roles = auth.username, set(auth.roles)
        self.edit_error = self.edit_ok = ""
        try:
            if self.es_nuevo:
                cod = await asyncio.to_thread(
                    repo_emp.crear, campos, usuario=usuario, roles=roles
                )
                self.edit_empleado, self.es_nuevo = cod, False
            else:
                await asyncio.to_thread(
                    repo_emp.actualizar, self.edit_empleado, campos, token,
                    usuario=usuario, roles=roles,
                )
            self.edit_ok = "Guardado."
            e = await asyncio.to_thread(repo_emp.obtener, self.edit_empleado, "sqlserver")
            if e:
                self.edit_token = e.token
        except repo_emp.ConflictoConcurrencia as e:
            self.edit_error = str(e)
        except Exception as e:  # noqa: BLE001
            self.edit_error = str(e)

    @rx.event
    def set_confirmar_borrado(self, v: str):
        self.confirmar_borrado = v

    @rx.event
    async def eliminar(self):
        auth = await self.get_state(AuthState)
        if "empleados:eliminar" not in auth.permisos_flat:
            self.edit_error = "Sin permiso."
            return
        if self.confirmar_borrado.strip() != self.edit_empleado:
            self.edit_error = "Escribe el código exacto para confirmar."
            return
        try:
            await asyncio.to_thread(
                repo_emp.eliminar, self.edit_empleado, usuario=auth.username, roles=set(auth.roles)
            )
        except Exception as e:  # noqa: BLE001
            self.edit_error = str(e)
            return
        self.confirmar_borrado = ""
        return rx.redirect("/empleados/buscar")

    # ── Carga masiva ──────────────────────────────────────────────────────
    masiva_filas: list[dict] = []
    masiva_errores: list[str] = []
    masiva_job: int = 0
    masiva_status: str = ""
    masiva_msg: str = ""
    masiva_path: str = ""

    @rx.event
    async def subir_masiva(self, files: list[rx.UploadFile]):
        from core.excel.parsers import parse_carga_masiva_empleados

        if not files:
            return
        datos = await files[0].read()
        filas, errores = parse_carga_masiva_empleados(datos)
        self.masiva_filas = filas[:500]
        self.masiva_errores = errores[:50]

    @rx.event
    async def aplicar_masiva(self):
        auth = await self.get_state(AuthState)
        if "empleados:cargar_masivo" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        filas = list(self.masiva_filas)
        usuario, roles = auth.username, set(auth.roles)

        def _fn(ctx):
            repo_emp.job_carga_masiva(ctx, filas, usuario=usuario, roles=roles)

        self.masiva_path = ""
        self.masiva_job = get_runner().encolar(
            "carga_masiva_empleados", {"n": len(filas)}, creado_por=usuario, fn=_fn
        )
        self.masiva_status = "pendiente"
        return EmpleadosState.vigilar_masiva

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
        from core.jobs.runner import JobRunner

        if self.masiva_job:
            JobRunner.cancelar(self.masiva_job)

    @rx.event
    def descargar_masiva(self):
        if not self.masiva_path:
            return
        from pathlib import Path

        p = Path(self.masiva_path)
        return rx.download(data=p.read_bytes(), filename=p.name)
