"""Estado del módulo SANCIONES — reemplazo web de `sistema_sanciones_RRHH/main.py`.

RRHH y gerencia revisan / aprueban / rechazan / procesan los reportes que cargan
supervisores y coordinadores (tabla `sanciones` del proyecto Supabase
`syxzopyevfuwymmltbwn`), + novedades de horario + estadísticas + reportes.

Todas las llamadas a `core/` van por `asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import datetime as dt

import reflex as rx

from core.repos import sanciones as repo
from core.sanciones import catalogos
from insevig_web.states.auth_state import AuthState

_HOY = dt.date.today()


def _roles(auth: AuthState) -> set[str]:
    return set(auth.roles or [])


class SancionesState(rx.State):
    # ═══════════════════════ BANDEJA ═══════════════════════
    tab: str = "aprobacion"                     # aprobacion | proceso
    aprob: list[dict] = []
    proceso: list[dict] = []
    cargando: bool = False
    sel: list[str] = []                          # ids seleccionados
    motivo_rechazo: str = ""
    msg: str = ""

    @rx.event
    def set_tab(self, v: str | list[str]):
        self.tab = v if isinstance(v, str) else (v[0] if v else "aprobacion")
        self.sel = []

    @rx.event
    def set_motivo_rechazo(self, v: str):
        self.motivo_rechazo = v

    @rx.event
    def toggle_sel(self, sid: str):
        self.sel = [x for x in self.sel if x != sid] if sid in self.sel else [*self.sel, sid]

    @rx.event
    def sel_todos(self):
        filas = self.aprob if self.tab == "aprobacion" else self.proceso
        ids = [f["id"] for f in filas]
        self.sel = [] if set(self.sel) >= set(ids) else ids

    @rx.event
    async def cargar_bandeja(self):
        self.cargando = True
        self.msg = ""
        yield
        try:
            self.aprob = await asyncio.to_thread(repo.obtener_sanciones_pendientes_aprobacion)
            self.proceso = await asyncio.to_thread(repo.obtener_sanciones_pendientes)
        finally:
            self.cargando = False

    @rx.var
    def bandeja_actual(self) -> list[dict]:
        return self.aprob if self.tab == "aprobacion" else self.proceso

    @rx.var
    def conteo_aprob(self) -> int:
        return len(self.aprob)

    @rx.var
    def conteo_proceso(self) -> int:
        return len(self.proceso)

    @rx.event
    async def aprobar_sel(self):
        auth = await self.get_state(AuthState)
        filas = {f["id"]: f for f in self.aprob}
        objetivo = [filas[i] for i in self.sel if i in filas]
        if not objetivo:
            self.msg = "Seleccioná al menos una sanción."
            return
        ok, fail, errs = await asyncio.to_thread(
            repo.aprobar_multiples_sanciones, objetivo, auth.username,
        )
        self.msg = f"Aprobadas {ok}, con error {fail}."
        self.sel = []
        await self._recargar()

    @rx.event
    async def rechazar_sel(self):
        auth = await self.get_state(AuthState)
        motivo = self.motivo_rechazo.strip()
        if len(motivo) < catalogos.VALIDACIONES["motivo_rechazo_minimo"]:
            self.msg = f"El motivo de rechazo debe tener al menos {catalogos.VALIDACIONES['motivo_rechazo_minimo']} caracteres."
            return
        filas = {f["id"]: f for f in self.aprob}
        objetivo = [filas[i] for i in self.sel if i in filas]
        if not objetivo:
            self.msg = "Seleccioná al menos una sanción."
            return
        ok = fail = 0
        for s in objetivo:
            exito, _ = await asyncio.to_thread(
                repo.rechazar_sancion_individual, s, auth.username, motivo,
            )
            ok += exito
            fail += not exito
        self.msg = f"Rechazadas {ok}, con error {fail}."
        self.sel = []
        self.motivo_rechazo = ""
        await self._recargar()

    @rx.event
    async def procesar_sel(self):
        auth = await self.get_state(AuthState)
        filas = {f["id"]: f for f in self.proceso}
        objetivo = [filas[i] for i in self.sel if i in filas]
        if not objetivo:
            self.msg = "Seleccioná al menos una sanción."
            return
        ok, fail, errs = await asyncio.to_thread(
            repo.procesar_multiples_sanciones, objetivo, auth.username,
        )
        self.msg = f"Procesadas {ok}, con error {fail}." + (f" {errs[0]}" if errs else "")
        self.sel = []
        await self._recargar()

    async def _recargar(self):
        self.aprob = await asyncio.to_thread(repo.obtener_sanciones_pendientes_aprobacion)
        self.proceso = await asyncio.to_thread(repo.obtener_sanciones_pendientes)

    # ═══════════════════════ HISTORIAL ═══════════════════════
    hist: list[dict] = []
    hist_page: int = 1
    hist_has_more: bool = False
    hist_cargando: bool = False

    @rx.event
    async def hist_cargar(self, page: int = 1):
        self.hist_cargando = True
        self.hist_page = max(1, page)
        yield
        try:
            res = await asyncio.to_thread(repo.obtener_procesadas_completas, self.hist_page)
            self.hist = res["data"]
            self.hist_has_more = res["has_more"]
        finally:
            self.hist_cargando = False

    @rx.event
    async def hist_siguiente(self):
        async for x in self.hist_cargar(self.hist_page + 1):
            yield x

    @rx.event
    async def hist_anterior(self):
        async for x in self.hist_cargar(self.hist_page - 1):
            yield x

    @rx.event
    async def exportar_historial(self):
        data = await asyncio.to_thread(repo.exportar_excel, self.hist)
        if not data:
            return rx.toast.error("No se pudo generar el Excel (¿openpyxl instalado? ¿hay datos?).")
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        return rx.download(data=data, filename=f"Sanciones_Historial_{ts}.xlsx")

    # ═══════════════════════ BUSCAR ═══════════════════════
    q_texto: str = ""
    q_tipo: str = ""
    q_solo_hist: bool = False
    q_resultados: list[dict] = []
    q_buscando: bool = False

    @rx.event
    def set_q_texto(self, v: str):
        self.q_texto = v

    @rx.event
    def set_q_tipo(self, v: str):
        self.q_tipo = v

    @rx.event
    def toggle_q_solo_hist(self, v: bool):
        self.q_solo_hist = bool(v)

    @rx.event
    async def buscar(self):
        self.q_buscando = True
        yield
        try:
            self.q_resultados = await asyncio.to_thread(
                repo.buscar_sanciones, self.q_texto, 300,
                self.q_tipo or None, self.q_solo_hist,
            )
        finally:
            self.q_buscando = False

    @rx.event
    async def exportar_busqueda(self):
        data = await asyncio.to_thread(repo.exportar_excel, self.q_resultados)
        if not data:
            return rx.toast.error("Nada que exportar.")
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        return rx.download(data=data, filename=f"Sanciones_Busqueda_{ts}.xlsx")

    # ═══════════════════════ FICHA DE DETALLE ═══════════════════════
    detalle: dict = {}
    detalle_abierto: bool = False
    detalle_urls: dict = {}

    @rx.event
    async def ver_detalle(self, sid: str):
        s = await asyncio.to_thread(repo.obtener_sancion, sid)
        if not s:
            return rx.toast.error("No se encontró la sanción.")
        s = await asyncio.to_thread(repo.enriquecer_sanciones_lote, [s])
        self.detalle = s[0]
        self.detalle_urls = await asyncio.to_thread(repo.resolver_urls_evidencia, self.detalle)
        self.detalle_abierto = True

    @rx.event
    def cerrar_detalle(self):
        self.detalle_abierto = False

    @rx.event
    async def descargar_pdf_detalle(self):
        sid = self.detalle.get("id")
        if not sid:
            return
        data = await asyncio.to_thread(repo.ficha_pdf, sid)
        if not data:
            return rx.toast.error("No se pudo generar el PDF (¿reportlab instalado?).")
        return rx.download(data=data, filename=f"sancion_{sid[:8]}.pdf")

    # ═══════════════════════ NOVEDADES DE HORARIO ═══════════════════════
    nov: list[dict] = []
    nov_cargando: bool = False
    nov_obs: dict = {}                           # {novedad_id: observacion}

    @rx.event
    async def nov_cargar(self):
        self.nov_cargando = True
        yield
        try:
            self.nov = await asyncio.to_thread(repo.obtener_novedades_pendientes, 200)
        finally:
            self.nov_cargando = False

    @rx.event
    def set_nov_obs(self, nid: str, v: str):
        self.nov_obs = {**self.nov_obs, nid: v}

    @rx.event
    async def nov_marcar(self, nid: int):
        obs = self.nov_obs.get(str(nid), "")
        ok = await asyncio.to_thread(repo.marcar_novedad_procesada, nid, obs)
        if ok:
            self.nov = [n for n in self.nov if n.get("id") != nid]
        else:
            return rx.toast.error("No se pudo marcar la novedad.")

    # ═══════════════════════ ESTADÍSTICAS ═══════════════════════
    stats: dict = {}
    stats_cargando: bool = False

    @rx.event
    async def stats_cargar(self):
        self.stats_cargando = True
        yield
        try:
            self.stats = await asyncio.to_thread(repo.estadisticas)
        finally:
            self.stats_cargando = False

    @rx.var
    def stats_por_estado(self) -> list[dict]:
        return [{"k": k, "v": v} for k, v in (self.stats.get("por_estado") or {}).items()]

    @rx.var
    def stats_por_tipo(self) -> list[dict]:
        return [{"k": k, "v": v} for k, v in (self.stats.get("por_tipo") or {}).items()]

    # ── valores monetarios (config, admin) ───────────────────────────
    valores: list[dict] = []
    val_edit: dict = {}

    @rx.event
    async def cargar_valores(self):
        from core.sanciones.valores import get_valores

        d = await asyncio.to_thread(get_valores)
        self.valores = [{"tipo": k, "valor": v} for k, v in sorted(d.items())]

    @rx.event
    def set_val_edit(self, tipo: str, v: str):
        self.val_edit = {**self.val_edit, tipo: v}

    @rx.event
    async def guardar_valor(self, tipo: str):
        from core.sanciones.valores import set_valor

        try:
            v = float(self.val_edit.get(tipo, "0"))
        except ValueError:
            return rx.toast.error("Valor inválido.")
        await asyncio.to_thread(set_valor, tipo, v)
        await self.cargar_valores()
        return rx.toast.success(f"{tipo}: {v}")
