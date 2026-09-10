"""Dominio de Sanciones disciplinarias (backend puro).

Regla #7 / contrato C3: `sanciones` NO tiene UI Reflex ni entra en `registry`.
El frontend es la app Flutter `sistema_sanciones_insevig/`. Este paquete +
`core/repos/sanciones.py` existen para un futuro worker de sincronización.
"""

from core.sanciones import catalogos, imagenes, validadores, valores

__all__ = ["catalogos", "imagenes", "validadores", "valores"]
