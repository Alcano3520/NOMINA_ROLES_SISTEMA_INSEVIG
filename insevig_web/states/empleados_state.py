"""Estado del módulo Gestión de Empleados.

Fase 2: historial de nómina (solo lectura). Fase 3 añade CRUD y carga masiva.
"""

from __future__ import annotations

import asyncio
import datetime as dt

import reflex as rx

from core.datos.service import datos_empleado
from core.jobs.runner import get_runner, leer_job
from core.repos import empleados as repo_emp
from core.repos import observaciones
from insevig_web.states.auth_state import AuthState
from insevig_web.states.datasource_state import DataSourceState

GRUPOS = {g: list(cs) for g, cs in repo_emp.GRUPOS.items()}
_TERMINALES = {"ok", "error", "cancelado"}


def _limpiar_valor(k: str, v: object) -> str:
    """Muestra el valor sin ruido (cédula sin '.0', fechas sin hora)."""
    if v is None:
        return ""
    s = str(v).strip()
    if k == "CEDULA":
        from core.utils import normalizar_cedula

        return normalizar_cedula(v) if s not in ("", "None") else ""
    if s.endswith(".0"):
        s = s[:-2]
    if "T00:00:00" in s:
        s = s.split("T")[0]
    return s


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
        return await ds.resolver("empleados")

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
    async def toggle_solo_activos(self, v: bool):
        self.grid_solo_activos = v
        self.grid_cargando = True
        yield
        await self._recargar_grid()

    async def _recargar_grid(self):
        try:
            fuente = await self._fuente()
            self.grid = await asyncio.to_thread(
                repo_emp.buscar, self.grid_texto, fuente, solo_activos=self.grid_solo_activos
            )
        except Exception:  # noqa: BLE001
            self.grid = []
        self.grid_cargando = False

    @rx.event
    async def buscar_grid(self):
        self.grid_cargando = True
        yield
        await self._recargar_grid()

    @rx.event
    async def cargar_lista_inicial(self):
        """Al abrir Gestión de empleados: mostrar la lista (como el sistema anterior)."""
        if self.grid:
            return
        self.grid_cargando = True
        yield
        await self._recargar_grid()

    # ── Editor / CRUD (siempre SQL Server) ─────────────────────────────────
    edit_empleado: str = ""
    edit_campos: dict = {}
    edit_token: str = ""
    es_nuevo: bool = False
    edit_error: str = ""
    edit_ok: str = ""
    edit_audit: str = ""  # "creado por X · modificado por Y"
    modo_edicion: bool = False  # como el legado: hay que pulsar "Modificar" para editar
    confirmar_borrado: str = ""  # el usuario reescribe el código para confirmar
    edit_catalogos: dict[str, list[dict]] = {"FNC": [], "SEC": [], "DPT": [], "BAN": []}

    @rx.event
    def toggle_modo_edicion(self):
        self.modo_edicion = not self.modo_edicion
        self.edit_ok = self.edit_error = ""

    async def _cargar_catalogos_editor(self):
        if self.edit_catalogos:
            return
        fuente = await self._fuente()
        try:
            self.edit_catalogos = await asyncio.to_thread(repo_emp.catalogos, fuente)
        except Exception:  # noqa: BLE001
            self.edit_catalogos = {}

    cargando_editor: bool = False

    @rx.var
    def nombre_editor(self) -> str:
        c = self.edit_campos
        nom = f"{c.get('APELLIDOS', '')} {c.get('NOMBRES', '')}".strip()
        return f"{self.edit_empleado} — {nom}" if nom else f"Empleado {self.edit_empleado}"

    @rx.event
    def cerrar_editor(self):
        self.edit_empleado = ""
        self.edit_campos = {}
        self.es_nuevo = False
        self.modo_edicion = False
        self.edit_error = self.edit_ok = self.edit_audit = ""

    @rx.event
    async def abrir_editor(self, empleado: str):
        """Carga el empleado en el panel de detalle (misma pantalla, sin navegar)."""
        self.edit_error = self.edit_ok = ""
        self.edit_empleado = str(empleado)
        self.es_nuevo = False
        self.cargando_editor = True
        yield
        fuente = await self._fuente()
        try:
            e = await asyncio.to_thread(repo_emp.obtener, empleado, fuente)
        except Exception as ex:  # noqa: BLE001
            self.edit_error = f"No se pudo cargar el empleado: {ex}"
            self.cargando_editor = False
            return
        if e is None:
            self.edit_error = "Empleado no encontrado."
            self.cargando_editor = False
            return
        self.edit_empleado = e.empleado
        self.edit_campos = {k: _limpiar_valor(k, v) for k, v in e.campos.items()}
        self.edit_campos["EMPLEADO"] = e.empleado
        self.edit_token = e.token
        self.modo_edicion = False
        self.edit_audit = (
            f"Creado por {e.creado_por or '—'} ({e.fecha_crea or '—'}) · "
            f"Últ. modif. {e.mod_por or '—'} ({e.fecha_mod or '—'})"
        )
        self.edit_obs_slots = ["", "", "", "", "", "", ""]
        self.edit_obs_existe = False
        self.edit_obs_msg = ""
        self.cargando_editor = False
        await self._cargar_catalogos_editor()

    @rx.event
    async def nuevo(self):
        self.edit_empleado = "NUEVO"
        self.edit_campos = {c: "" for cs in GRUPOS.values() for c in cs}
        self.edit_campos["EMPLEADO"] = ""
        self.edit_token = ""
        self.es_nuevo = True
        self.modo_edicion = True
        self.edit_error = self.edit_ok = self.edit_audit = ""
        self.edit_obs_slots = ["", "", "", "", "", "", ""]
        yield
        await self._cargar_catalogos_editor()

    @rx.event
    def set_campo(self, campo: str, valor: str):
        self.edit_campos[campo] = valor

    @rx.event
    def toggle_campo(self, campo: str):
        actual = str(self.edit_campos.get(campo, ""))
        self.edit_campos[campo] = "" if actual in ("1", "S", "true") else "1"

    @rx.event
    async def guardar(self):
        auth = await self.get_state(AuthState)
        accion = "crear" if self.es_nuevo else "editar"
        if f"empleados:{accion}" not in auth.permisos_flat:
            self.edit_error = "Sin permiso."
            return
        if not self.es_nuevo and not self.modo_edicion:
            self.edit_error = "Pulsa 'Modificar' para habilitar la edicion."
            return
        req = [c for c in ("EMPLEADO", "CEDULA", "NOMBRES", "APELLIDOS") if not str(self.edit_campos.get(c, "")).strip()]
        if req:
            self.edit_error = "Campos obligatorios faltantes: " + ", ".join(req)
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
            self.modo_edicion = False
            e = await asyncio.to_thread(repo_emp.obtener, self.edit_empleado, "sqlserver")
            if e:
                self.edit_token = e.token
                self.edit_audit = (
                    f"Creado por {e.creado_por or '—'} ({e.fecha_crea or '—'}) · "
                    f"Últ. modif. {e.mod_por or '—'} ({e.fecha_mod or '—'})"
                )
        except repo_emp.ConflictoConcurrencia as e:
            self.edit_error = str(e)
        except Exception as e:  # noqa: BLE001
            self.edit_error = str(e)

    # ── Observaciones por período (pestaña dentro del editor) ──────────────
    edit_obs_periodo: str = ""
    edit_obs_slots: list[str] = ["", "", "", "", "", "", ""]
    edit_obs_existe: bool = False
    edit_obs_msg: str = ""
    obs_historial: list[dict] = []

    @rx.event
    def set_obs_periodo(self, v: str):
        self.edit_obs_periodo = v.strip()

    @rx.event
    def set_obs_slot(self, idx: int, v: str):
        s = list(self.edit_obs_slots)
        s[idx] = v
        self.edit_obs_slots = s

    @rx.event
    async def cargar_obs_editor(self):
        if not self.edit_empleado:
            return
        per = self.edit_obs_periodo or _periodo_actual()
        self.edit_obs_periodo = per
        fuente = await self._fuente()
        d = await asyncio.to_thread(observaciones.observaciones_mes, self.edit_empleado, per, fuente)
        self.edit_obs_existe = d["existe"]
        self.edit_obs_slots = d["slots"]
        self.edit_obs_msg = "" if d["existe"] else f"Sin observaciones para {per}. Puedes crear."

    @rx.event
    async def guardar_obs_editor(self):
        auth = await self.get_state(AuthState)
        if "empleados:editar" not in auth.permisos_flat:
            self.edit_obs_msg = "Sin permiso."
            return
        per = self.edit_obs_periodo or _periodo_actual()
        slots = list(self.edit_obs_slots)
        try:
            n = await asyncio.to_thread(
                observaciones.guardar_observaciones_mes,
                self.edit_empleado, per, slots,
                usuario=auth.username, roles=set(auth.roles),
            )
            self.edit_obs_msg = f"{n} campo(s) guardado(s)."
            self.edit_obs_existe = True
        except Exception as e:  # noqa: BLE001
            self.edit_obs_msg = str(e)

    @rx.event
    async def cargar_historial_obs(self):
        if not self.edit_empleado:
            return
        fuente = await self._fuente()
        filas = await asyncio.to_thread(
            observaciones.historial_observaciones, self.edit_empleado, fuente
        )
        self.obs_historial = [
            {"fecha_ven": f["fecha_ven"], "texto": " · ".join(f["textos"])} for f in filas
        ]

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
