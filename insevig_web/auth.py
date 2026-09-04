"""Autenticación local + matriz de permisos.

★ CONGELADO. Los módulos consumen `puede(...)` / `AuthState.can(...)`, no lo editan.
"""

from __future__ import annotations

import base64
import hashlib

import bcrypt

from core.config import get_settings

ROLES = ("admin", "editor", "consulta")

# Acciones posibles sobre un módulo.
ACCIONES = (
    "ver",
    "exportar",
    "crear",
    "editar",
    "eliminar",
    "cargar_masivo",
    "generar_pdf",
    "enviar_email",
    "registrar_rpingdes",
)

# Permisos por defecto (los siembra seed.py en RolePermission; admin puede editarlos).
_TODOS_MODULOS = (
    "reportes", "prestamos", "observaciones", "empleados", "roles",
    "registrador", "bitacora", "liquidaciones", "admin",
)

PERMISOS_POR_DEFECTO: dict[str, dict[str, set[str]]] = {
    "admin": {m: set(ACCIONES) for m in _TODOS_MODULOS},
    "editor": {
        "reportes": {"ver", "exportar"},
        "prestamos": {"ver", "exportar"},
        "observaciones": {"ver", "exportar", "crear", "editar"},
        "empleados": {"ver", "exportar", "crear", "editar", "cargar_masivo"},
        "roles": {"ver", "generar_pdf", "enviar_email"},
        "registrador": {"ver", "registrar_rpingdes"},
        "bitacora": {"ver", "crear", "editar"},
        "liquidaciones": {"ver", "exportar", "generar_pdf", "editar"},
    },
    "consulta": {
        "reportes": {"ver", "exportar"},
        "prestamos": {"ver"},
        "observaciones": {"ver"},
        "empleados": {"ver"},
        "roles": {"ver"},
        "registrador": {"ver"},
        "bitacora": {"ver"},
        "liquidaciones": {"ver", "exportar"},
    },
}


def _pre(clave: str) -> bytes:
    # sha256+base64 evita el límite de 72 bytes de bcrypt sin truncar.
    return base64.b64encode(hashlib.sha256(clave.encode("utf-8")).digest())


def hash_password(clave: str) -> str:
    return bcrypt.hashpw(_pre(clave), bcrypt.gensalt()).decode("ascii")


def verify_password(clave: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(_pre(clave), hash_.encode("ascii"))
    except (ValueError, TypeError):
        return False


def puede(roles: set[str], modulo: str, accion: str) -> bool:
    """True si alguno de los roles permite `accion` sobre `modulo`."""
    return any(
        accion in PERMISOS_POR_DEFECTO.get(r, {}).get(modulo, set()) for r in roles
    )


def firmar_sesion(user_id: int) -> str:
    from itsdangerous import URLSafeSerializer

    return URLSafeSerializer(get_settings().secret_key, salt="sesion").dumps(user_id)


def leer_sesion(token: str) -> int | None:
    from itsdangerous import BadSignature, URLSafeSerializer

    if not token:
        return None
    try:
        return URLSafeSerializer(get_settings().secret_key, salt="sesion").loads(token)
    except BadSignature:
        return None
