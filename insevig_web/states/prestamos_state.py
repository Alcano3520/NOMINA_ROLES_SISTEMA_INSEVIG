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

_IA_LABELS = {
    "Todo el historial": "todo", "Año actual": "anio",
    "Último año": "ultimo_anio", "Último semestre": "semestre",
}


def _a_fecha(txt: str):
    import datetime as _dt

    s = str(txt or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _filtrar_rango_ia(movs: list, rango: str) -> list:
    """Filtra los movimientos por el rango del análisis IA (como el .pyw:
    Todo / Año actual / Último año / Último semestre)."""
    import datetime as _dt

    if rango in ("", "todo"):
        return movs
    hoy = _dt.date.today()
    if rango == "anio":
        desde = _dt.date(hoy.year, 1, 1)
    elif rango == "ultimo_anio":
        desde = hoy - _dt.timedelta(days=365)
    elif rango == "semestre":
        desde = hoy - _dt.timedelta(days=183)
    else:
        return movs
    out = []
    for m in movs:
        f = _a_fecha(getattr(m, "fecha", ""))
        if f is None or f >= desde:
            out.append(m)
    return out


class PrestamosState(rx.State):
    # búsqueda de empleado
    texto_busqueda: str = ""
    resultados: list[dict] = []
    empleado_sel: str = ""
    nombre_sel: str = ""

    # historial del empleado seleccionado
    movimientos: list[dict] = []          # movimientos crudos (para IA / export)
    hist_crudas: list[dict] = []          # filas del árbol antes de numerar
    hist_info: dict[str, str] = {}        # nombre / cédula / saldo / históricos / total
    saldo_empleado: float = 0.0
    cargando_hist: bool = False
    filtro_desde: str = ""  # DD/MM/AAAA o YYYY-MM-DD
    filtro_hasta: str = ""
    filtro_tipo: str = ""    # "" | INGRESO | EGRESO   (como el combo Tipo del .pyw)
    filtro_origen: str = ""  # "" | SISTEMA | HISTORICO (como el combo Origen del .pyw)
    filtro_numero: str = ""
    filtro_texto: str = ""    # observación
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

        def _iso(s: str) -> str:
            f = _a_fecha(s)
            return f.isoformat() if f else ""

        return {
            "tipo": self.filtro_tipo,
            "origen": self.filtro_origen,
            "numero": self.filtro_numero,
            "texto": self.filtro_texto,
            "desde": _iso(self.filtro_desde),
            "hasta": _iso(self.filtro_hasta),
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
    def filas_historial(self) -> list[dict]:
        """Filas del árbol (# / FECHA / INGRESO / EGRESO / NÚMERO / OBSERV / TIPO /
        SALDO) — filtradas y numeradas, igual que `mostrar_movimientos_en_tree`."""
        crudas = list(self.hist_crudas)
        if self.hay_filtros:
            crudas = prestamos.filtrar_historial(crudas, **self._filtros_kwargs())
        return [asdict(f) for f in prestamos.numerar_historial(crudas)]

    @rx.var
    def hist_mostrando(self) -> str:
        vis = len(self.filas_historial)
        tot = len(self.hist_crudas)
        txt = f"Mostrando {vis} de {tot} registros"
        return txt + (" (FILTRADO)" if vis != tot else "")

    @rx.var
    def info_empleado_txt(self) -> str:
        """Banda 'Información del Empleado' del .pyw."""
        i = self.hist_info
        if not i:
            return ""
        partes = [
            f"\U0001f464 {i.get('nombre', '')}",
            f"\U0001f194 {i.get('cedula', '')}",
            f"\U0001f4b0 SALDO: {i.get('saldo', '')}",
        ]
        if i.get("historicos") not in (None, "", "0"):
            partes.append(f"\U0001f4c1 HISTÓRICOS: {i.get('historicos')}")
        if i.get("total") not in (None, "", "0"):
            partes.append(f"\U0001f4ca TOTAL: {i.get('total')}")
        return "   •   ".join(partes)

    # narrativa IA (Job)
    narrativa: str = ""
    narrativa_job: int = 0
    narrativa_status: str = ""
    ia_rango: str = "todo"  # todo | anio | ultimo_anio | semestre

    @rx.event
    def set_ia_rango(self, v: str):
        self.ia_rango = _IA_LABELS.get(v, "todo")

    @rx.var
    def ia_rango_label(self) -> str:
        return next((lbl for lbl, val in _IA_LABELS.items() if val == self.ia_rango),
                    "Todo el historial")

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
    panel_solo_activos: bool = True   # checkbox "Act." del panel

    @rx.event
    async def cargar_panel_saldos(self):
        if self.panel_saldos or self.panel_cargando:
            return
        self.panel_cargando = True
        yield
        fuente = await self._fuente()
        filas = await asyncio.to_thread(prestamos.saldos, fuente)
        self.panel_saldos = [
            {
                "empleado": s.empleado, "nombre": s.apellidos_nombres,
                "cedula": s.cedula, "saldo": round(s.saldo, 2),
                "situacion": s.situacion,
            }
            for s in filas
            if s.saldo > 0.01
        ]
        self.panel_cargando = False

    @rx.event
    def set_panel_filtro(self, v: str):
        self.panel_filtro = v

    @rx.event
    def toggle_panel_activos(self, v: bool):
        self.panel_solo_activos = bool(v)

    @rx.var
    def panel_saldos_filtrado(self) -> list[dict]:
        q = self.panel_filtro.strip().lower()
        filas = self.panel_saldos
        if self.panel_solo_activos and any(f.get("situacion") for f in filas):
            filas = [f for f in filas if f.get("situacion") == "ACT"]
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
        self.hist_crudas = []
        self.hist_info = {}
        self.narrativa = ""
        self.cargando_hist = True
        yield
        fuente = await self._fuente()
        movs = await asyncio.to_thread(prestamos.historial_empleado, empleado, fuente)
        crudas, info = await asyncio.to_thread(prestamos.historial_display, empleado, fuente)
        self.movimientos = [asdict(m) for m in movs]
        self.hist_crudas = crudas
        self.hist_info = {
            "nombre": info.nombre or nombre,
            "cedula": info.cedula,
            "saldo": f"{info.saldo_total:,.2f}",
            "historicos": str(info.historicos),
            "total": str(info.total),
        }
        self.saldo_empleado = round(info.saldo_total, 2)
        self.cargando_hist = False

    # detalle de un MOVIMIENTO individual (clic en la fila del historial) — como
    # el diálogo "DETALLE DEL {INGRESO|EGRESO}" del .pyw
    mov_detalle: dict[str, str] = {}

    @rx.event
    def ver_mov_detalle(self, fila: dict):
        """Detalle de la fila (como el diálogo 'DETALLE DEL {INGRESO|EGRESO}')."""
        ing = float(fila.get("ingreso", 0) or 0)
        egr = float(fila.get("egreso", 0) or 0)
        self.mov_detalle = {
            "fecha": str(fila.get("fecha", "")),
            "numero": str(fila.get("numero", "")).replace(" [H]", ""),
            "posicion": str(fila.get("posicion", "")),
            "valor": f"{(ing or egr):,.2f}",
            "saldo": f"{float(fila.get('saldo', 0) or 0):,.2f}",
            "tipo": str(fila.get("tipo", "")),
            "origen": (
                "Histórico (SQLite)" if fila.get("historico")
                else "Sistema Actual (SQL Server)"
            ),
            "concepto": str(fila.get("observacion", "") or "Sin observaciones registradas"),
        }

    @rx.event
    def cerrar_mov_detalle(self):
        self.mov_detalle = {}

    @rx.var
    def mov_detalle_abierto(self) -> bool:
        return bool(self.mov_detalle)

    @rx.event
    async def exportar_empleado(self):
        if not self.empleado_sel:
            return rx.toast.error("Selecciona un empleado.")
        fuente = await self._fuente()
        cod, nombre = self.empleado_sel, self.nombre_sel

        def _fn(ctx):
            from core import storage
            from core.excel.prestamos_builders import historial_xlsx

            ctx.progreso(0, 1, "Generando Excel…")
            movs = prestamos.historial_empleado(cod, fuente)
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
        movs = _filtrar_rango_ia(movs, self.ia_rango)
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
