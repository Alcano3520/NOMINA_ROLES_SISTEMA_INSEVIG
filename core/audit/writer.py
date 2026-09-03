"""Escritor de auditoría.

    with audit_scope("empleados", "editar", usuario="jperez", roles={"editor"},
                     target_table="RPEMPLEA", target_key="1012",
                     antes=fila_actual) as ev:
        ...  # mutar SQL Server
        ev.despues(fila_nueva)
    # al salir sin excepción -> status 'ok'; con excepción -> 'error' + re-raise
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
from collections.abc import Iterator

from core.db import appdb
from core.db.models import AuditLog
from core.logging_setup import request_id_var, usuario_var

log = logging.getLogger(__name__)


def _json(v: object) -> str:
    if v is None:
        return ""
    try:
        return json.dumps(v, default=str, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(v))


class AuditWriter:
    def __init__(self, fila_id: int):
        self.fila_id = fila_id

    def despues(self, valor: object) -> None:
        with appdb.session() as s:
            row = s.get(AuditLog, self.fila_id)
            if row:
                row.after_json = _json(valor)
                s.add(row)
                s.commit()

    def _cerrar(self, status: str, error: str = "") -> None:
        with appdb.session() as s:
            row = s.get(AuditLog, self.fila_id)
            if row:
                row.status = status
                row.error = error[:4000]
                s.add(row)
                s.commit()


@contextlib.contextmanager
def audit_scope(
    module: str,
    action: str,
    *,
    usuario: str = "",
    roles: set[str] | None = None,
    fuente: str = "",
    target_table: str = "",
    target_key: str = "",
    antes: object = None,
    after: object = None,
) -> Iterator[AuditWriter]:
    with appdb.session() as s:
        row = AuditLog(
            username=usuario or usuario_var.get(),
            role=",".join(sorted(roles or [])),
            module=module,
            action=action,
            fuente=fuente,
            target_table=target_table,
            target_key=str(target_key),
            before_json=_json(antes),
            after_json=_json(after),
            status="pending",
            request_id=request_id_var.get(),
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        assert row.id is not None
        fila_id = row.id

    w = AuditWriter(fila_id)
    try:
        yield w
    except Exception as e:  # noqa: BLE001
        w._cerrar("error", repr(e))
        raise
    else:
        w._cerrar("ok")


def registrar_evento(
    module: str,
    action: str,
    *,
    usuario: str = "",
    roles: set[str] | None = None,
    status: str = "ok",
    **extra: str,
) -> None:
    """Evento simple sin before/after (login, logout, export, etc.)."""
    with appdb.session() as s:
        s.add(
            AuditLog(
                ts=dt.datetime.now(dt.UTC),
                username=usuario or usuario_var.get(),
                role=",".join(sorted(roles or [])),
                module=module,
                action=action,
                status=status,
                request_id=request_id_var.get(),
                target_table=extra.get("target_table", ""),
                target_key=str(extra.get("target_key", "")),
                fuente=extra.get("fuente", ""),
            )
        )
        s.commit()
