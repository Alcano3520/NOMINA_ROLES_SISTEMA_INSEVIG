"""Sincronización de usuarios de INSEVIG_web hacia `usuarios_rrhh` (proyecto
Supabase SANCIONES, `syxzopyevfuwymmltbwn`) — BACKEND.

Pedido del usuario 2026-09-16 ("unificar usuarios"): esa tabla ya existe y ya
la usan otros 2 programas (`sistema_sanciones_RRHH` de escritorio,
`gestion_rrhh_parametrizacion`) como su propio login compartido — no es algo
que este proyecto creó, es una integración con algo preexistente.

Reglas de negocio acordadas explícitamente con el usuario (no asumidas):

1. **Solo de acá hacia adelante.** Las 9 cuentas que ya existían en
   `usuarios_rrhh` (incluida una literal `admin`, real y activa, de otro
   sistema) NUNCA se tocan. Solo se sincronizan usuarios creados en
   INSEVIG_web a partir de este cambio.
2. **Nunca pisar un usuario ajeno.** Si el `username` que se va a crear en
   INSEVIG_web ya existe en `usuarios_rrhh` (de antes, o de otro sistema),
   la sincronización se salta esa fila -- nunca hace UPDATE de algo que no
   creó. Se distingue "fila creada por esta sincronización" de "fila
   preexistente" con la columna `origen_sync` (`'insevig_web'` vs `NULL`),
   agregada a propósito para esto.
3. **Nunca rompe el uso local.** El login de INSEVIG_web sigue siendo 100%
   local (`app_user`, ver `insevig_web/auth.py` -- ★ CONGELADO, no se toca).
   Si Supabase no responde o no está configurado, todo esto falla en
   silencio (logueado) y la operación local igual se completa.
4. **Mismo formato de contraseña que ya usan los otros 2 programas**:
   SHA-256 sin sal (`hashlib.sha256(password.encode()).hexdigest()`) --
   confirmado leyendo `sistema_sanciones_RRHH/nucleo_modular/usuarios.py` y
   `gestion_rrhh_parametrizacion/api.py`. NO es bcrypt (lo que sí usa
   INSEVIG_web localmente) -- son dos hashes distintos de la MISMA
   contraseña en el mismo momento de creación/reset, cuando el texto plano
   todavía está en memoria (después de eso, el hash local no es reversible).
5. **Mapeo de rol**: `usuarios_rrhh.rol` tiene un CHECK que solo acepta
   `admin|rrhh|gerencia|supervisor`; INSEVIG_web usa `admin|editor|consulta`
   (y un usuario puede tener varios roles locales, `usuarios_rrhh.rol` es
   uno solo). Se usa el de mayor privilegio: `admin` si el usuario tiene rol
   `admin` localmente, si no `rrhh` (el genérico no-privilegiado más
   parecido a "personal de RRHH/nómina", que es lo que son los usuarios de
   esta app).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

log = logging.getLogger(__name__)

_ORIGEN = "insevig_web"
_TABLA = "usuarios_rrhh"


def _cli(cliente: Any | None) -> Any:
    if cliente is not None:
        return cliente
    from core.db.supabase_client import get_client_sanciones

    return get_client_sanciones(service=True)


def _hash(password_plano: str) -> str:
    """SHA-256 sin sal -- mismo formato que `sistema_sanciones_RRHH` y
    `gestion_rrhh_parametrizacion`. Deliberadamente NO bcrypt (ver docstring
    del módulo, punto 4)."""
    return hashlib.sha256(password_plano.encode()).hexdigest()


def mapear_rol(roles_locales: set[str] | list[str]) -> str:
    return "admin" if "admin" in roles_locales else "rrhh"


def sincronizar_creacion(
    username: str, password_plano: str, nombre: str, roles_locales: set[str] | list[str],
    *, cliente: Any | None = None,
) -> tuple[bool, str]:
    """Al crear un usuario nuevo en INSEVIG_web. Devuelve `(ok, detalle)` --
    `ok=False` NUNCA debe frenar la creación local, es solo para mostrarle
    al operador qué pasó."""
    try:
        cli = _cli(cliente)
        existente = (
            cli.table(_TABLA).select("id").eq("username", username).limit(1).execute().data
        )
        if existente:
            return False, (
                f"'{username}' ya existe en el sistema RRHH compartido (de otro sistema) -- "
                "no se sincronizó para no pisarlo."
            )
        cli.table(_TABLA).insert({
            "username": username,
            "password_hash": _hash(password_plano),
            "nombre": nombre or username,
            "rol": mapear_rol(roles_locales),
            "activo": True,
            "origen_sync": _ORIGEN,
        }).execute()
        return True, "Sincronizado con el sistema RRHH compartido."
    except Exception as e:  # noqa: BLE001 -- nunca debe frenar la creación local
        log.warning("No se pudo sincronizar creación de usuario %r a usuarios_rrhh: %s", username, e)
        return False, f"No se pudo sincronizar (sin conexión o Supabase no configurado): {e}"


def sincronizar_clave(username: str, password_plano: str, *, cliente: Any | None = None) -> tuple[bool, str]:
    """Al resetear/cambiar una clave. Solo actualiza si la fila fue creada
    por `sincronizar_creacion` (`origen_sync='insevig_web'`) -- nunca toca
    una cuenta preexistente de otro sistema."""
    try:
        cli = _cli(cliente)
        res = (
            cli.table(_TABLA).update({"password_hash": _hash(password_plano)})
            .eq("username", username).eq("origen_sync", _ORIGEN).execute()
        )
        if not res.data:
            return False, "No sincronizado (ese usuario no fue creado por esta app en el sistema compartido)."
        return True, "Clave actualizada también en el sistema RRHH compartido."
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo sincronizar clave de usuario %r a usuarios_rrhh: %s", username, e)
        return False, f"No se pudo sincronizar (sin conexión o Supabase no configurado): {e}"


def sincronizar_activo(username: str, activo: bool, *, cliente: Any | None = None) -> tuple[bool, str]:
    """Al activar/desactivar un usuario. Mismo resguardo que `sincronizar_clave`."""
    try:
        cli = _cli(cliente)
        res = (
            cli.table(_TABLA).update({"activo": activo})
            .eq("username", username).eq("origen_sync", _ORIGEN).execute()
        )
        if not res.data:
            return False, "No sincronizado (ese usuario no fue creado por esta app en el sistema compartido)."
        return True, "Estado actualizado también en el sistema RRHH compartido."
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo sincronizar estado de usuario %r a usuarios_rrhh: %s", username, e)
        return False, f"No se pudo sincronizar (sin conexión o Supabase no configurado): {e}"
