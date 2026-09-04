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

    # ── Historial de varios períodos ─────────────────────────────────────
    hist_periodos: list[dict] = []   # [{'periodo','ingresos','egresos','neto','dias'}]
    hist_n: str = "6"
    hist_cargando: bool = False
    hist_detalle: list[dict] = []
    hist_detalle_periodo: str = ""

    @rx.event
    def set_hist_n(self, v: str):
        self.hist_n = v

    @rx.event
    async def cargar_varios_periodos(self):
        if not self.empleado_sel:
            return
        self.hist_cargando = True
        self.hist_detalle = []
        yield
        fuente = await self._fuente()
        emp_cod = self.empleado_sel
        try:
            n = max(1, min(24, int(self.hist_n)))
        except ValueError:
            n = 6
        hoy = dt.date.today()
        periodos = []
        y, m = hoy.year, hoy.month
        for _ in range(n):
            periodos.append(f"{y}-{m:02d}")
            m -= 1
            if m == 0:
                m, y = 12, y - 1

        def _run():
            filas = []
            for per in periodos:
                e = datos_empleado(per, emp_cod, fuente)
                if e is None:
                    continue
                filas.append({
                    "periodo": per, "dias": e.dias,
                    "ingresos": round(e.total_ingresos, 2),
                    "egresos": round(e.total_egresos, 2),
                    "neto": round(e.total_recibir, 2),
                    "conceptos": [{"concepto": k, "valor": round(v, 2)} for k, v in sorted(e.conceptos.items())],
                })
            return filas

        todo = await asyncio.to_thread(_run)
        self.hist_periodos = [{k: v for k, v in f.items() if k != "conceptos"} for f in todo]
        self._hist_conceptos = {f["periodo"]: f["conceptos"] for f in todo}
        self.hist_cargando = False

    _hist_conceptos: dict = {}

    @rx.event
    def ver_detalle_periodo(self, periodo: str):
        self.hist_detalle_periodo = periodo
        self.hist_detalle = self._hist_conceptos.get(periodo, [])

    @rx.event
    def exportar_historial(self):
        if not self.hist_periodos:
            return
        import csv
        import io

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Período", "Días", "Ingresos", "Egresos", "Neto"])
        for f in self.hist_periodos:
            w.writerow([f["periodo"], f["dias"], f["ingresos"], f["egresos"], f["neto"]])
        return rx.download(
            data=buf.getvalue().encode("utf-8"),
            filename=f"historial_nomina_{self.empleado_sel}.csv",
        )

    # ── Grid de búsqueda (página /empleados/buscar) ────────────────────────
    grid_texto: str = ""            # búsqueda contra el origen (código/cédula/nombre)
    grid_filtro_vivo: str = ""      # filtro incremental sobre lo ya cargado
    grid_estado: str = "ACTIVOS"    # ACTIVOS / INACTIVOS / TODOS
    grid: list[dict] = []
    grid_cargando: bool = False

    @rx.event
    def set_grid_texto(self, v: str):
        self.grid_texto = v

    @rx.event
    def set_grid_filtro_vivo(self, v: str):
        self.grid_filtro_vivo = v

    @rx.var
    def grid_filtrado(self) -> list[dict]:
        t = self.grid_filtro_vivo.strip().lower()
        if not t:
            return self.grid
        return [
            e for e in self.grid
            if t in e["empleado"].lower()
            or t in e["apellidos_nombres"].lower()
            or t in e["cedula"].lower()
        ]

    @rx.event
    async def set_grid_estado(self, v: str):
        self.grid_estado = v
        self.grid_cargando = True
        yield
        await self._recargar_grid()

    async def _recargar_grid(self):
        try:
            fuente = await self._fuente()
            self.grid = await asyncio.to_thread(
                repo_emp.buscar, self.grid_texto, fuente, estado=self.grid_estado
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

    # navegación primer / anterior / siguiente / último (sobre la lista filtrada)
    @rx.event
    async def ir_a_indice(self, delta: int, extremo: str = ""):
        filas = self.grid_filtrado
        if not filas:
            return
        if extremo == "primero":
            idx = 0
        elif extremo == "ultimo":
            idx = len(filas) - 1
        else:
            actuales = [i for i, e in enumerate(filas) if e["empleado"] == self.edit_empleado]
            base = actuales[0] if actuales else 0
            idx = max(0, min(len(filas) - 1, base + delta))
        cod = filas[idx]["empleado"]
        self.edit_empleado = cod
        self.cargando_editor = True
        yield
        await self._cargar_ficha(cod)

    # ── Búsqueda avanzada / Vista completa ────────────────────────────────
    av_apellidos: str = ""
    av_nombres: str = ""
    av_cedula: str = ""
    av_estado: str = ""
    av_depto: str = ""
    av_cargo: str = ""
    av_resultados: list[dict] = []
    av_cargando: bool = False
    av_msg: str = ""

    @rx.event
    def set_av(self, campo: str, v: str):
        setattr(self, f"av_{campo}", v)

    @rx.event
    async def buscar_avanzada(self, todos: bool = False):
        self.av_cargando = True
        self.av_msg = ""
        yield
        fuente = await self._fuente()
        try:
            self.av_resultados = await asyncio.to_thread(
                repo_emp.buscar_avanzado, fuente,
                apellidos="" if todos else self.av_apellidos,
                nombres="" if todos else self.av_nombres,
                cedula="" if todos else self.av_cedula,
                estado="" if todos else self.av_estado,
                depto="" if todos else self.av_depto,
                cargo="" if todos else self.av_cargo,
                limite=3000 if todos else 1000,
            )
            self.av_msg = f"{len(self.av_resultados)} empleados"
        except Exception as e:  # noqa: BLE001
            self.av_resultados = []
            self.av_msg = str(e)
        self.av_cargando = False

    @rx.event
    def exportar_avanzada(self):
        if not self.av_resultados:
            return
        from core.excel.empleados_builders import busqueda_avanzada_xlsx

        data = busqueda_avanzada_xlsx(list(self.av_resultados))
        return rx.download(data=data, filename="empleados.xlsx")

    @rx.event
    async def exportar_catalogos(self):
        from core.excel.empleados_builders import catalogos_xlsx

        fuente = await self._fuente()
        cat = await asyncio.to_thread(repo_emp.catalogos, fuente)
        return rx.download(data=catalogos_xlsx(cat), filename="catalogos.xlsx")

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
        if any(self.edit_catalogos.values()):
            return
        fuente = await self._fuente()
        try:
            cat = await asyncio.to_thread(repo_emp.catalogos, fuente)
        except Exception:  # noqa: BLE001
            cat = {}
        # cap por catálogo: el datalist con cientos de opciones ralentiza el navegador.
        self.edit_catalogos = {k: (v or [])[:120] for k, v in cat.items()} or self.edit_catalogos

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

    async def _cargar_ficha(self, empleado: str):
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
        self.foto_msg = ""
        self.edit_tab = "0"
        self.cargando_editor = False
        await self._cargar_foto()
        await self._cargar_catalogos_editor()
        await self._resolver_nombres_catalogo()

    edit_nombres_cat: dict[str, str] = {}  # campo -> nombre del código (DEPTO/CARGO/...)
    edit_tab: str = "0"

    @rx.event
    def set_edit_tab(self, v: str):
        self.edit_tab = v

    async def _resolver_nombres_catalogo(self):
        pares = [
            (tipo, str(self.edit_campos.get(campo, "")).strip())
            for campo, tipo in repo_emp.CAMPOS_CATALOGO.items()
            if str(self.edit_campos.get(campo, "")).strip()
        ]
        if not pares:
            self.edit_nombres_cat = {}
            return
        try:
            fuente = await self._fuente()
            res = await asyncio.to_thread(repo_emp.nombres_catalogo, fuente, pares)
        except Exception:  # noqa: BLE001
            res = {}
        self.edit_nombres_cat = {
            campo: res.get(str(self.edit_campos.get(campo, "")).strip(), "")
            for campo in repo_emp.CAMPOS_CATALOGO
        }

    @rx.event
    async def set_campo_catalogo(self, campo: str, valor: str):
        self.edit_campos[campo] = valor
        # refresca el nombre mostrado
        await self._resolver_nombres_catalogo()

    @rx.event
    async def abrir_editor(self, empleado: str):
        """Carga el empleado en el panel de detalle (misma pantalla, sin navegar)."""
        self.edit_error = self.edit_ok = ""
        self.edit_empleado = str(empleado)
        self.es_nuevo = False
        self.cargando_editor = True
        yield
        await self._cargar_ficha(empleado)

    @rx.event
    async def cancelar_edicion(self):
        cod = self.edit_empleado
        self.modo_edicion = False
        self.edit_ok = self.edit_error = ""
        if cod and cod != "NUEVO":
            self.cargando_editor = True
            yield
            await self._cargar_ficha(cod)

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

    # ── Casilla "Fondo de Reserva" (deriva de NUM_AFIL) ──────────────────
    @rx.var
    def fdr_marcado(self) -> bool:
        """Fondo de Reserva activo cuando NUM_AFIL != 9999999999."""
        v = str(self.edit_campos.get("NUM_AFIL", "")).strip().replace(".0", "")
        return v != "9999999999"

    @rx.var
    def fdr_num_real(self) -> bool:
        """NUM_AFIL tiene un número de afiliación real (no 0 ni 9999999999)."""
        v = str(self.edit_campos.get("NUM_AFIL", "")).strip().replace(".0", "")
        return v not in ("", "0", "9999999999")

    @rx.event
    def toggle_fdr(self):
        if self.fdr_marcado and self.fdr_num_real:
            yield rx.toast.warning(
                "Este empleado tiene un No. de afiliación IESS real. "
                "Para marcarlo como NO afiliado, bórrelo en Referencias."
            )
            return
        self.edit_campos["NUM_AFIL"] = "9999999999" if self.fdr_marcado else "0"

    @rx.event
    def imprimir_ficha(self):
        if not self.edit_campos:
            return
        from core.pdf.ficha_empleado import ficha_empleado_pdf

        data = ficha_empleado_pdf(self.edit_empleado, dict(self.edit_campos))
        return rx.download(data=data, filename=f"ficha_{self.edit_empleado}.pdf")

    # ── Foto del empleado ────────────────────────────────────────────────
    foto_uri: str = ""
    foto_msg: str = ""

    async def _cargar_foto(self):
        import base64

        from core.repos import fotos

        self.foto_uri = ""
        try:
            r = await asyncio.to_thread(fotos.leer_foto, self.edit_empleado)
        except Exception:  # noqa: BLE001
            r = None
        if r:
            datos, mime = r
            self.foto_uri = f"data:{mime};base64," + base64.b64encode(datos).decode("ascii")

    @rx.event
    async def subir_foto(self, files: list[rx.UploadFile]):
        from core.repos import fotos

        if not files or not self.edit_empleado or self.edit_empleado == "NUEVO":
            return
        datos = await files[0].read()
        try:
            await asyncio.to_thread(
                fotos.guardar_foto, self.edit_empleado, datos, files[0].name or ""
            )
            self.foto_msg = "Foto guardada."
        except Exception as e:  # noqa: BLE001
            self.foto_msg = str(e)
        await self._cargar_foto()

    @rx.event
    async def quitar_foto(self):
        from core.repos import fotos

        await asyncio.to_thread(fotos.borrar_foto, self.edit_empleado)
        self.foto_uri = ""
        self.foto_msg = "Foto eliminada."

    @rx.event
    async def guardar_foto_datauri(self, data_uri: str):
        """Recibe una foto tomada con la cámara (data:image/...;base64,...)."""
        import base64

        from core.repos import fotos

        if not self.edit_empleado or self.edit_empleado == "NUEVO" or "," not in data_uri:
            return
        try:
            crudo = base64.b64decode(data_uri.split(",", 1)[1])
            await asyncio.to_thread(fotos.guardar_foto, self.edit_empleado, crudo, "camara.jpg")
            self.foto_msg = "Foto guardada."
        except Exception as e:  # noqa: BLE001
            self.foto_msg = str(e)
        await self._cargar_foto()

    # ── Documentos (CV, certificado, contrato, renuncia) ─────────────────
    @rx.event
    def generar_documento(self, tipo: str):
        if not self.edit_campos:
            return
        from core.pdf.documentos_empleado import DOCUMENTOS

        if tipo not in DOCUMENTOS:
            return
        _nombre, fn = DOCUMENTOS[tipo]
        data = fn(self.edit_empleado, dict(self.edit_campos))
        return rx.download(data=data, filename=f"{tipo}_{self.edit_empleado}.pdf")

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
