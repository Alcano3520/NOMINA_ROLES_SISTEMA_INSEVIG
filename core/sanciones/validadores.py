"""Validación de datos de sanción y de transición de estado.

Trasplante verbatim de `sistema_sanciones_RRHH/nucleo_modular/validadores.py`
(consolida `EditorSancion.validar_datos` + `utils_nuevo.ValidadorSanciones`, ambos
código muerto en el legado — ver README §1-2). Sin I/O.
"""

from __future__ import annotations

from datetime import datetime

from core.sanciones import catalogos


def validar_datos_sancion(datos: dict) -> tuple[bool, list[str]]:
    """Valida los datos de una sanción antes de guardarla.

    Obligatorios: empleado_cod, empleado_nombre, puesto, agente, fecha, hora,
    tipo_sancion. `empleado_cod` int positivo. `tipo_sancion` en `CATEGORIAS`.
    `fecha` = YYYY-MM-DD. `observaciones` ≤ `VALIDACIONES['observaciones_maximo']`.
    Devuelve (es_valido, errores).
    """
    errores: list[str] = []

    requeridos = ["empleado_cod", "empleado_nombre", "puesto", "agente", "fecha", "hora", "tipo_sancion"]
    for campo in requeridos:
        if not datos.get(campo):
            errores.append(f"{campo.replace('_', ' ').title()} es requerido")

    if datos.get("empleado_cod"):
        try:
            if int(datos["empleado_cod"]) <= 0:
                errores.append("Código de empleado debe ser positivo")
        except (ValueError, TypeError):
            errores.append("Código de empleado debe ser un número")

    if datos.get("tipo_sancion"):
        tipos_validos = [t for tipos in catalogos.CATEGORIAS.values() for t in tipos]
        if datos["tipo_sancion"] not in tipos_validos:
            errores.append(f"Tipo de sanción '{datos['tipo_sancion']}' no es válido")

    if datos.get("fecha"):
        try:
            datetime.strptime(str(datos["fecha"])[:10], "%Y-%m-%d")
        except ValueError:
            errores.append("Formato de fecha inválido (debe ser YYYY-MM-DD)")

    obs = datos.get("observaciones")
    if obs and len(obs) > catalogos.VALIDACIONES["observaciones_maximo"]:
        errores.append(
            f"Observaciones no puede exceder {catalogos.VALIDACIONES['observaciones_maximo']} caracteres"
        )

    return len(errores) == 0, errores


def validar_estado_transicion(estado_actual: str, estado_nuevo: str) -> tuple[bool, str]:
    """LEGADO (código muerto, README §item utils_nuevo): los nombres de estado
    ('pendiente'/'creado'/'procesado') no coinciden con los reales de Supabase
    ('borrador'/'enviado'/'aprobado'/'rechazado'). Se porta tal cual, sin corregir.
    """
    transiciones_validas = {
        "pendiente": ["aprobado", "rechazado"],
        "creado": ["aprobado", "rechazado"],
        "aprobado": ["procesado"],
        "rechazado": [],
        "procesado": [],
    }
    if estado_actual not in transiciones_validas:
        return False, f"Estado actual '{estado_actual}' no es válido"
    if estado_nuevo not in transiciones_validas[estado_actual]:
        return False, f"No se puede cambiar de '{estado_actual}' a '{estado_nuevo}'"
    return True, "Transición válida"


def formatear_texto_estado(estado: str) -> str:
    return catalogos.ESTADOS_LEGIBLES.get(estado, estado.title())


def obtener_color_estado(estado: str) -> str:
    return catalogos.COLORES_ESTADO.get(estado, "#1976d2")
