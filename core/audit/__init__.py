"""Auditoría de escrituras. Como SQL Server y el Postgres de la app no comparten
transacción, se escribe una fila `pending` (con before-image) ANTES de mutar y se
marca `ok`/`error` después. Da rastro forense incluso ante caída.
"""

from core.audit.writer import AuditWriter, audit_scope, registrar_evento

__all__ = ["AuditWriter", "audit_scope", "registrar_evento"]
