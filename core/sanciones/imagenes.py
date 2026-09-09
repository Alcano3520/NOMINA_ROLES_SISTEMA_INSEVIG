"""Resolución de URL de firma / foto de evidencia de una sanción.

Trasplante verbatim de `sistema_sanciones_RRHH/nucleo_modular/imagenes.py`.
Pura lógica de strings: no descarga nada.
"""

from __future__ import annotations

CAMPOS_FIRMA = ["firma_path", "firma", "firma_url", "signature_url", "firma_empleado", "documento_firma"]
CAMPOS_FOTO = ["foto_url", "foto", "image_url", "documento", "documento_url"]


def resolver_url_imagen(sancion: dict, campos_posibles: list[str], supabase_url: str) -> str | None:
    """Primer campo de `campos_posibles` con valor en `sancion`, convertido a URL
    pública (acepta http(s) completas y rutas relativas del Storage de Supabase).
    `None` si ningún campo es reconocible como imagen.
    """
    for campo in campos_posibles:
        valor = sancion.get(campo, "")
        if not (valor and isinstance(valor, str) and valor.strip()):
            continue
        valor = valor.strip()
        if valor.startswith("http"):
            return valor
        base = supabase_url.rstrip("/")
        if valor.startswith(("/storage/", "storage/")):
            return f"{base}/{valor.lstrip('/')}"
        if "/" in valor and "." in valor.rsplit("/", 1)[-1]:
            return f"{base}/storage/v1/object/public/{valor.lstrip('/')}"
    return None


def resolver_url_firma(sancion: dict, supabase_url: str) -> str | None:
    return resolver_url_imagen(sancion, CAMPOS_FIRMA, supabase_url)


def resolver_url_foto(sancion: dict, supabase_url: str) -> str | None:
    return resolver_url_imagen(sancion, CAMPOS_FOTO, supabase_url)
