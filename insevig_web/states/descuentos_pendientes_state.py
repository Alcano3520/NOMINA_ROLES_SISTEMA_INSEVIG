"""Estado de la pantalla 'Descuentos Pendientes' (módulo liquidaciones)."""

from __future__ import annotations

import asyncio

import reflex as rx

from core.repos import descuentos_pendientes as repo
from insevig_web.states.auth_state import AuthState


class DescuentosPendientesState(rx.State):
    filtro: str = "pendiente"   # "" | pendiente | aplicado
    filas: list[dict] = []
    cargando: bool = False
    msg: str = ""
    seleccion: list[str] = []

    # formulario de alta individual
    f_cedula: str = ""
    f_nombre: str = ""
    f_motivo: str = ""
    f_monto: str = ""
    f_fecha: str = ""
    bulk_texto: str = ""

    @rx.event
    def set_campo(self, campo: str, v: str):
        setattr(self, f"f_{campo}", v)

    @rx.event
    def set_bulk(self, v: str):
        self.bulk_texto = v

    @rx.event
    async def set_filtro(self, v: str):
        self.filtro = "" if v == "todos" else v
        await self._recargar()

    async def _recargar(self):
        """Lógica de carga sin `yield` — se puede `await`-ear directo desde
        otro handler (a diferencia de `cargar`, que es un generador async por
        el `yield` de abajo y no se puede `await`)."""
        try:
            self.filas = await asyncio.to_thread(repo.listar, self.filtro)
        except Exception as e:  # noqa: BLE001
            self.msg = f"No se pudo cargar: {e}"
            self.filas = []
        self.seleccion = []

    @rx.event
    async def cargar(self):
        self.cargando = True
        self.msg = ""
        yield
        await self._recargar()
        self.cargando = False

    @rx.event
    def toggle_sel(self, did: str):
        self.seleccion = (
            [x for x in self.seleccion if x != did]
            if did in self.seleccion
            else [*self.seleccion, did]
        )

    async def _puede(self) -> bool:
        auth = await self.get_state(AuthState)
        return "liquidaciones:editar" in auth.permisos_flat

    @rx.event
    async def crear(self):
        if not await self._puede():
            return rx.toast.error("Sin permiso.")
        auth = await self.get_state(AuthState)
        datos = dict(
            cedula=self.f_cedula, nombre=self.f_nombre, motivo=self.f_motivo,
            monto=self.f_monto or "0", fecha=self.f_fecha,
        )

        def _run():
            try:
                monto = float(str(datos["monto"]).replace("$", "").replace(",", "."))
            except ValueError:
                return False, "El monto no es un número."
            return repo.crear(
                cedula=datos["cedula"], nombre=datos["nombre"], motivo=datos["motivo"],
                monto=monto, fecha=datos["fecha"], usuario=auth.username,
            )

        ok, err = await asyncio.to_thread(_run)
        if not ok:
            self.msg = err
            return
        self.f_cedula = self.f_nombre = self.f_motivo = self.f_monto = self.f_fecha = ""
        self.msg = "Descuento registrado."
        await self._recargar()

    @rx.event
    async def crear_masivo(self):
        if not await self._puede():
            yield rx.toast.error("Sin permiso.")
            return
        auth = await self.get_state(AuthState)
        texto = self.bulk_texto

        creados, errores = await asyncio.to_thread(repo.crear_masivo, texto, usuario=auth.username)
        self.msg = f"{creados} descuento(s) registrado(s)." + (
            f" {len(errores)} con error." if errores else ""
        )
        for e in errores[:5]:
            yield rx.toast.warning(e)
        if creados:
            self.bulk_texto = ""
        await self._recargar()

    @rx.event
    async def eliminar_seleccionados(self):
        if not await self._puede():
            return rx.toast.error("Sin permiso.")
        if not self.seleccion:
            return rx.toast.error("Marca al menos un descuento.")
        auth = await self.get_state(AuthState)
        ids = list(self.seleccion)
        await asyncio.to_thread(repo.eliminar, ids, usuario=auth.username)
        self.msg = f"{len(ids)} descuento(s) eliminado(s)."
        await self._recargar()
