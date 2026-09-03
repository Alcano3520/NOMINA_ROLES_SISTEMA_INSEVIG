"""Generación de PDF (roles de pago). Devuelven bytes."""

from core.pdf.layout import formatear_nombre_archivo
from core.pdf.rol_pago import OpcionesRol, rol_pago_pdf

__all__ = ["OpcionesRol", "formatear_nombre_archivo", "rol_pago_pdf"]
