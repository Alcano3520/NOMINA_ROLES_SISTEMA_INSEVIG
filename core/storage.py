"""Almacenamiento de salidas de jobs (Excel, PDF, ZIP). Reemplaza el
`filedialog.askdirectory` del escritorio por descargas del navegador.

Los archivos se guardan bajo `STORAGE_DIR/<job_id>/` y se sirven vía `rx.download`.
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

from core.config import get_settings


def _raiz() -> Path:
    p = get_settings().storage_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


def guardar(job_id: str | int, nombre: str, datos: bytes) -> Path:
    """Guarda `datos` como `<STORAGE_DIR>/<job_id>/<nombre>` y devuelve la ruta."""
    nombre = Path(nombre).name  # evita traversal
    carpeta = _raiz() / str(job_id)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / nombre
    destino.write_bytes(datos)
    return destino


def leer(job_id: str | int, nombre: str) -> bytes:
    return (_raiz() / str(job_id) / Path(nombre).name).read_bytes()


def listar(job_id: str | int) -> list[Path]:
    carpeta = _raiz() / str(job_id)
    return sorted(carpeta.iterdir()) if carpeta.is_dir() else []


def purgar(dias: int = 30) -> int:
    """Borra carpetas de jobs más viejas que `dias`. Devuelve cuántas borró."""
    limite = dt.datetime.now().timestamp() - dias * 86400
    borradas = 0
    for carpeta in _raiz().iterdir():
        if carpeta.is_dir() and carpeta.stat().st_mtime < limite:
            shutil.rmtree(carpeta, ignore_errors=True)
            borradas += 1
    return borradas
