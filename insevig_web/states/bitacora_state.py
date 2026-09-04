"""Estado del módulo BITÁCORA — Agenda de cobro de liquidación de haberes
+ Bitácora de Atención Personal + Reportes."""

from __future__ import annotations

import asyncio
import datetime as dt

import reflex as rx

from core.repos import bitacora
from insevig_web.states.auth_state import AuthState

CAMPOS = list(bitacora.CAMPOS)
ESTADOS = list(bitacora.ESTADOS)
FORMAS_PAGO = list(bitacora.FORMAS_PAGO)
ETIQUETAS = dict(bitacora.ETIQUETAS)
CAMPOS_FECHA = sorted(bitacora.CAMPOS_FECHA)


class BitacoraState(rx.State):
    tab: str = "agenda"

    # ── Agenda ──────────────────────────────────────────────────────────
    filtro_estado: str = ""
    filtro_periodo: str = ""
    filtro_texto: str = ""
    registros: list[dict] = []
    cargando: bool = False
    error: str = ""
    msg: str = ""

    editando_id: int = 0
    form: dict = {}
    mostrar_form: bool = False
    cedula_aviso: str = ""

    @rx.event
    def set_tab(self, v: str):
        self.tab = v
        if v == "atencion":
            return BitacoraState.cargar_atenciones
        if v == "reportes":
            return BitacoraState.cargar_reportes
        return None

    @rx.var
    def periodos(self) -> list[str]:
        return ["(todos)", *bitacora.periodos_recientes()]

    @rx.event
    def set_filtro_texto(self, v: str):
        self.filtro_texto = v

    @rx.event
    def set_filtro_estado(self, v: str):
        self.filtro_estado = "" if v == "(todos)" else v

    @rx.event
    def set_filtro_periodo(self, v: str):
        self.filtro_periodo = "" if v == "(todos)" else v

    @rx.event
    async def cargar(self):
        self.cargando = True
        self.error = ""
        yield
        try:
            self.registros = await asyncio.to_thread(
                bitacora.listar, self.filtro_estado, self.filtro_texto, self.filtro_periodo
            )
        except Exception as e:  # noqa: BLE001
            self.error = f"No se pudo cargar (¿hay conexión?): {e}"
        self.cargando = False

    @rx.event
    def nuevo(self):
        self.editando_id = 0
        self.form = {c: "" for c in CAMPOS}
        self.form["estado"] = "PENDIENTE"
        self.form["forma_pago"] = "EFECTIVO"
        self.form["periodo"] = bitacora.periodo_actual()
        self.form["fecha_firma_acuerdo"] = dt.date.today().strftime("%Y-%m-%d")
        self.form["hora"] = "15H30 PM"
        self.form["qap"] = ""
        self.mostrar_form = True
        self.cedula_aviso = ""
        self.msg = ""

    @rx.event
    def editar(self, reg: dict):
        self.editando_id = reg.get("id", 0)
        self.form = {c: ("" if reg.get(c) in (None, False) else str(reg.get(c))) for c in CAMPOS}
        self.form["qap"] = "1" if reg.get("qap") else ""
        self.mostrar_form = True
        self.cedula_aviso = ""
        self.msg = ""

    @rx.event
    def cerrar_form(self):
        self.mostrar_form = False

    @rx.event
    def set_campo(self, campo: str, v: str):
        self.form[campo] = v
        if campo == "cedula":
            self.cedula_aviso = (
                "" if not v.strip() or bitacora.cedula_es_valida(v)
                else "La cédula no pasa la validación ecuatoriana."
            )

    @rx.event
    def toggle_qap(self):
        self.form["qap"] = "" if self.form.get("qap") else "1"

    @rx.event
    async def generar_en_sistema(self):
        auth = await self.get_state(AuthState)
        fsal = self.form.get("fecha_salida", "")
        if not bitacora.fecha_iso(fsal):
            self.msg = "Indica primero la fecha de salida."
            return
        self.form["en_sistema"] = bitacora.texto_en_sistema(
            auth.username, fsal, self.form.get("observacion", "")
        )

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

    # ── Bitácora de Atención Personal ──────────────────────────────────
    at_texto: str = ""
    atenciones: list[dict] = []
    at_cargando: bool = False
    at_motivos: list[str] = []
    at_form: dict = {
        "apellidos_nombres": "", "cedula": "", "empleado_cod": "",
        "motivo": "", "observacion": "", "fecha": "", "hora": "",
    }
    at_msg: str = ""

    @rx.event
    async def cargar_atenciones(self):
        self.at_cargando = True
        yield
        try:
            if not self.at_motivos:
                self.at_motivos = await asyncio.to_thread(bitacora.motivos_activos)
            self.atenciones = await asyncio.to_thread(bitacora.atenciones, self.at_texto)
        except Exception as e:  # noqa: BLE001
            self.at_msg = f"No se pudo cargar: {e}"
        self.at_cargando = False

    @rx.event
    def set_at_texto(self, v: str):
        self.at_texto = v

    @rx.event
    def nueva_atencion(self):
        self.at_form = {
            "apellidos_nombres": "", "cedula": "", "empleado_cod": "",
            "motivo": self.at_motivos[0] if self.at_motivos else "OTRO",
            "observacion": "",
            "fecha": dt.date.today().strftime("%Y-%m-%d"),
            "hora": dt.datetime.now().strftime("%H:%M"),
        }
        self.at_msg = ""

    @rx.event
    def set_at_campo(self, campo: str, v: str):
        self.at_form[campo] = v

    @rx.event
    async def guardar_atencion(self):
        auth = await self.get_state(AuthState)
        if "bitacora:crear" not in auth.permisos_flat:
            self.at_msg = "Sin permiso."
            return
        f = dict(self.at_form)
        try:
            await asyncio.to_thread(
                bitacora.registrar_atencion,
                apellidos_nombres=f.get("apellidos_nombres", ""),
                cedula=f.get("cedula", ""),
                motivo=f.get("motivo", ""),
                observacion=f.get("observacion", ""),
                fecha=f.get("fecha", ""),
                hora=f.get("hora", ""),
                empleado_cod=f.get("empleado_cod", ""),
                usuario=auth.username,
                roles=set(auth.roles),
            )
            self.at_msg = "Atención registrada."
            self.at_form = {}
            await self.cargar_atenciones()
        except Exception as e:  # noqa: BLE001
            self.at_msg = f"Error: {e}"

    @rx.event
    async def eliminar_atencion(self, aid: int):
        auth = await self.get_state(AuthState)
        if "admin" not in auth.roles:
            self.at_msg = "Solo un administrador puede borrar una atención."
            return
        await asyncio.to_thread(
            bitacora.eliminar_atencion, aid, usuario=auth.username, roles=set(auth.roles)
        )
        await self.cargar_atenciones()

    # ── Reportes ──────────────────────────────────────────────────────
    rep_estado: str = ""
    rep_periodo: str = ""
    resumen: dict = {"total": 0, "horas_suspension": 0.0, "con_qap": 0, "por_estado": {}}
    historial: list[dict] = []
    rep_cargando: bool = False

    @rx.event
    def set_rep_estado(self, v: str):
        self.rep_estado = "" if v == "(todos)" else v

    @rx.event
    def set_rep_periodo(self, v: str):
        self.rep_periodo = "" if v == "(todos)" else v

    @rx.event
    async def cargar_reportes(self):
        self.rep_cargando = True
        yield
        try:
            self.resumen = await asyncio.to_thread(
                bitacora.resumen, self.rep_estado, self.rep_periodo
            )
            self.historial = await asyncio.to_thread(bitacora.historial_reciente)
        except Exception as e:  # noqa: BLE001
            self.error = f"No se pudo cargar el reporte: {e}"
        self.rep_cargando = False

    @rx.event
    async def exportar_excel(self):
        estado, periodo = self.rep_estado, self.rep_periodo

        def _fn() -> bytes:
            from core.excel.bitacora_builders import reporte_agenda_xlsx

            filas = bitacora.filas_reporte(estado, periodo)
            return reporte_agenda_xlsx(filas)

        data = await asyncio.to_thread(_fn)
        return rx.download(data=data, filename="agenda_liquidacion.xlsx")
