"""Envío por SMTP autenticado (smtp.office365.com:587 STARTTLS, o relay interno)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from core.config import get_settings
from core.email.service import EmailMensaje


class SmtpSender:
    def enviar(self, mensaje: EmailMensaje) -> None:
        s = get_settings()
        msg = EmailMessage()
        msg["From"] = s.smtp_sender or s.smtp_user
        msg["To"] = mensaje.para
        if mensaje.cc:
            msg["Cc"] = ", ".join(mensaje.cc)
        msg["Subject"] = mensaje.asunto
        msg.set_content("Este correo requiere un cliente que muestre HTML.")
        msg.add_alternative(mensaje.html, subtype="html")
        for nombre, contenido in mensaje.adjuntos:
            msg.add_attachment(
                contenido, maintype="application", subtype="pdf", filename=nombre
            )
        destinos = [mensaje.para, *mensaje.cc, *mensaje.bcc]
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=60) as srv:
            if s.smtp_starttls:
                srv.starttls()
            if s.smtp_user:
                srv.login(s.smtp_user, s.smtp_password)
            srv.send_message(msg, to_addrs=destinos)
