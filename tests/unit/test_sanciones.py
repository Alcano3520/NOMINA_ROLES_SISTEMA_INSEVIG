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


def test_es_modulo_reflex():
    # C3 revisado (2026-09-09): sanciones ES un módulo web (reemplaza main.py).
    from insevig_web.registry import MODULES

    m = {x.nombre: x for x in MODULES}
    assert "sanciones" in m
    assert {i.ruta for i in m["sanciones"].items} == {
        "/sanciones/bandeja", "/sanciones/historial", "/sanciones/buscar",
        "/sanciones/novedades", "/sanciones/estadisticas",
    }


def test_roles_usuarios_referencia():
    assert catalogos.ROLES_USUARIOS["rrhh"]["puede_procesar"] is True
    assert catalogos.ROLES_USUARIOS["gerencia"]["puede_procesar"] is False


@pytest.mark.parametrize("estado,esperado", [
    ("enviado", "Pendiente de Aprobacion"), ("aprobado", "Aprobado por Gerencia"),
])
def test_estados_legibles(estado, esperado):
    assert catalogos.ESTADOS_LEGIBLES[estado] == esperado


# ── estadísticas (fake client) ────────────────────────────────────────────

def test_estadisticas():
    import datetime as dt

    hoy = dt.datetime.now().strftime("%Y-%m-%d")
    cli = _FakeClient([
        {"status": "enviado", "tipo_sancion": "ATRASO", "comentarios_rrhh": None},
        {"status": "aprobado", "tipo_sancion": "FALTA", "comentarios_rrhh": None},
        {"status": "aprobado", "tipo_sancion": "FALTA",
         "comentarios_rrhh": "Procesado", "updated_at": f"{hoy}T10:00:00"},
    ])
    st = repo.estadisticas(cliente=cli)
    assert st["pendientes_aprobacion"] == 1
    assert st["pendientes_proceso"] == 1
    assert st["total_procesadas"] == 1
    assert st["procesadas_hoy"] == 1
    assert st["por_tipo"]["FALTA"] == 1


# ── valores monetarios (AppConfig) ────────────────────────────────────────

def test_valores_defaults_y_set():
    from core.sanciones.valores import DEFAULTS, get_valores, set_valor

    # los tipos por defecto siempre están presentes (aunque otro test los cambie)
    assert set(DEFAULTS) <= set(get_valores())
    set_valor("MAL USO DEL EQUIPO DE DOTACION", 99)
    assert get_valores()["MAL USO DEL EQUIPO DE DOTACION"] == 99.0
    set_valor("MAL USO DEL EQUIPO DE DOTACION", DEFAULTS["MAL USO DEL EQUIPO DE DOTACION"])


# ── excel builder ─────────────────────────────────────────────────────────

def test_sanciones_xlsx():
    import io

    import openpyxl

    from core.excel.sanciones_builders import sanciones_xlsx

    data = sanciones_xlsx(
        [{"id": "s1", "empleado_cod": 1, "empleado_cedula": "0912345678",
          "empleado_nombre": "ANA", "tipo_sancion": "ATRASO", "fecha": "2026-09-05",
          "status": "aprobado"}],
        {}, {"ATRASO": 16},
    )
    wb = openpyxl.load_workbook(io.BytesIO(data))
    assert "Resumen" in wb.sheetnames
    assert "Detalle Resumen" in wb.sheetnames
