"""Dominio sanciones (backend puro) + repo con cliente Supabase falso.

`core/repos/sanciones.py` NO tiene UI ni entra en registry (contrato C3).
"""

from __future__ import annotations

import pytest

from core.repos import sanciones as repo
from core.sanciones import catalogos, imagenes, validadores

# ── validadores ────────────────────────────────────────────────────────────

def test_validar_datos_sancion_ok():
    ok, errs = validadores.validar_datos_sancion({
        "empleado_cod": 1234, "empleado_nombre": "PEREZ ANA", "puesto": "VIGILANTE",
        "agente": "SUP X", "fecha": "2026-09-05", "hora": "08:00", "tipo_sancion": "ATRASO",
    })
    assert ok and errs == []


def test_validar_datos_sancion_errores():
    ok, errs = validadores.validar_datos_sancion({
        "empleado_cod": -1, "fecha": "05/09/2026", "tipo_sancion": "INVENTADO",
    })
    assert not ok
    assert any("requerido" in e for e in errs)
    assert any("positivo" in e for e in errs)
    assert any("fecha" in e.lower() for e in errs)
    assert any("no es válido" in e for e in errs)


def test_validar_estado_transicion():
    assert validadores.validar_estado_transicion("aprobado", "procesado")[0]
    assert not validadores.validar_estado_transicion("rechazado", "aprobado")[0]


def test_formato_y_color_estado():
    assert validadores.formatear_texto_estado("enviado") == "Pendiente de Aprobacion"
    assert validadores.obtener_color_estado("desconocido") == "#1976d2"


# ── imágenes ───────────────────────────────────────────────────────────────

def test_resolver_url_imagen():
    base = "https://proj.supabase.co"
    assert imagenes.resolver_url_firma({"firma_path": "https://x/y.png"}, base) == "https://x/y.png"
    assert imagenes.resolver_url_firma({"firma_path": "firmas/a.png"}, base) == (
        "https://proj.supabase.co/storage/v1/object/public/firmas/a.png"
    )
    assert imagenes.resolver_url_foto({"foto_url": ""}, base) is None


# ── categorización ─────────────────────────────────────────────────────────

def test_categorizar_sanciones():
    out = repo.categorizar_sanciones([
        {"tipo_sancion": "FALTA"}, {"tipo_sancion": "ATRASO"}, {"tipo_sancion": "RARO"},
    ])
    assert len(out["Faltas y Permisos"]) == 1
    assert len(out["Resto"]) == 2  # ATRASO + RARO (fallback)


# ── repo con cliente falso ─────────────────────────────────────────────────

class _FakeQuery:
    def __init__(self, data, count=None):
        self._data = data
        self._count = count
        self.updates: list[dict] = []

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    @property
    def not_(self):
        return self

    def ilike(self, *a, **k):
        return self

    def or_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def range(self, *a, **k):
        return self

    def update(self, data):
        self.updates.append(data)
        return self

    def execute(self):
        return type("R", (), {"data": self._data, "count": self._count})()


class _FakeClient:
    def __init__(self, data=None, count=None):
        self.q = _FakeQuery(data if data is not None else [], count)

    def table(self, _name):
        return self.q


def test_obtener_sancion_normaliza_cedula():
    cli = _FakeClient([{"id": "s1", "empleado_cedula": "912345678"}])
    s = repo.obtener_sancion("s1", cliente=cli)
    assert s["empleado_cedula"] == "0912345678"  # normalizada en la frontera


def test_buscar_sanciones_texto_corto():
    assert repo.buscar_sanciones("x", cliente=_FakeClient([])) == []


def test_enriquecer_sanciones_lote():
    emp_cli = _FakeClient([
        {"cod": 1234, "nombres_completos": "ANA PEREZ", "cedula": "912345678",
         "nomcargo": "VIGILANTE", "nomdep": "OPERACIONES", "es_activo": True},
    ])
    sanciones = [{"id": "s1", "empleado_cod": 1234}]
    out = repo.enriquecer_sanciones_lote(sanciones, cliente_empleados=emp_cli)
    assert out[0]["empleado_nombre"] == "ANA PEREZ"
    assert out[0]["empleado_cedula"] == "0912345678"
    assert out[0]["empleado_cargo"] == "VIGILANTE"


def test_aprobar_sancion_individual():
    cli = _FakeClient([])
    ok, msg = repo.aprobar_sancion_individual({"id": "s1"}, "jperez", cliente=cli)
    assert ok
    assert cli.q.updates[0]["status"] == "aprobado"


def test_procesar_sancion_individual():
    cli = _FakeClient([])
    ok, _ = repo.procesar_sancion_individual({"id": "s1"}, "rrhh1", cliente=cli)
    assert ok
    assert catalogos.MSG_PROCESADO in cli.q.updates[0]["comentarios_rrhh"]


def test_no_esta_en_registry():
    from insevig_web.registry import MODULES

    assert "sanciones" not in {m.nombre for m in MODULES}


def test_roles_usuarios_referencia():
    assert catalogos.ROLES_USUARIOS["rrhh"]["puede_procesar"] is True
    assert catalogos.ROLES_USUARIOS["gerencia"]["puede_procesar"] is False


@pytest.mark.parametrize("estado,esperado", [
    ("enviado", "Pendiente de Aprobacion"), ("aprobado", "Aprobado por Gerencia"),
])
def test_estados_legibles(estado, esperado):
    assert catalogos.ESTADOS_LEGIBLES[estado] == esperado
