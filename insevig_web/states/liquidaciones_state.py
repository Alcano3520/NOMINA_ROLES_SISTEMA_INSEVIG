"""Estado del módulo Liquidaciones (módulo 9)."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import asdict

import reflex as rx

from core.db.health import FUENTE_SUPABASE
from core.jobs.runner import JobRunner, get_runner, leer_job
from core.repos import liquidaciones as repo
from insevig_web.states.auth_state import AuthState
from insevig_web.states.datasource_state import DataSourceState

_TERMINALES = {"ok", "error", "cancelado"}

# Paridad con `MOTIVOS_SALIDA` del `.pyw` (combo del modo Individual, editable).
MOTIVOS_SALIDA = [
    "RENUNCIA VOLUNTARIA", "DESPIDO INTEMPESTIVO", "VISTO BUENO",
    "CONTRATO A PRUEBA", "TÉRMINO DE CONTRATO", "CONSIGNACIÓN",
    "MUTUO ACUERDO", "JUBILACIÓN", "MUERTE", "OTRO",
]


class LiquidacionesState(rx.State):
    entrada: str = ""  # cédula, fecha (dd/mm/aaaa), motivo  — una por línea
    region: str = "COSTA"

    # "1. Formato de Salida": MASIVO (Excel, por plantilla) o INDIVIDUAL (PDF,
    # un solo empleado con vista previa) — paridad con el selector del `.pyw`.
    formato: str = "MASIVO"

    # "RESUMEN DE LIQUIDACIONES GUARDADAS" (4 tarjetas por estado).
    resumen: dict[str, int] = {}

    previsualizacion: list[dict] = []  # resumen por empleado (modo masivo)
    _liqs: list[repo.Liquidacion] = []  # objetos completos, en el mismo orden (uso interno)
    fila_msg: dict[str, str] = {}  # índice (str) -> mensaje ("Guardada", error…)
    job: int = 0
    status: str = ""
    msg: str = ""
    path: str = ""

    # ── Modo Individual (PDF de 1 empleado + vista previa) ──────────────────
    busqueda_modo: str = "cedula"  # cedula | codigo | nombre
    ind_identificador: str = ""
    ind_fecha: str = ""
    ind_motivo: str = ""
    ind_emp: dict[str, str] = {}  # panel "Datos del Empleado" (solo lectura)
    ind_buscando: bool = False
    ind_msg: str = ""
    # Casillas del `.pyw` ya conectadas al motor de cálculo (las otras 3 —
    # desahucio sobre ingresos reales, valores reales del mes en curso,
    # incluir/excluir sueldo del mes de salida — quedan pendientes, ver
    # docs/modulos/liquidaciones.md).
    ind_incluir_dec13_ant: bool = False
    ind_incluir_dec14_ant: bool = False
    ind_mostrar_insumos: bool = False
    ind_conceptos: list[dict] = []  # vista previa: concepto/tipo/valor
    ind_totales: dict[str, float] = {}
    _ind_liq: repo.Liquidacion | None = None

    @rx.event
    def set_entrada(self, v: str):
        self.entrada = v

    @rx.event
    def set_region(self, v: str):
        self.region = v

    @rx.event
    def set_formato(self, v: str):
        self.formato = v

    @rx.event
    def set_busqueda_modo(self, v: str):
        self.busqueda_modo = v

    @rx.event
    def set_ind_identificador(self, v: str):
        self.ind_identificador = v

    @rx.event
    def set_ind_fecha(self, v: str):
        self.ind_fecha = v

    @rx.event
    def set_ind_motivo(self, v: str):
        self.ind_motivo = v

    @rx.event
    def set_ind_incluir_dec13_ant(self, v: bool):
        self.ind_incluir_dec13_ant = v

    @rx.event
    def set_ind_incluir_dec14_ant(self, v: bool):
        self.ind_incluir_dec14_ant = v

    @rx.event
    def set_ind_mostrar_insumos(self, v: bool):
        self.ind_mostrar_insumos = v

    @rx.event
    async def cargar_pantalla(self):
        """on_load: fecha de hoy por defecto + resumen de guardadas."""
        import datetime as _dt

        if not self.ind_fecha:
            self.ind_fecha = _dt.date.today().strftime("%d/%m/%Y")

        def _run():
            return repo.resumen_liquidaciones()

        try:
            self.resumen = await asyncio.to_thread(_run)
        except Exception:  # noqa: BLE001
            self.resumen = {}

    async def _fuente(self) -> str:
        ds = await self.get_state(DataSourceState)
        # las tablas históricas grandes están en Supabase; por defecto Supabase aquí
        return ds.fuente_por_modulo.get("liquidaciones", FUENTE_SUPABASE)

    @rx.event
    async def buscar_empleado_individual(self):
        self.ind_msg = ""
        if not self.ind_identificador.strip():
            self.ind_msg = "Ingrese una cédula, código o nombre."
            return
        fuente = await self._fuente()
        modo, identificador = self.busqueda_modo, self.ind_identificador

        def _run():
            return repo.buscar_empleado_preview(identificador, modo, fuente)

        self.ind_buscando = True
        yield
        try:
            emp = await asyncio.to_thread(_run)
        finally:
            self.ind_buscando = False
        if emp is None:
            self.ind_emp = {}
            self.ind_msg = "No se encontró ningún empleado con ese dato."
            return
        self.ind_emp = {k: str(v) for k, v in emp.items()}
        self.ind_conceptos = []
        self.ind_totales = {}
        self._ind_liq = None

    @rx.event
    async def calcular_individual(self):
        self.ind_msg = ""
        if not self.ind_emp.get("cedula"):
            self.ind_msg = "Busque un empleado primero."
            return
        fuente = await self._fuente()
        from core.parametros import config_liquidacion

        cfg = config_liquidacion(self.region)
        cedula, fecha, motivo = self.ind_emp["cedula"], self.ind_fecha, self.ind_motivo
        dec13, dec14 = self.ind_incluir_dec13_ant, self.ind_incluir_dec14_ant

        def _run():
            return repo.procesar_empleado(
                cedula, fecha, motivo, fuente, cfg,
                incluir_dec13_anterior=dec13, incluir_dec14_anterior=dec14,
            )

        liq = await asyncio.to_thread(_run)
        self._ind_liq = liq
        if liq.error:
            self.ind_msg = liq.error
            self.ind_conceptos = []
            self.ind_totales = {}
            return
        # Paridad con el `.pyw`: el décimo "anterior" (ya pagado) solo se
        # MUESTRA en la vista previa si el usuario marca la casilla — no solo
        # se excluye del total (evita confundirlo con dinero pendiente).
        conceptos = repo.previsualizar_conceptos(liq)
        if not dec13:
            conceptos = [c for c in conceptos if c["concepto_codigo"] != "DEC_TERCERA_ANT"]
        if not dec14:
            conceptos = [c for c in conceptos if c["concepto_codigo"] != "DEC_CUARTA_ANT"]
        self.ind_conceptos = conceptos
        self.ind_totales = {
            "ingresos": liq.campos.get("TOTAL_INGRESOS", 0.0),
            "descuentos": liq.campos.get("TOTAL_DESCUENTOS", 0.0),
            "recibir": liq.campos.get("TOTAL_A_RECIBIR", 0.0),
        }

    @rx.event
    def generar_pdf_individual(self):
        liq = self._ind_liq
        if liq is None or liq.error:
            return rx.toast.error("Calcule la liquidación primero.")
        from core.pdf.liquidacion_individual import liquidacion_pdf

        data = liquidacion_pdf(liq, mostrar_insumos=self.ind_mostrar_insumos, es_simulacion=True)
        return rx.download(data=data, filename=f"liquidacion_{liq.empleado}_{liq.fecha_salida}.pdf")

    @rx.event
    async def guardar_individual(self):
        auth = await self.get_state(AuthState)
        if "liquidaciones:editar" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        liq = self._ind_liq
        if liq is None or liq.error:
            return rx.toast.error("Calcule la liquidación primero.")
        from core.parametros import config_liquidacion

        cfg = config_liquidacion(self.region)
        usuario, roles = auth.username, set(auth.roles)

        def _guardar():
            existente = repo.buscar_liquidacion_existente(
                liq.cedula, liq.fecha_salida, "generada", liq.fecha_ingreso
            )
            return repo.guardar_liquidacion(
                liq, "generada", cfg, usuario=usuario, roles=roles,
                liquidacion_id_existente=existente or "",
            )

        ok, resultado = await asyncio.to_thread(_guardar)
        self.ind_msg = "Guardada en el sistema." if ok else f"Error al guardar: {resultado}"
        if ok:

            def _run():
                return repo.resumen_liquidaciones()

            with contextlib.suppress(Exception):
                self.resumen = await asyncio.to_thread(_run)

    @rx.event
    async def previsualizar(self):
        if not self.entrada.strip():
            return
        fuente = await self._fuente()
        from core.parametros import config_liquidacion
        cfg = config_liquidacion(self.region)
        texto = self.entrada

        def _run():
            return repo.procesar_lote(texto, fuente, cfg)

        liqs = await asyncio.to_thread(_run)
        self._liqs = liqs
        self.fila_msg = {}
        self.previsualizacion = [
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

    @rx.event
    def generar_pdf_fila(self, idx: int):
        if not 0 <= idx < len(self._liqs):
            return
        liq = self._liqs[idx]
        if liq.error:
            return rx.toast.error(liq.error)
        from core.pdf.liquidacion_individual import liquidacion_pdf

        data = liquidacion_pdf(liq, es_simulacion=True)
        return rx.download(data=data, filename=f"liquidacion_{liq.empleado}_{liq.fecha_salida}.pdf")

    @rx.event
    async def guardar_fila(self, idx: int):
        auth = await self.get_state(AuthState)
        if "liquidaciones:editar" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        if not 0 <= idx < len(self._liqs):
            return
        liq = self._liqs[idx]
        if liq.error:
            self.fila_msg = {**self.fila_msg, str(idx): liq.error}
            return
        from core.parametros import config_liquidacion

        cfg = config_liquidacion(self.region)
        usuario, roles = auth.username, set(auth.roles)

        def _guardar():
            existente = repo.buscar_liquidacion_existente(
                liq.cedula, liq.fecha_salida, "generada", liq.fecha_ingreso
            )
            return repo.guardar_liquidacion(
                liq, "generada", cfg, usuario=usuario, roles=roles,
                liquidacion_id_existente=existente or "",
            )

        ok, resultado = await asyncio.to_thread(_guardar)
        self.fila_msg = {
            **self.fila_msg,
            str(idx): "Guardada en el sistema." if ok else f"Error al guardar: {resultado}",
        }

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
