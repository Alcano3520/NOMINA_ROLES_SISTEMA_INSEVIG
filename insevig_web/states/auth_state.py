"""Estado de autenticación y autorización. Compartido por toda la app."""

from __future__ import annotations

import datetime as dt

import reflex as rx
import sqlmodel

from core.db import appdb
from insevig_web import auth
from insevig_web.models import User, UserRole


def _iter_permisos(roles: set[str]):
    for r in roles:
        yield from auth.PERMISOS_POR_DEFECTO.get(r, {}).items()


class AuthState(rx.State):
    # Token de sesión firmado, persistido en cookie.
    sesion: str = rx.Cookie(name="insevig_sesion", max_age=60 * 60 * 12)

    _user_id: int | None = None
    username: str = ""
    nombre: str = ""
    roles: list[str] = []
    error_login: str = ""

    @rx.var
    def autenticado(self) -> bool:
        return bool(self.username)

    @rx.var
    def es_admin(self) -> bool:
        return "admin" in self.roles

    @rx.var(cache=True)
    def permisos_flat(self) -> list[str]:
        """Permisos del usuario como ``"modulo:accion"`` (para chequeo reactivo en UI)."""
        roles = set(self.roles)
        out: set[str] = set()
        for modulo, acciones in _iter_permisos(roles):
            out.update(f"{modulo}:{a}" for a in acciones)
        return sorted(out)

    @rx.event
    def cargar_sesion(self):
        """on_load global: rehidrata el usuario desde la cookie firmada."""
        if self.username:
            return
        uid = auth.leer_sesion(self.sesion)
        if uid is None:
            return
        with appdb.session() as s:
            user = s.get(User, uid)
            if not user or not user.is_active:
                self.sesion = ""
                return
            roles = s.exec(
                sqlmodel.select(UserRole.role).where(UserRole.user_id == uid)
            ).all()
        self._user_id = uid
        self.username = user.username
        self.nombre = user.full_name or user.username
        self.roles = list(roles)

    @rx.event
    def login(self, form_data: dict):
        usuario = (form_data.get("usuario") or "").strip()
        clave = form_data.get("clave") or ""
        self.error_login = ""
        with appdb.session() as s:
            user = s.exec(
                sqlmodel.select(User).where(User.username == usuario)
            ).one_or_none()
            if not user or not user.is_active or not auth.verify_password(
                clave, user.password_hash
            ):
                self.error_login = "Usuario o contraseña incorrectos."
                return
            user.last_login = dt.datetime.now(dt.UTC)
            s.add(user)
            s.commit()
            s.refresh(user)
            roles = s.exec(
                sqlmodel.select(UserRole.role).where(UserRole.user_id == user.id)
            ).all()
        self._user_id = user.id
        self.username = user.username
        self.nombre = user.full_name or user.username
        self.roles = list(roles)
        self.sesion = auth.firmar_sesion(user.id)
        return rx.redirect("/")

    @rx.event
    def logout(self):
        self._user_id = None
        self.username = ""
        self.nombre = ""
        self.roles = []
        self.sesion = ""
        return rx.redirect("/login")

    # ── Cambio de contraseña (autoservicio) ───────────────────────────
    clave_msg: str = ""

    @rx.event
    def cambiar_mi_clave(self, form_data: dict):
        self.clave_msg = ""
        actual = form_data.get("actual") or ""
        nueva = form_data.get("nueva") or ""
        conf = form_data.get("confirmar") or ""
        if len(nueva) < 6:
            self.clave_msg = "La nueva contraseña debe tener al menos 6 caracteres."
            return
        if nueva != conf:
            self.clave_msg = "La confirmación no coincide."
            return
        if self._user_id is None:
            self.clave_msg = "Sesión no válida."
            return
        with appdb.session() as s:
            user = s.get(User, self._user_id)
            if not user or not auth.verify_password(actual, user.password_hash):
                self.clave_msg = "La contraseña actual es incorrecta."
                return
            user.password_hash = auth.hash_password(nueva)
            s.add(user)
            s.commit()
        self.clave_msg = "Contraseña actualizada."
        return rx.toast.success("Contraseña actualizada.")
