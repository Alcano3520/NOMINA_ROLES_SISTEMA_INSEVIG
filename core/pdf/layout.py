"""Formateadores del nombre de archivo del rol (6 patrones del legado) y utilidades."""

from __future__ import annotations

import re

from core.utils import normalizar_cedula

FORMATOS = (
    "cedula-nombre",
    "nombre-cedula",
    "cedula-nombre-cargo",
    "cedula-nombre-depto",
    "nombre-cargo-cedula",
    "depto-nombre-cedula",
)


def _slug(texto: str) -> str:
    texto = str(texto or "").strip()
    return re.sub(r"[^\w\- ]", "", texto).replace(" ", "_")[:60] or "SIN_DATO"


def formatear_nombre_archivo(
    formato: str, *, empleado: str, nombre: str, cedula: object, cargo: str, depto: str, periodo: str
) -> str:
    ced = normalizar_cedula(cedula)
    nom = _slug(nombre)
    car = _slug(cargo)
    dep = _slug(depto)
    partes = {
        "cedula-nombre": [ced, nom],
        "nombre-cedula": [nom, ced],
        "cedula-nombre-cargo": [ced, nom, car],
        "cedula-nombre-depto": [ced, nom, dep],
        "nombre-cargo-cedula": [nom, car, ced],
        "depto-nombre-cedula": [dep, nom, ced],
    }.get(formato, [ced, nom])
    return "-".join(partes) + f"_{periodo}.pdf"
