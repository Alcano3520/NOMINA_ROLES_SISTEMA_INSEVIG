"""Re-exporta los modelos de la BD de la app (viven en `core/db/models.py`).

Se mantiene este módulo por compatibilidad de imports en la app web.
"""

from core.db.models import (  # noqa: F401
    AppConfig,
    AuditLog,
    EmailSendLog,
    Job,
    LoanHistoryMigrated,
    RolePermission,
    User,
    UserRole,
)
