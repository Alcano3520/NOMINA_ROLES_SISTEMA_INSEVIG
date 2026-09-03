"""Foto del empleado. Se guarda en STORAGE_DIR/fotos/<empleado>.<ext>
(fuera de RPEMPLEA; el ERP no tiene columna de foto).
"""

from __future__ import annotations

from pathlib import Path

from core.config import get_settings

_EXT_OK = {"jpg", "jpeg", "png", "webp"}


def _dir() -> Path:
    p = get_settings().storage_dir / "fotos"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ruta(empleado: str) -> Path | None:
    d = _dir()
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = d / f"{empleado}.{ext}"
        if p.exists():
            return p
    return None


def guardar_foto(empleado: str, datos: bytes, nombre_original: str = "") -> str:
    empleado = str(empleado).strip()
    if not empleado:
        raise ValueError("Empleado vacío")
    if len(datos) > 5 * 1024 * 1024:
        raise ValueError("La foto supera 5 MB")
    ext = (nombre_original.rsplit(".", 1)[-1] or "jpg").lower()
    if ext not in _EXT_OK:
        ext = "jpg"
    # borra cualquier foto previa (otra extensión)
    prev = _ruta(empleado)
    if prev:
        prev.unlink(missing_ok=True)
    destino = _dir() / f"{empleado}.{ext}"
    destino.write_bytes(datos)
    return str(destino)


def leer_foto(empleado: str) -> tuple[bytes, str] | None:
    p = _ruta(str(empleado).strip())
    if not p:
        return None
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}[p.suffix.lstrip(".")]
    return p.read_bytes(), f"image/{mime}"


def borrar_foto(empleado: str) -> bool:
    p = _ruta(str(empleado).strip())
    if p:
        p.unlink(missing_ok=True)
        return True
    return False
