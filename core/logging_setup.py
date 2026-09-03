"""Configuración de logging para el núcleo y la app."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

# Contexto por request/job para correlacionar líneas de log con la auditoría.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
usuario_var: ContextVar[str] = ContextVar("usuario", default="-")


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.usuario = usuario_var.get()
        return True


def configurar(nivel: int | str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(usuario)s/%(request_id)s] %(name)s: %(message)s"
        )
    )
    handler.addFilter(_ContextFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(nivel)
