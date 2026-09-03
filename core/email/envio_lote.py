"""Envío de roles por correo, como Job reanudable e idempotente.

Reemplaza `envio_roles/ENVIO_ROLES_*` (Outlook COM). Idempotencia por `EmailSendLog`:
no reenvía a un empleado ya marcado 'enviado' para el mismo job.
"""

from __future__ import annotations

import datetime as dt
import time

import sqlmodel

from core.db import appdb
from core.db.models import EmailSendLog
from core.email.service import EmailMensaje, get_sender, render_plantilla

_HTML_DEFECTO = (
    "<p>Estimado/a {{StrNombres}},</p>"
    "<p>Adjunto encontrará su rol de pago correspondiente a {{mes}}/{{anio}}.</p>"
    "<p>Cédula: {{StrCedula}} · Código: {{StrEmpleado}}</p>"
    "<p>Recursos Humanos — INSEVIG</p>"
)


def job_enviar_roles(
    ctx,
    destinatarios: list[dict],  # [{'empleado','nombre','cedula','email','pdf': bytes}]
    *,
    mes: str,
    anio: str,
    intervalo_seg: float = 2.0,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    html_plantilla: str = "",
) -> None:
    sender = get_sender()
    plantilla = html_plantilla or _HTML_DEFECTO
    total = len(destinatarios)
    enviados = 0
    errores = 0

    with appdb.session() as s:
        ya = {
            r.employee_code
            for r in s.exec(
                sqlmodel.select(EmailSendLog).where(
                    EmailSendLog.job_id == ctx.job_id, EmailSendLog.status == "enviado"
                )
            ).all()
        }

    for i, d in enumerate(destinatarios, 1):
        if ctx.cancelado:
            break
        cod = str(d.get("empleado") or "").strip()
        if cod in ya:
            continue
        try:
            html = render_plantilla(
                plantilla,
                {
                    "StrNombres": d.get("nombre", ""),
                    "StrCedula": d.get("cedula", ""),
                    "StrEmpleado": cod,
                    "mes": mes,
                    "anio": anio,
                    "año": anio,
                },
            )
            msg = EmailMensaje(
                para=d["email"],
                asunto=f"ROL {mes}/{anio}",
                html=html,
                cc=cc or [],
                bcc=bcc or [],
                adjuntos=[(f"rol_{cod}_{anio}-{mes}.pdf", d["pdf"])] if d.get("pdf") else [],
            )
            sender.enviar(msg)
            _log(ctx.job_id, cod, d["email"], "enviado")
            enviados += 1
        except Exception as e:  # noqa: BLE001, PERF203
            _log(ctx.job_id, cod, d.get("email", ""), "error", str(e)[:300])
            errores += 1
        ctx.progreso(i, total, f"{enviados} enviados, {errores} con error")
        if intervalo_seg:
            time.sleep(intervalo_seg)

    ctx.progreso(total, total, f"Terminado: {enviados} enviados, {errores} con error")


def _log(job_id: int, empleado: str, email: str, estado: str, error: str = "") -> None:
    with appdb.session() as s:
        s.add(
            EmailSendLog(
                job_id=job_id,
                employee_code=empleado,
                email=email,
                status=estado,
                error=error,
                sent_at=dt.datetime.now(dt.UTC) if estado == "enviado" else None,
            )
        )
        s.commit()
