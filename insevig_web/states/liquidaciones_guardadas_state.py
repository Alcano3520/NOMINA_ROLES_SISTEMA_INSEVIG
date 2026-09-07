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
        self.editando = False
        self.edit_valores = {}

    # ── Edición manual de valores (Editor del legado) ────────────────
    editando: bool = False
    edit_valores: dict[str, str] = {}   # concepto_codigo -> valor (texto)
    edit_msg: str = ""

    @rx.var
    def conceptos_editables(self) -> list[dict]:
        """`detalle_conceptos` + el valor en edición de cada concepto (texto)."""
        out = []
        for c in self.detalle_conceptos:
            cod = str(c["concepto_codigo"])
            out.append({**c, "edit_valor": self.edit_valores.get(cod, str(c["valor_total"]))})
        return out

    @rx.event
    def abrir_edicion(self):
        self.edit_valores = {
            str(c["concepto_codigo"]): str(c["valor_total"]) for c in self.detalle_conceptos
        }
        self.editando = True
        self.edit_msg = ""

    @rx.event
    def cancelar_edicion(self):
        self.editando = False
        self.edit_valores = {}
        self.edit_msg = ""

    @rx.event
    def set_edit_valor(self, codigo: str, v: str):
        self.edit_valores = {**self.edit_valores, codigo: v}

    @rx.event
    async def guardar_edicion(self):
        auth = await self.get_state(AuthState)
        if "liquidaciones:editar" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso para editar liquidaciones.")
        originales = {str(c["concepto_codigo"]): round(float(c["valor_total"]), 2) for c in self.detalle_conceptos}
        cambios: dict[str, float] = {}
        for cod, txt in self.edit_valores.items():
            try:
                nuevo = round(float(str(txt).replace(",", ".").strip() or 0), 2)
            except ValueError:
                self.edit_msg = f"Valor inválido en {cod}: «{txt}»."
                return
            if nuevo != originales.get(cod):
                cambios[cod] = nuevo
        if not cambios:
            self.edit_msg = "No cambiaste ningún valor."
            return
        ok, error = await asyncio.to_thread(
            repo.editar_valores_liquidacion, self.detalle_id, cambios,
            usuario=auth.username, roles=set(auth.roles),
        )
        if not ok:
            self.edit_msg = error
            return
        self.editando = False
        self.edit_valores = {}
        self.msg = f"Liquidación corregida ({len(cambios)} concepto(s))."
        await self.ver_detalle(self.detalle_id)
        await self.buscar()

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
