"""Siembra inicial: tablas + permisos por defecto + usuario admin.

    python -m insevig_web.seed                 # admin / admin  (¡cambiar!)
    python -m insevig_web.seed --user jperez --clave 'xxx' --nombre 'Juan Pérez' --rol editor
"""

from __future__ import annotations

import argparse

import sqlmodel

from core.db import appdb
from insevig_web import auth
from insevig_web.models import RolePermission, User, UserRole


def sembrar_permisos(s: sqlmodel.Session) -> None:
    existentes = {
        (rp.role, rp.module, rp.action)
        for rp in s.exec(sqlmodel.select(RolePermission)).all()
    }
    for rol, modulos in auth.PERMISOS_POR_DEFECTO.items():
        for modulo, acciones in modulos.items():
            for accion in acciones:
                if (rol, modulo, accion) not in existentes:
                    s.add(RolePermission(role=rol, module=modulo, action=accion, allowed=True))
    s.commit()


def crear_usuario(s: sqlmodel.Session, username: str, clave: str, nombre: str, rol: str) -> None:
    u = s.exec(sqlmodel.select(User).where(User.username == username)).one_or_none()
    if u is None:
        u = User(username=username, full_name=nombre, password_hash=auth.hash_password(clave))
        s.add(u)
        s.commit()
        s.refresh(u)
        print(f"Usuario creado: {username}")
    else:
        print(f"Usuario ya existe: {username}")
    if not s.exec(
        sqlmodel.select(UserRole).where(UserRole.user_id == u.id, UserRole.role == rol)
    ).first():
        s.add(UserRole(user_id=u.id, role=rol))
        s.commit()
        print(f"  rol asignado: {rol}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--user", default="admin")
    p.add_argument("--clave", default="admin")
    p.add_argument("--nombre", default="Administrador")
    p.add_argument("--rol", default="admin", choices=auth.ROLES)
    args = p.parse_args()

    appdb.crear_tablas()
    with appdb.session() as s:
        sembrar_permisos(s)
        crear_usuario(s, args.user, args.clave, args.nombre, args.rol)
    print("Listo.")


if __name__ == "__main__":
    main()
