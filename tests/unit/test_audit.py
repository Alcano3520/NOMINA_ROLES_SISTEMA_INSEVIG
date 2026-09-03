import pytest
import sqlmodel

from core.audit.writer import audit_scope, registrar_evento
from core.db import appdb
from core.db.models import AuditLog


def _logs():
    with appdb.session() as s:
        return s.exec(sqlmodel.select(AuditLog)).all()


def test_audit_scope_ok(app_db):
    with audit_scope(
        "empleados", "editar", usuario="jperez", roles={"editor"},
        target_table="RPEMPLEA", target_key="1012", antes={"SUELDO": 800},
    ) as ev:
        ev.despues({"SUELDO": 850})

    (log,) = _logs()
    assert log.status == "ok"
    assert log.module == "empleados" and log.action == "editar"
    assert log.username == "jperez"
    assert "800" in log.before_json and "850" in log.after_json


def test_audit_scope_error_marca_y_relanza(app_db):
    with pytest.raises(RuntimeError):  # noqa: PT012
        with audit_scope("empleados", "eliminar", usuario="x", target_key="99"):
            raise RuntimeError("falló el DELETE")

    (log,) = _logs()
    assert log.status == "error"
    assert "falló el DELETE" in log.error


def test_registrar_evento_login(app_db):
    registrar_evento("auth", "login", usuario="jperez", roles={"editor"})
    (log,) = _logs()
    assert log.module == "auth" and log.action == "login" and log.status == "ok"
