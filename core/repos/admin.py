"""Consultas de administración sobre la BD de la app (auditoría, …).

Rebanada del módulo `admin`. Solo toca la BD de la app (`core.db.appdb`);
no importa otros `core/repos/*`.
"""

from __future__ import annotations

import datetime as dt

import sqlmodel
from sqlalchemy import func

from core.db import appdb
from core.db.models import AuditLog

LIMITE_AUDITORIA = 200


def _a_fecha(txt: str, *, fin: bool = False) -> dt.datetime | None:
    """`'2026-09-06'` → datetime. `fin=True` suma un día (rango inclusivo)."""
    try:
        d = dt.datetime.fromisoformat(txt.strip())
    except (ValueError, AttributeError):
        return None
    return d + dt.timedelta(days=1) if fin else d


def buscar_auditoria(
    *,
    usuario: str = "",
    modulo: str = "",
    estado: str = "",
    desde: str = "",
    hasta: str = "",
    limite: int = LIMITE_AUDITORIA,
) -> tuple[int, list[dict[str, str]]]:
    """Devuelve `(total_de_coincidencias, hasta `limite` filas más recientes)`.

    Filtros opcionales: `usuario` (substring), `modulo` y `estado` (exactos),
    `desde`/`hasta` (fechas ISO `YYYY-MM-DD`, rango inclusivo). Una fecha
    inválida se ignora.
    """
    d_ini = _a_fecha(desde)
    d_fin = _a_fecha(hasta, fin=True)

    def _filtra(q):
        if usuario.strip():
            q = q.where(sqlmodel.col(AuditLog.username).ilike(f"%{usuario.strip()}%"))
        if modulo.strip():
            q = q.where(AuditLog.module == modulo.strip())
        if estado.strip():
            q = q.where(AuditLog.status == estado.strip())
        if d_ini is not None:
            q = q.where(sqlmodel.col(AuditLog.ts) >= d_ini)
        if d_fin is not None:
            q = q.where(sqlmodel.col(AuditLog.ts) < d_fin)
        return q

    with appdb.session() as s:
        total = int(s.exec(_filtra(sqlmodel.select(func.count()).select_from(AuditLog))).one())
        filas = s.exec(
            _filtra(sqlmodel.select(AuditLog))
            .order_by(sqlmodel.col(AuditLog.ts).desc())
            .limit(limite)
        ).all()
        return total, [
            {
                "ts": str(a.ts)[:19],
                "usuario": a.username,
                "modulo": a.module,
                "accion": a.action,
                "objetivo": f"{a.target_table} {a.target_key}".strip(),
                "status": a.status,
            }
            for a in filas
        ]
