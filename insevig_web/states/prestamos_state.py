"""Estado del módulo Préstamos (Fase 2). Solo lectura."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict

import reflex as rx

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
    resumen: list[dict] = []  # agrupado por NUMERO de préstamo
    saldo_empleado: float = 0.0
    cargando_hist: bool = False
    filtro_desde: str = ""  # YYYY-MM-DD
    filtro_hasta: str = ""
    filtro_tipo: str = ""    # "" | ingreso | egreso
    filtro_origen: str = ""  # "" | RPINGDES | RPHISTOR | MIGRADO
    filtro_numero: str = ""
    filtro_texto: str = ""
    filtro_monto_min: str = ""
    filtro_monto_max: str = ""
    exportar_job: int = 0
    exportar_status: str = ""
    exportar_path: str = ""

    @rx.event
    def set_filtro(self, campo: str, v: str):
        setattr(self, f"filtro_{campo}", v.strip())

    @rx.event
    def limpiar_filtros(self):
        self.filtro_desde = self.filtro_hasta = self.filtro_tipo = ""
        self.filtro_origen = self.filtro_numero = self.filtro_texto = ""
        self.filtro_monto_min = self.filtro_monto_max = ""

    def _filtros_kwargs(self) -> dict:
        def _num(s: str):
            try:
                return float(s.replace(",", "")) if s.strip() else None
            except ValueError:
                return None

        return {
            "tipo": self.filtro_tipo,
            "origen": self.filtro_origen,
            "numero": self.filtro_numero,
            "texto": self.filtro_texto,
            "desde": self.filtro_desde,
            "hasta": self.filtro_hasta,
            "monto_min": _num(self.filtro_monto_min),
            "monto_max": _num(self.filtro_monto_max),
        }

    @rx.var
    def hay_filtros(self) -> bool:
        return any(
            [
                self.filtro_desde, self.filtro_hasta, self.filtro_tipo, self.filtro_origen,
                self.filtro_numero, self.filtro_texto, self.filtro_monto_min, self.filtro_monto_max,
            ]
        )

    @rx.var
    def movimientos_filtrados(self) -> list[dict]:
        if not self.hay_filtros:
            return self.movimientos
        return prestamos.filtrar_movimientos(list(self.movimientos), **self._filtros_kwargs())

    @rx.var
    def total_filtrado(self) -> float:
        """Suma de los movimientos visibles (informativa)."""
        return round(sum(m["valor"] for m in self.movimientos_filtrados), 2)

    @rx.var
    def pagado_filtrado(self) -> float:
        return round(sum(m["valor"] for m in self.movimientos_filtrados if m["tipo"] == "pago"), 2)

    @rx.var
    def conteo_filtrado(self) -> str:
        vis = sum(1 for m in self.movimientos_filtrados if not m["es_cuadre"])
        tot = sum(1 for m in self.movimientos if not m["es_cuadre"])
        return f"{vis} de {tot}" + (" (filtrado)" if vis != tot else "")

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
        return await ds.resolver("prestamos")

    @rx.event
    async def buscar(self):
        if not self.texto_busqueda.strip():
            return
        fuente = await self._fuente()
        from core.repos import observaciones

        self.resultados = observaciones.buscar_empleados(self.texto_busqueda, fuente)

    # ── Panel "Empleados con saldo" (como el del .pyw, siempre visible) ──────
    panel_saldos: list[dict] = []
    panel_filtro: str = ""
    panel_cargando: bool = False

    @rx.event
    async def cargar_panel_saldos(self):
        if self.panel_saldos or self.panel_cargando:
            return
        self.panel_cargando = True
        yield
        fuente = await self._fuente()
        filas = await asyncio.to_thread(prestamos.saldos, fuente)
        self.panel_saldos = [
            {"empleado": s.empleado, "nombre": s.apellidos_nombres, "saldo": round(s.saldo, 2)}
            for s in filas
            if s.saldo > 0.01
        ]
        self.panel_cargando = False

    @rx.event
    def set_panel_filtro(self, v: str):
        self.panel_filtro = v

    @rx.var
    def panel_saldos_filtrado(self) -> list[dict]:
        q = self.panel_filtro.strip().lower()
        filas = self.panel_saldos
        if q:
            filas = [
                f for f in filas
                if q in str(f["nombre"]).lower() or q in str(f["empleado"]).lower()
            ]
        return filas[:300]

    @rx.var
    def panel_saldos_resumen(self) -> str:
        n = len(self.panel_saldos)
        total = round(sum(f["saldo"] for f in self.panel_saldos), 2)
        return f"{n} empleados · saldo total ${total:,.2f}"

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
        self.resumen = [asdict(g) for g in prestamos.agrupar_por_numero(movs)]
        self.saldo_empleado = round(
            sum(m["valor"] for m in self.movimientos if m["tipo"] == "pendiente"), 2
        )
        self.cargando_hist = False

    # detalle de un préstamo (doble clic en la fila del resumen)
    detalle_movs: list[dict] = []
    detalle_titulo: str = ""

    @rx.event
    def ver_detalle_prestamo(self, numero: str):
        movs = [prestamos.MovimientoPrestamo(**m) for m in self.movimientos]
        d = prestamos.movimientos_de_numero(movs, numero)
        self.detalle_movs = [asdict(m) for m in d]
        self.detalle_titulo = f"Préstamo N° {numero} — {len(d)} movimientos"

    @rx.event
    def cerrar_detalle(self):
        self.detalle_movs = []
        self.detalle_titulo = ""

    @rx.event
    async def exportar_empleado(self):
        if not self.empleado_sel:
            return rx.toast.error("Selecciona un empleado.")
        fuente = await self._fuente()
        cod, nombre = self.empleado_sel, self.nombre_sel
        filtros = self._filtros_kwargs() if self.hay_filtros else None

        def _fn(ctx):
            from dataclasses import asdict as _asdict

            from core import storage
            from core.excel.prestamos_builders import historial_xlsx

            ctx.progreso(0, 1, "Generando Excel…")
            movs = prestamos.historial_empleado(cod, fuente)
            if filtros:
                claves = {
                    (m["fecha"], round(m["valor"], 2), m["numero"], m["origen"])
                    for m in prestamos.filtrar_movimientos([_asdict(m) for m in movs], **filtros)
                }
                movs = [m for m in movs if (m.fecha, round(m.valor, 2), m.numero, m.origen) in claves]
            data = historial_xlsx(cod, nombre, movs)
            ruta = storage.guardar(ctx.job_id, f"PRESTAMOS_{cod}.xlsx", data)
            ctx.set_resultado(str(ruta))
            ctx.progreso(1, 1, "Listo")

        self.exportar_path = ""
        self.exportar_job = get_runner().encolar("prestamos_empleado", {"emp": cod}, creado_por="", fn=_fn)
        self.exportar_status = "pendiente"
        return PrestamosState.vigilar_exportar

    @rx.event(background=True)
    async def vigilar_exportar(self):
        for _ in range(300):
            async with self:
                jid = self.exportar_job
            j = leer_job(jid)
            if j is None:
                return
            async with self:
                self.exportar_status = j.status
                self.exportar_path = j.result_path
            if j.status in _TERMINALES:
                return
            await asyncio.sleep(1)

    @rx.event
    def descargar_exportar(self):
        if not self.exportar_path:
            return rx.toast.error("Aún no hay archivo.")
        from pathlib import Path

        p = Path(self.exportar_path)
        return rx.download(data=p.read_bytes(), filename=p.name)

    @rx.event
    def leer_en_voz_alta(self):
        """Lee la narrativa con la Web Speech API del navegador (sin depender de gTTS)."""
        if not self.narrativa:
            return
        texto = json.dumps(self.narrativa)
        return rx.call_script(
            "window.speechSynthesis.cancel();"
            f"var u=new SpeechSynthesisUtterance({texto});u.lang='es-ES';"
            "window.speechSynthesis.speak(u);"
        )

    @rx.event
    def detener_voz(self):
        return rx.call_script("window.speechSynthesis.cancel();")

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
