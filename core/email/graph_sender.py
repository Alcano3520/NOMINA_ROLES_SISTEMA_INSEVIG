"""Envío por Microsoft Graph (client-credentials). Preferido si hay M365.

Requiere: app registrada en Entra ID con permiso de aplicación Mail.Send y una
Application Access Policy que limite el envío al buzón de RRHH (`GRAPH_SENDER`).
"""

from __future__ import annotations

import base64

import httpx

from core.config import get_settings
from core.email.service import EmailMensaje

_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_SEND_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"


class GraphSender:
    def _token(self) -> str:
        s = get_settings()
        r = httpx.post(
            _TOKEN_URL.format(tenant=s.graph_tenant_id),
            data={
                "client_id": s.graph_client_id,
                "client_secret": s.graph_client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["access_token"]

    def enviar(self, mensaje: EmailMensaje) -> None:
        s = get_settings()
        payload = {
            "message": {
                "subject": mensaje.asunto,
                "body": {"contentType": "HTML", "content": mensaje.html},
                "toRecipients": [{"emailAddress": {"address": mensaje.para}}],
                "ccRecipients": [{"emailAddress": {"address": c}} for c in mensaje.cc],
                "bccRecipients": [{"emailAddress": {"address": b}} for b in mensaje.bcc],
                "attachments": [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": nombre,
                        "contentBytes": base64.b64encode(contenido).decode(),
                    }
                    for nombre, contenido in mensaje.adjuntos
                ],
            },
            "saveToSentItems": True,
        }
        r = httpx.post(
            _SEND_URL.format(sender=s.graph_sender),
            headers={"Authorization": f"Bearer {self._token()}"},
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
