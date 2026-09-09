"""Estado del módulo CARGA_USUARIOS — cuentas de Supabase Auth de los
supervisores de la app Flutter de sanciones (proyecto syxzopyevfuwymmltbwn).

SERVICE key: SOLO en `core/` — este state nunca la ve ni la envía al navegador.
Contraseñas generadas: se muestran una vez en pantalla para copiar; NO se
descargan a un archivo ni se guardan.
"""

from __future__ import annotations

import asyncio
import dataclasses

import reflex as rx

from core.repos import usuarios_auth as repo
from insevig_web.states.auth_state import AuthState

ROLES = ["supervisor", "gerencia", "rrhh", "admin"]


class CargaUsuariosState(rx.State):
    # ── individual ────────────────────────────────────────────────────
    ind_email: str = ""
    ind_nombre: str = ""
    ind_rol: str = "supervisor"
    ind_departamento: str = ""
    ind_password: str = ""
    ind_generar: bool = True
    ind_actualizar: bool = False
    ind_resultado: dict = {}
    ind_msg: str = ""

    @rx.event
    def set_ind_email(self, v: str):
        self.ind_email = v

    @rx.event
    def set_ind_nombre(self, v: str):
        self.ind_nombre = v

    @rx.event
    def set_ind_rol(self, v: str):
        self.ind_rol = v

    @rx.event
    def set_ind_departamento(self, v: str):
        self.ind_departamento = v

    @rx.event
    def set_ind_password(self, v: str):
        self.ind_password = v

    @rx.event
    def toggle_ind_generar(self, v: bool):
        self.ind_generar = bool(v)

    @rx.event
    def toggle_ind_actualizar(self, v: bool):
        self.ind_actualizar = bool(v)

    @rx.event
    def generar_ind_password(self):
        self.ind_password = repo.generar_password_segura()
        self.ind_generar = False

    @rx.event
    async def ind_verificar(self):
        self.ind_msg = ""
        u = await asyncio.to_thread(repo.buscar_usuario, self.ind_email)
        self.ind_msg = (
            f"Ya existe: {u['email']} · rol {u.get('rol') or '—'}" if u
            else "No existe en Auth — se puede crear."
        )

    @rx.event
    async def ind_crear(self):
        pwd = self.ind_password
        generada = False
        if not pwd and self.ind_generar:
            pwd = repo.generar_password_segura()
            generada = True
        auth = await self.get_state(AuthState)
        r = await asyncio.to_thread(
            repo.crear_usuario,
            {"email": self.ind_email, "nombre": self.ind_nombre, "rol": self.ind_rol,
             "departamento": self.ind_departamento, "password": pwd,
             "_password_generada": generada},
            actualizar_si_existe=self.ind_actualizar,
            usuario_operador=auth.username,
        )
        self.ind_resultado = dataclasses.asdict(r)
        self.ind_msg = r.detalle or ("OK" if r.ok else "Error")

    # ── listado ──────────────────────────────────────────────────────
    lst_usuarios: list[dict] = []
    lst_cargando: bool = False
    lst_filtro: str = ""

    @rx.event
    def set_lst_filtro(self, v: str):
        self.lst_filtro = v

    @rx.event
    async def lst_cargar(self):
        self.lst_cargando = True
        yield
        try:
            self.lst_usuarios = await asyncio.to_thread(repo.listar_usuarios)
        finally:
            self.lst_cargando = False

    @rx.var
    def lst_filtrados(self) -> list[dict]:
        f = self.lst_filtro.strip().lower()
        if not f:
            return self.lst_usuarios[:300]
        return [u for u in self.lst_usuarios
                if f in (u.get("email", "") + u.get("nombre", "")).lower()][:300]

    # ── reset ────────────────────────────────────────────────────────
    rst_email: str = ""
    rst_user: dict = {}
    rst_password: str = ""
    rst_msg: str = ""

    @rx.event
    def set_rst_email(self, v: str):
        self.rst_email = v

    @rx.event
    def set_rst_password(self, v: str):
        self.rst_password = v

    @rx.event
    def generar_rst_password(self):
        self.rst_password = repo.generar_password_segura()

    @rx.event
    async def rst_buscar(self):
        self.rst_msg = ""
        self.rst_user = {}
        u = await asyncio.to_thread(repo.buscar_usuario, self.rst_email)
        if u:
            self.rst_user = u
        else:
            self.rst_msg = "No se encontró ese email en Auth."

    @rx.event
    async def rst_resetear(self):
        if not self.rst_user.get("id"):
            self.rst_msg = "Buscá primero el usuario."
            return
        pwd = self.rst_password or repo.generar_password_segura()
        self.rst_password = pwd
        auth = await self.get_state(AuthState)
        ok, msg = await asyncio.to_thread(
            repo.resetear_password, self.rst_user["id"], pwd, usuario_operador=auth.username,
        )
        self.rst_msg = msg

    # ── masivo ───────────────────────────────────────────────────────
    mas_pegado: str = ""
    mas_generar: bool = True
    mas_actualizar: bool = False
    mas_filas: list[dict] = []
    mas_resultados: list[dict] = []
    mas_resumen: dict = {}
    mas_procesando: bool = False

    @rx.event
    def set_mas_pegado(self, v: str):
        self.mas_pegado = v

    @rx.event
    def toggle_mas_generar(self, v: bool):
        self.mas_generar = bool(v)

    @rx.event
    def toggle_mas_actualizar(self, v: bool):
        self.mas_actualizar = bool(v)

    @rx.event
    def mas_parsear(self):
        self.mas_filas = repo.parsear_pegado(self.mas_pegado)
        self.mas_resultados = []
        self.mas_resumen = {}

    @rx.event
    async def mas_dry_run(self):
        r = await asyncio.to_thread(
            repo.cargar_masivo, self.mas_filas,
            generar_passwords=self.mas_generar, actualizar_si_existe=self.mas_actualizar,
            dry_run=True,
        )
        self.mas_resultados = [dataclasses.asdict(x) for x in r.resultados]
        self.mas_resumen = {"creados": r.creados, "actualizados": r.actualizados,
                            "errores": r.errores, "dry_run": True}

    @rx.event
    async def mas_ejecutar(self):
        self.mas_procesando = True
        yield
        auth = await self.get_state(AuthState)
        try:
            r = await asyncio.to_thread(
                repo.cargar_masivo, self.mas_filas,
                generar_passwords=self.mas_generar, actualizar_si_existe=self.mas_actualizar,
                dry_run=False, usuario_operador=auth.username,
            )
            self.mas_resultados = [dataclasses.asdict(x) for x in r.resultados]
            self.mas_resumen = {"creados": r.creados, "actualizados": r.actualizados,
                                "errores": r.errores, "dry_run": False}
        finally:
            self.mas_procesando = False

    @rx.event
    def mas_limpiar(self):
        self.mas_pegado = ""
        self.mas_filas = []
        self.mas_resultados = []
        self.mas_resumen = {}
