"""Estado del módulo Registrador (Fase 5, alcance acotado): BIESS + alta manual."""

from __future__ import annotations

import asyncio
import datetime as dt

import reflex as rx

from core.repos import registrador
from insevig_web.states.auth_state import AuthState


class RegistradorState(rx.State):
    periodo: str = ""
    # BIESS
    filas_biess: list[dict] = []  # {'cedula','valor'}
    avisos: list[str] = []
    movs: list[dict] = []  # {'empleado','cedula','valor','estado_biess'}
    dry: dict = {}
    resultado: str = ""
    error: str = ""

    # manual
    m_empleado: str = ""
    m_clase: str = "204"
    m_valor: str = ""
    m_concepto: str = ""

    @rx.event
    def on_load(self):
        if not self.periodo:
            self.periodo = dt.date.today().strftime("%Y-%m")

    @rx.event
    def set_periodo(self, v: str):
        self.periodo = v.strip()

    @rx.event
    async def subir_biess(self, files: list[rx.UploadFile]):
        if not files:
            return
        from core.excel.parsers import parse_biess_quirografarios

        datos = await files[0].read()
        filas, errores = parse_biess_quirografarios(datos)
        self.filas_biess = filas
        self.avisos = errores[:50]
        self.movs = []
        self.dry = {}
        self.resultado = ""

    @rx.event
    async def preparar(self):
        if not self.filas_biess:
            return
        periodo = self.periodo or dt.date.today().strftime("%Y-%m")
        filas = list(self.filas_biess)

        def _prep():
            movs, avisos = registrador.preparar_biess(filas, periodo)
            return (
                [
                    {"empleado": m.empleado, "cedula": "", "valor": m.valor, "estado_biess": m.estado_biess}
                    for m in movs
                ],
                avisos,
                registrador.postear(movs, usuario="", roles=set(), dry_run=True),
            )

        self.movs, avisos, self.dry = await asyncio.to_thread(_prep)
        self.avisos = avisos[:50]

    @rx.event
    async def postear(self):
        auth = await self.get_state(AuthState)
        if "registrador:registrar_rpingdes" not in auth.permisos_flat:
            self.error = "Sin permiso."
            return
        periodo = self.periodo or dt.date.today().strftime("%Y-%m")
        filas = list(self.filas_biess)
        usuario, roles = auth.username, set(auth.roles)
        self.error = ""

        def _post():
            movs, _ = registrador.preparar_biess(filas, periodo)
            return registrador.postear(movs, usuario=usuario, roles=roles, dry_run=False)

        try:
            res = await asyncio.to_thread(_post)
            self.resultado = (
                f"Insertados: {res['insertados']} · omitidos (dedupe): {res['omitidos_dedupe']} "
                f"· sin empleado: {res['sin_empleado']}"
            )
        except Exception as e:  # noqa: BLE001
            self.error = str(e)

    # ── Manual ────────────────────────────────────────────────────────────
    @rx.event
    def set_m(self, campo: str, v: str):
        setattr(self, f"m_{campo}", v)

    @rx.event
    async def registrar_manual(self):
        auth = await self.get_state(AuthState)
        if "registrador:registrar_rpingdes" not in auth.permisos_flat:
            self.error = "Sin permiso."
            return
        try:
            valor = float(self.m_valor)
            clase = int(self.m_clase)
        except ValueError:
            self.error = "Valor y clase deben ser numéricos."
            return
        periodo = self.periodo or dt.date.today().strftime("%Y-%m")
        mov = registrador.Movimiento(
            self.m_empleado.strip(), clase, round(valor, 2), self.m_concepto.strip() or "REGISTRO MANUAL", periodo
        )
        usuario, roles = auth.username, set(auth.roles)
        self.error = ""
        try:
            res = await asyncio.to_thread(
                registrador.postear, [mov], usuario=usuario, roles=roles, dry_run=False
            )
            self.resultado = f"Insertados: {res['insertados']} · omitidos: {res['omitidos_dedupe']}"
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
