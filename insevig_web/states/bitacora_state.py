"""Estado del módulo BITACORAS — Agenda de cobro de liquidación de haberes."""

from __future__ import annotations

import asyncio

import reflex as rx

from core.repos import bitacora
from insevig_web.states.auth_state import AuthState

CAMPOS = list(bitacora.CAMPOS)
ESTADOS = list(bitacora.ESTADOS)


class BitacoraState(rx.State):
    filtro_estado: str = ""
    filtro_texto: str = ""
    registros: list[dict] = []
    cargando: bool = False
    error: str = ""
    msg: str = ""

    # editor
    editando_id: int = 0
    form: dict = {}
    mostrar_form: bool = False

    @rx.event
    def set_filtro_texto(self, v: str):
        self.filtro_texto = v

    @rx.event
    def set_filtro_estado(self, v: str):
        self.filtro_estado = "" if v == "(todos)" else v

    @rx.event
    async def cargar(self):
        self.cargando = True
        self.error = ""
        yield
        try:
            self.registros = await asyncio.to_thread(
                bitacora.listar, self.filtro_estado, self.filtro_texto
            )
        except Exception as e:  # noqa: BLE001
            self.error = f"No se pudo cargar (¿Supabase disponible?): {e}"
        self.cargando = False

    @rx.event
    def nuevo(self):
        self.editando_id = 0
        self.form = {c: "" for c in CAMPOS}
        self.form["estado"] = "pendiente"
        self.mostrar_form = True
        self.msg = ""

    @rx.event
    def editar(self, reg: dict):
        self.editando_id = reg.get("id", 0)
        self.form = {c: ("" if reg.get(c) is None else str(reg.get(c))) for c in CAMPOS}
        self.mostrar_form = True
        self.msg = ""

    @rx.event
    def cerrar_form(self):
        self.mostrar_form = False

    @rx.event
    def set_campo(self, campo: str, v: str):
        self.form[campo] = v

    @rx.event
    async def guardar(self):
        auth = await self.get_state(AuthState)
        accion = "editar" if self.editando_id else "crear"
        if f"bitacora:{accion}" not in auth.permisos_flat:
            self.msg = "Sin permiso."
            return
        datos = dict(self.form)
        rid, usuario, roles = self.editando_id, auth.username, set(auth.roles)
        try:
            if rid:
                await asyncio.to_thread(bitacora.actualizar, rid, datos, usuario=usuario, roles=roles)
            else:
                await asyncio.to_thread(bitacora.crear, datos, usuario=usuario, roles=roles)
            self.msg = "Guardado."
            self.mostrar_form = False
            await self.cargar()
        except Exception as e:  # noqa: BLE001
            self.msg = f"Error: {e}"

    @rx.event
    async def cambiar_estado(self, reg_id: int, estado: str):
        auth = await self.get_state(AuthState)
        if "bitacora:editar" not in auth.permisos_flat:
            return
        await asyncio.to_thread(
            bitacora.cambiar_estado, reg_id, estado, usuario=auth.username, roles=set(auth.roles)
        )
        await self.cargar()

    @rx.event
    async def eliminar(self, reg_id: int):
        auth = await self.get_state(AuthState)
        if "bitacora:eliminar" not in auth.permisos_flat:
            self.msg = "Sin permiso."
            return
        await asyncio.to_thread(
            bitacora.eliminar, reg_id, usuario=auth.username, roles=set(auth.roles)
        )
        await self.cargar()
