"""Envío de correo (reemplazo de Outlook COM). Backend por config: console|smtp|graph."""

from core.email.service import EmailMensaje, get_sender, render_plantilla

__all__ = ["EmailMensaje", "get_sender", "render_plantilla"]
