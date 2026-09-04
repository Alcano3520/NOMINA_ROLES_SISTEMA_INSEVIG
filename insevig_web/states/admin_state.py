"""Estado del módulo Administración: usuarios, roles, auditoría, config."""

from __future__ import annotations

import asyncio

import reflex as rx
import sqlmodel

from core.db import appdb
from core.db.models import AuditLog, User, UserRole
from insevig_web import auth
from insevig_web.states.auth_state import AuthState


class AdminState(rx.State):
    usuarios: list[dict] = []
    auditoria: list[dict] = []

    nu_username: str = ""
    nu_nombre: str = ""
    nu_clave: str = ""
    nu_rol: str = "consulta"
    msg: str = ""

    @rx.event
    async def cargar_usuarios(self):
        def _q():
            with appdb.session() as s:
                us = s.exec(sqlmodel.select(User)).all()
                roles: dict[int, list[str]] = {}
                for ur in s.exec(sqlmodel.select(UserRole)).all():
                    roles.setdefault(ur.user_id, []).append(ur.role)
                return [
                    {
                        "id": u.id,
                        "username": u.username,
                        "nombre": u.full_name,
                        "activo": u.is_active,
                        "roles": ", ".join(sorted(roles.get(u.id, []))),
                        "ultimo": str(u.last_login or "")[:19],
                    }
                    for u in us
                ]

        self.usuarios = await asyncio.to_thread(_q)

    aud_usuario: str = ""
    aud_modulo: str = ""

    @rx.event
    def set_aud(self, campo: str, v: str):
        setattr(self, f"aud_{campo}", v)

    @rx.event
    async def cargar_auditoria(self):
        f_user, f_mod = self.aud_usuario.strip(), self.aud_modulo.strip()

        def _q():
            with appdb.session() as s:
                q = sqlmodel.select(AuditLog).order_by(sqlmodel.col(AuditLog.ts).desc())
                if f_user:
                    q = q.where(sqlmodel.col(AuditLog.username).ilike(f"%{f_user}%"))
                if f_mod:
                    q = q.where(AuditLog.module == f_mod)
                filas = s.exec(q.limit(200)).all()
                return [
                    {
                        "ts": str(a.ts)[:19],
                        "usuario": a.username,
                        "modulo": a.module,
                        "accion": a.action,
                        "objetivo": f"{a.target_table} {a.target_key}".strip(),
                        "status": a.status,
                    }
                    for a in filas
                ]

        self.auditoria = await asyncio.to_thread(_q)

    @rx.event
    def set_nu(self, campo: str, v: str):
        setattr(self, f"nu_{campo}", v)

    @rx.event
    async def crear_usuario(self):
        actual = await self.get_state(AuthState)
        if "admin" not in actual.roles:
            self.msg = "Solo admin puede crear usuarios."
            return
        if not self.nu_username.strip() or not self.nu_clave:
            self.msg = "Usuario y clave son obligatorios."
            return
        u, nombre, clave, rol = self.nu_username.strip(), self.nu_nombre.strip(), self.nu_clave, self.nu_rol

        def _crear():
            with appdb.session() as s:
                if s.exec(sqlmodel.select(User).where(User.username == u)).first():
                    return "ya existe"
                nuevo = User(username=u, full_name=nombre or u, password_hash=auth.hash_password(clave))
                s.add(nuevo)
                s.commit()
                s.refresh(nuevo)
                s.add(UserRole(user_id=nuevo.id, role=rol))
                s.commit()
                return "ok"

        r = await asyncio.to_thread(_crear)
        self.msg = "Usuario creado." if r == "ok" else "Ese usuario ya existe."
        self.nu_username = self.nu_nombre = self.nu_clave = ""
        await self.cargar_usuarios()

    @rx.event
    async def toggle_activo(self, user_id: int):
        def _t():
            with appdb.session() as s:
                u = s.get(User, user_id)
                if u:
                    u.is_active = not u.is_active
                    s.add(u)
                    s.commit()

        await asyncio.to_thread(_t)
        await self.cargar_usuarios()

    @rx.var
    def matriz_permisos(self) -> list[dict]:
        filas = []
        for rol, modulos in auth.PERMISOS_POR_DEFECTO.items():
            for modulo, acciones in modulos.items():
                filas.append({"rol": rol, "modulo": modulo, "acciones": ", ".join(sorted(acciones))})
        return filas
