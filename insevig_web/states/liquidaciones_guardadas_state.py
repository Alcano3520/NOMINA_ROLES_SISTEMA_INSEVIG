"""Estado de 'Liquidaciones guardadas' — Editor + Gestión de liquidaciones
(módulo 9), combinados en una sola pantalla: buscar, ver detalle, cambiar
estado, eliminar y regenerar PDF de lo ya guardado en Supabase."""

from __future__ import annotations

import asyncio

import reflex as rx

from core.repos import liquidaciones as repo
from insevig_web.states.auth_state import AuthState

ESTADOS = list(repo.ESTADOS_LIQUIDACION)


class LiquidacionesGuardadasState(rx.State):
    texto: str = ""
    estado_filtro: str = ""
    filas: list[dict] = []
    cargando: bool = False
    msg: str = ""

    @rx.event
    def set_texto(self, v: str):
        self.texto = v

    @rx.event
    def set_estado_filtro(self, v: str):
        self.estado_filtro = "" if v == "(todos)" else v

    @rx.event
    async def buscar(self):
        self.cargando = True
        self.msg = ""
        yield
        texto, estado = self.texto, self.estado_filtro
        try:
            filas = await asyncio.to_thread(repo.listar_liquidaciones, texto=texto, estado=estado)
        except Exception as e:  # noqa: BLE001
            self.msg = f"No se pudo cargar: {e}"
            filas = []
        self.filas = filas
        self.cargando = False

    # ── Detalle ──────────────────────────────────────────────────────
    detalle_id: str = ""
    detalle: dict = {}
    detalle_conceptos: list[dict] = []
    detalle_msg: str = ""

    @rx.event
    async def ver_detalle(self, liquidacion_id: str):
        self.detalle_id = liquidacion_id
        self.detalle = {}
        self.detalle_conceptos = []
        self.detalle_msg = ""
        yield
        registro, conceptos = await asyncio.to_thread(repo.obtener_liquidacion, liquidacion_id)
        if registro is None:
            self.detalle_msg = "No se encontró esa liquidación."
            return
        self.detalle = registro
        self.detalle_conceptos = conceptos

    @rx.event
    def cerrar_detalle(self):
        self.detalle_id = ""
        self.detalle = {}
        self.detalle_conceptos = []

    @rx.event
    async def cambiar_estado(self, liquidacion_id: str, estado: str):
        auth = await self.get_state(AuthState)
        if "liquidaciones:editar" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        try:
            await asyncio.to_thread(
                repo.cambiar_estado_liquidacion, liquidacion_id, estado,
                usuario=auth.username, roles=set(auth.roles),
            )
            self.msg = f"Estado actualizado a «{estado}»."
        except Exception as e:  # noqa: BLE001
            self.msg = f"Error: {e}"
        await self.buscar()
        if self.detalle_id == liquidacion_id:
            await self.ver_detalle(liquidacion_id)

    @rx.event
    async def eliminar(self, liquidacion_id: str):
        auth = await self.get_state(AuthState)
        if "admin" not in auth.roles:
            return rx.toast.error("Solo un administrador puede eliminar una liquidación guardada.")
        ok, error = await asyncio.to_thread(
            repo.eliminar_liquidacion, liquidacion_id, "Eliminada desde Liquidaciones guardadas",
            usuario=auth.username, roles=set(auth.roles),
        )
        self.msg = "Liquidación eliminada." if ok else f"No se pudo eliminar: {error}"
        if ok and self.detalle_id == liquidacion_id:
            self.cerrar_detalle()
        await self.buscar()

    @rx.event
    def generar_pdf(self, liquidacion_id: str):
        registro, conceptos = repo.obtener_liquidacion(liquidacion_id)
        if registro is None:
            return rx.toast.error("No se encontró esa liquidación.")
        from core.pdf.liquidacion_individual import liquidacion_pdf

        liq = repo.reconstruir_liquidacion(registro, conceptos)
        data = liquidacion_pdf(liq, es_simulacion=False)
        return rx.download(
            data=data, filename=f"liquidacion_{liq.empleado}_{liq.fecha_salida}.pdf"
        )
