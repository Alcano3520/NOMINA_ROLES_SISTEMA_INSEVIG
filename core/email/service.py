"""Contrato de envío de correo + selección de backend + render de plantilla."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol

from jinja2 import Environment, select_autoescape

from core.config import get_settings

_env = Environment(autoescape=select_autoescape(["html"]))


@dataclass
class EmailMensaje:
    para: str
    asunto: str
    html: str
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    adjuntos: list[tuple[str, bytes]] = field(default_factory=list)  # (nombre, contenido)


class EmailSender(Protocol):
    def enviar(self, mensaje: EmailMensaje) -> None:
        ...


class ConsoleSender:
    """Backend de desarrollo: no envía, solo registra."""

    def enviar(self, mensaje: EmailMensaje) -> None:
        import logging

        logging.getLogger(__name__).info(
            "[EMAIL/console] para=%s asunto=%s adjuntos=%d",
            mensaje.para, mensaje.asunto, len(mensaje.adjuntos),
        )


def render_plantilla(html: str, contexto: dict) -> str:
    """Soporta tanto Jinja (`{{ x }}`) como los placeholders del legado
    (`{{StrNombres}}`, `{{año}}` sin espacios)."""
    normalizado = html
    for k, v in contexto.items():
        normalizado = normalizado.replace("{{" + k + "}}", str(v))
    return _env.from_string(normalizado).render(**contexto)


@lru_cache
def get_sender() -> EmailSender:
    backend = get_settings().email_backend.lower()
    if backend == "smtp":
        from core.email.smtp_sender import SmtpSender

        return SmtpSender()
    if backend == "graph":
        from core.email.graph_sender import GraphSender

        return GraphSender()
    return ConsoleSender()
