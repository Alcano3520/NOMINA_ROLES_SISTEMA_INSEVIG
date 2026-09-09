"""Catálogos y constantes del dominio de sanciones disciplinarias.

Trasplante verbatim de `sistema_sanciones_RRHH/nucleo_modular/catalogos.py`.
Sin credenciales, sin I/O.
"""

from __future__ import annotations

# Categorías de tipos de sanción (usado por `categorizar_sanciones`).
CATEGORIAS: dict[str, list[str]] = {
    "Faltas y Permisos": ["FALTA", "PERMISO"],
    "Horas y Franco": ["HORAS EXTRAS", "FRANCO TRABAJADO"],
    "Resto": [
        "ATRASO", "DORMIDO", "MALA URBANIDAD", "FALTA DE RESPETO",
        "MAL UNIFORMADO", "ABANDONO DE PUESTO", "MAL SERVICIO DE GUARDIA",
        "INCUMPLIMIENTO DE POLITICAS", "MAL USO DEL EQUIPO DE DOTACION",
    ],
}

# Estados de la columna `status` en Supabase `sanciones`.
ESTADOS_SANCION = {
    "BORRADOR": "borrador", "ENVIADO": "enviado",
    "APROBADO": "aprobado", "RECHAZADO": "rechazado",
}

ESTADOS_LEGIBLES = {
    "borrador": "Borrador",
    "enviado": "Pendiente de Aprobacion",
    "aprobado": "Aprobado por Gerencia",
    "rechazado": "Rechazado por Gerencia",
}

COLORES_ESTADO = {
    "borrador": "#616161", "enviado": "#f57c00",
    "aprobado": "#2e7d32", "rechazado": "#c62828",
}

# LEGADO: `ROLES_USUARIOS` solo lo usaban editor_sancion.py / utils_nuevo.py, ambos
# código muerto, y editor_sancion lo indexaba mal (por username en vez de por rol —
# bug #4 del README de nucleo_modular). Se conserva como referencia de "qué puede
# hacer cada rol"; el uso correcto es indexar por rol.
ROLES_USUARIOS = {
    "admin": {"puede_aprobar": True, "puede_procesar": True, "puede_crear": True,
              "puede_rechazar": True, "descripcion": "Administrador del sistema"},
    "gerencia": {"puede_aprobar": True, "puede_procesar": False, "puede_crear": False,
                 "puede_rechazar": True, "descripcion": "Gerencia - Solo aprobaciones"},
    "rrhh": {"puede_aprobar": False, "puede_procesar": True, "puede_crear": False,
             "puede_rechazar": False, "descripcion": "RRHH - Solo procesamiento"},
    "supervisor": {"puede_aprobar": True, "puede_procesar": True, "puede_crear": True,
                   "puede_rechazar": True, "descripcion": "Supervisor con acceso completo"},
}

MSG_LOGIN_ERROR = "Usuario o contraseña incorrectos"
MSG_CONEXION_ERROR = "Error de conexion con Supabase. Verifique su conexion."
MSG_CONCURRENCIA = "Sancion siendo procesada por otro usuario"
MSG_APROBADO = "Sancion aprobada por gerencia"
MSG_RECHAZADO = "Sancion rechazada por gerencia"
MSG_PROCESADO = "Procesado para nomina"

VALIDACIONES = {
    "motivo_rechazo_minimo": 15,
    "observaciones_maximo": 500,
    "sanciones_maximas_lote": 50,
    "timeout_validacion": 30,
    "reintentos_validacion": 2,
}
