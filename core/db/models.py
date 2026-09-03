"""Tablas propias de la app (Postgres en prod, SQLite en dev). NO son las tablas
de nómina de SQL Server ni de Supabase — solo: auth, auditoría, jobs, config,
historial de préstamos migrado del SQLite.

Viven en `core/` (no en `insevig_web/`) porque `core.audit` y `core.jobs` las
usan y `core/` no puede importar la app web. `insevig_web/models.py` las re-exporta.

★ CONGELADO: cambiar un modelo es una tarea aparte (migración + revisión).
Futuro (offline-first, ver docs/CONTRATOS.md): las tablas que se sincronicen con
Supabase necesitarán PK uuid + updated_at/synced_at/deleted_at.
"""

from __future__ import annotations

import datetime as dt

from sqlmodel import Field, SQLModel


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class User(SQLModel, table=True):
    __tablename__ = "app_user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    full_name: str = ""
    email: str = ""
    password_hash: str = ""
    is_active: bool = True
    created_at: dt.datetime = Field(default_factory=_now)
    last_login: dt.datetime | None = None


class UserRole(SQLModel, table=True):
    __tablename__ = "app_user_role"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    role: str = Field(index=True)  # admin | editor | consulta


class RolePermission(SQLModel, table=True):
    __tablename__ = "app_role_permission"

    id: int | None = Field(default=None, primary_key=True)
    role: str = Field(index=True)
    module: str = Field(index=True)
    action: str
    allowed: bool = True


class AuditLog(SQLModel, table=True):
    __tablename__ = "app_audit_log"

    id: int | None = Field(default=None, primary_key=True)
    ts: dt.datetime = Field(default_factory=_now, index=True)
    user_id: int | None = None
    username: str = ""
    role: str = ""
    module: str = Field(default="", index=True)
    action: str = Field(default="", index=True)
    fuente: str = ""
    target_table: str = ""
    target_key: str = ""
    before_json: str = ""
    after_json: str = ""
    status: str = "pending"  # pending | ok | error
    error: str = ""
    request_id: str = ""
    ip: str = ""


class AppConfig(SQLModel, table=True):
    __tablename__ = "app_config"

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(index=True)
    value_json: str = "{}"
    scope: str = "global"  # global | user
    user_id: int | None = Field(default=None, index=True)


class Job(SQLModel, table=True):
    __tablename__ = "app_job"

    id: int | None = Field(default=None, primary_key=True)
    tipo: str = Field(index=True)
    params_json: str = "{}"
    status: str = "pendiente"  # pendiente | corriendo | ok | error | cancelado
    progress: int = 0
    total: int = 0
    message: str = ""
    created_by: str = ""
    created_at: dt.datetime = Field(default_factory=_now, index=True)
    started_at: dt.datetime | None = None
    finished_at: dt.datetime | None = None
    result_path: str = ""
    error: str = ""
    cancel_requested: bool = False


class EmailSendLog(SQLModel, table=True):
    __tablename__ = "app_email_send_log"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(index=True)
    employee_code: str = Field(index=True)
    email: str = ""
    status: str = "pendiente"  # pendiente | enviado | error
    error: str = ""
    sent_at: dt.datetime | None = None


class LoanHistoryMigrated(SQLModel, table=True):
    __tablename__ = "app_loan_history_migrated"

    id: int | None = Field(default=None, primary_key=True)
    empleado: str = Field(index=True)
    fecha: str = ""
    ingreso: float = 0.0
    egreso: float = 0.0
    concepto: str = ""
    tipo: str = ""
    numero_fila: int | None = None
    observaciones: str = ""
    origen: str = "sqlite"
    creado_en: dt.datetime = Field(default_factory=_now)
