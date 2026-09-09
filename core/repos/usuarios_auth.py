"""Carga masiva de usuarios de Supabase Auth (proyecto SANCIONES) — BACKEND.

Trasplante de `sistema_sanciones_RRHH/nucleo_modular/carga_usuarios.py`
(origen legado: `carga maciva usuarios6.0.py`, clase
`SupabaseUserCreatorEnhanced`). Administra los logins de los **supervisores de
la app Flutter de sanciones** (Auth Admin API + tabla `profiles` del proyecto
`syxzopyevfuwymmltbwn`). NO son empleados de nómina ni `usuarios_rrhh`.

- El transporte `requests` + `/auth/v1/admin/users` del legado se reemplaza por
  el SDK (`client.auth.admin.*`) + `client.table("profiles")`.
- El **cliente se inyecta** (`cliente=`) o se resuelve con
  `get_client_sanciones(service=True)` — la SERVICE key SOLO vive en `core/`,
  nunca se serializa a un `rx.State` ni llega al navegador.
- **Contraseñas generadas:** se devuelven en el resultado de cada operación para
  que el operador las copie/entregue en el momento; **NO se escriben a disco ni
  a la BD** (el legado las volcaba a un `.txt` — eso NO se replica). La auditoría
  (`core.audit`) registra quién creó/reseteó qué cuenta, nunca el secreto.

Reglas de negocio (validación, mapeo de error_code 422, upsert de profiles) =
igual que el legado.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from typing import Any

from core.audit.writer import registrar_evento

log = logging.getLogger(__name__)

_LOWER = "abcdefghijklmnopqrstuvwxyz"
_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS = "0123456789"
_SYMBOLS = "!@#$%&*"


def _cli(cliente: Any | None) -> Any:
    if cliente is not None:
        return cliente
    from core.db.supabase_client import get_client_sanciones

    return get_client_sanciones(service=True)


# ── contraseñas ────────────────────────────────────────────────────────────


def generar_password_segura(length: int = 12) -> str:
    """Contraseña con al menos 1 minúscula, 1 mayúscula, 1 dígito y 1 símbolo
    (`!@#$%&*`). Puerto de `generar_password_segura` (con `secrets` en vez de
    `random`, que es lo correcto para credenciales).
    """
    length = max(8, length)
    base = [
        secrets.choice(_LOWER), secrets.choice(_UPPER),
        secrets.choice(_DIGITS), secrets.choice(_SYMBOLS),
    ]
    alfabeto = _LOWER + _UPPER + _DIGITS + _SYMBOLS
    base += [secrets.choice(alfabeto) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(base)
    return "".join(base)


def validar_password(password: str) -> tuple[bool, str]:
    """Reglas mínimas de Supabase Auth: 6-72 caracteres. Puerto exacto."""
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres"
    if len(password) > 72:
        return False, "La contraseña no puede tener más de 72 caracteres"
    return True, "Contraseña válida"


# ── lecturas ───────────────────────────────────────────────────────────────


def _user_dict(u: Any) -> dict:
    g = u.get if isinstance(u, dict) else (lambda k, d=None: getattr(u, k, d))
    return {
        "id": g("id"), "email": g("email"),
        "created_at": str(g("created_at") or "")[:19],
        "last_sign_in_at": str(g("last_sign_in_at") or "")[:19],
        "confirmed": bool(g("email_confirmed_at") or g("confirmed_at")),
    }


def listar_usuarios(per_page: int = 1000, *, cliente: Any | None = None) -> list[dict]:
    """Usuarios de Auth (primera página) mezclados con su fila de `profiles`."""
    cli = _cli(cliente)
    try:
        resp = cli.auth.admin.list_users(page=1, per_page=per_page)
        users = resp if isinstance(resp, list) else getattr(resp, "users", []) or []
    except Exception as e:  # noqa: BLE001
        log.error("listar_usuarios: %s", e)
        return []
    perfiles: dict[str, dict] = {}
    try:
        for p in cli.table("profiles").select("*").execute().data or []:
            perfiles[str(p.get("id"))] = p
    except Exception as e:  # noqa: BLE001
        log.warning("listar_usuarios/profiles: %s", e)
    salida = []
    for u in users:
        d = _user_dict(u)
        p = perfiles.get(str(d["id"]), {})
        d["nombre"] = p.get("full_name", "")
        d["rol"] = p.get("role", "")
        d["departamento"] = p.get("department", "")
        d["activo"] = p.get("is_active", True)
        salida.append(d)
    return salida


def buscar_usuario(email: str, *, cliente: Any | None = None) -> dict | None:
    """Busca por email en Auth + `profiles`. Puerto de `buscar_usuario_auth` +
    `buscar_usuario_profiles` (comparación case-insensitive).
    """
    email_l = (email or "").strip().lower()
    if not email_l:
        return None
    for u in listar_usuarios(cliente=cliente):
        if (u.get("email") or "").lower() == email_l:
            return u
    return None


# ── escrituras ─────────────────────────────────────────────────────────────


@dataclass
class ResultadoUsuario:
    email: str
    ok: bool
    accion: str = ""              # CREADO | ACTUALIZADO | ERROR
    user_id: str = ""
    password: str = ""            # solo si se generó — NO se persiste
    detalle: str = ""


def _map_422(err: Any) -> str:
    code = getattr(err, "code", "") or ""
    msg = getattr(err, "message", "") or str(err)
    if "weak_password" in f"{code}{msg}":
        return f"Contraseña débil: {msg}. Usa al menos 6 caracteres."
    if "email_address_invalid" in f"{code}{msg}":
        return f"Email inválido: {msg}"
    if "signup_disabled" in f"{code}{msg}":
        return "El registro está deshabilitado en Supabase"
    return f"Error de validación: {msg}"


def crear_usuario(
    usuario: dict, *, actualizar_si_existe: bool = False,
    usuario_operador: str = "", cliente: Any | None = None,
) -> ResultadoUsuario:
    """Crea un usuario en Auth (`email_confirm=True`) + su fila en `profiles`.
    `usuario` requiere email, password, nombre, rol; opcional departamento.
    Si Auth crea pero `profiles` falla → ok con detalle "(sin perfil)" (igual que
    el legado). Puerto de `crear_o_actualizar_usuario`.
    """
    email = (usuario.get("email") or "").strip()
    pwd = usuario.get("password") or ""
    valido, msg = validar_password(pwd)
    if not valido:
        return ResultadoUsuario(email, False, "ERROR", detalle=f"Error de contraseña: {msg}")

    cli = _cli(cliente)
    existente = buscar_usuario(email, cliente=cli)
    if existente and not actualizar_si_existe:
        return ResultadoUsuario(email, False, "ERROR", user_id=existente["id"],
                                detalle="El usuario ya existe (marcá 'actualizar si existe').")

    try:
        if existente:
            cli.auth.admin.update_user_by_id(existente["id"], {"password": pwd})
            user_id = existente["id"]
            accion = "ACTUALIZADO"
        else:
            resp = cli.auth.admin.create_user({
                "email": email, "password": pwd, "email_confirm": True,
            })
            user_id = getattr(getattr(resp, "user", None), "id", None) or resp.get("id")  # type: ignore[union-attr]
            accion = "CREADO"
    except Exception as e:  # noqa: BLE001
        return ResultadoUsuario(email, False, "ERROR", detalle=_map_422(e))

    perfil = {
        "id": user_id, "email": email, "full_name": usuario.get("nombre"),
        "role": usuario.get("rol"), "department": usuario.get("departamento") or None,
        "is_active": True,
    }
    detalle = ""
    try:
        cli.table("profiles").upsert(perfil).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("profiles upsert %s: %s", user_id, e)
        detalle = "(sin perfil)"

    registrar_evento("carga_usuarios", accion.lower(), usuario=usuario_operador,
                     target_table="auth.users", target_key=str(user_id))
    return ResultadoUsuario(email, True, accion, user_id=str(user_id),
                            password=pwd if usuario.get("_password_generada") else "",
                            detalle=detalle)


def resetear_password(
    user_id: str, nueva_password: str, *, usuario_operador: str = "", cliente: Any | None = None,
) -> tuple[bool, str]:
    """PUT de la contraseña de un usuario de Auth. Puerto de `resetear_password`."""
    valido, msg = validar_password(nueva_password)
    if not valido:
        return False, f"Contraseña inválida: {msg}"
    try:
        _cli(cliente).auth.admin.update_user_by_id(user_id, {"password": nueva_password})
    except Exception as e:  # noqa: BLE001
        return False, _map_422(e)
    registrar_evento("carga_usuarios", "reset_password", usuario=usuario_operador,
                     target_table="auth.users", target_key=str(user_id))
    return True, "Contraseña actualizada exitosamente"


def probar_conexion(*, cliente: Any | None = None) -> bool:
    """True si la SERVICE key puede listar usuarios de Auth."""
    try:
        _cli(cliente).auth.admin.list_users(page=1, per_page=1)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("probar_conexion: %s", e)
        return False


# ── carga masiva ───────────────────────────────────────────────────────────


def parsear_pegado(texto: str, sep: str | None = None) -> list[dict]:
    """Texto pegado → filas {email, nombre, rol, departamento, password}.
    Autodetecta TAB/`;`/`|`/`,`. Filas sin `@` en la 1ª columna se descartan.
    Puerto de `parsear_usuarios_pegado`.
    """
    filas: list[dict] = []
    for linea in (texto or "").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        s = sep
        if s is None:
            for cand in ("\t", ";", "|", ","):
                if cand in linea:
                    s = cand
                    break
        partes = [p.strip() for p in linea.split(s or "\t")]
        if not partes or "@" not in partes[0]:
            continue
        filas.append({
            "email": partes[0],
            "nombre": partes[1] if len(partes) > 1 else "",
            "rol": partes[2] if len(partes) > 2 else "",
            "departamento": partes[3] if len(partes) > 3 else "",
            "password": partes[4] if len(partes) > 4 else "",
        })
    return filas


@dataclass
class ResumenCarga:
    creados: int = 0
    actualizados: int = 0
    errores: int = 0
    resultados: list[ResultadoUsuario] = field(default_factory=list)


def cargar_masivo(
    filas: list[dict], *, generar_passwords: bool = True, actualizar_si_existe: bool = False,
    dry_run: bool = True, usuario_operador: str = "", cliente: Any | None = None,
    callback_progreso=None,
) -> ResumenCarga:
    """Procesa una lista de filas (de `parsear_pegado`). `dry_run=True` solo
    valida y reporta qué se haría. Puerto de `procesar_datos` / `procesar_usuarios`.
    """
    res = ResumenCarga()
    cli = None if dry_run else _cli(cliente)
    for i, fila in enumerate(filas, 1):
        email = (fila.get("email") or "").strip()
        pwd = fila.get("password") or ""
        generada = False
        if not pwd and generar_passwords:
            pwd = generar_password_segura()
            generada = True
        valido, msg = validar_password(pwd) if pwd else (False, "sin contraseña")
        if not email or "@" not in email:
            res.errores += 1
            res.resultados.append(ResultadoUsuario(email, False, "ERROR", detalle="email inválido"))
            continue
        if not valido:
            res.errores += 1
            res.resultados.append(ResultadoUsuario(email, False, "ERROR", detalle=msg))
            continue
        if dry_run:
            res.resultados.append(ResultadoUsuario(
                email, True, "CREARÍA", password=pwd if generada else "",
                detalle=f"rol={fila.get('rol', '')}",
            ))
            res.creados += 1
        else:
            r = crear_usuario(
                {**fila, "password": pwd, "_password_generada": generada},
                actualizar_si_existe=actualizar_si_existe,
                usuario_operador=usuario_operador, cliente=cli,
            )
            res.resultados.append(r)
            if not r.ok:
                res.errores += 1
            elif r.accion == "ACTUALIZADO":
                res.actualizados += 1
            else:
                res.creados += 1
        if callback_progreso:
            callback_progreso(f"{i}/{len(filas)}")
    return res
