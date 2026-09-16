"""core/repos/usuarios_rrhh_sync.py — sincronización hacia `usuarios_rrhh`
(sistema RRHH compartido). Cliente Supabase falso, sin red.
"""

from __future__ import annotations

import hashlib

from core.repos import usuarios_rrhh_sync as repo


def test_mapear_rol_admin():
    assert repo.mapear_rol({"admin"}) == "admin"
    assert repo.mapear_rol({"admin", "editor"}) == "admin"


def test_mapear_rol_no_admin_cae_a_rrhh():
    assert repo.mapear_rol({"editor"}) == "rrhh"
    assert repo.mapear_rol({"consulta"}) == "rrhh"
    assert repo.mapear_rol(set()) == "rrhh"


# ── cliente falso (mismo patrón que test_usuarios_auth.py) ──────────────────


class _Query:
    def __init__(self, tabla: _Tabla):
        self._tabla = tabla
        self._filtros: dict[str, object] = {}
        self._op = "select"
        self._payload: dict | None = None

    def eq(self, campo, valor):
        self._filtros[campo] = valor
        return self

    def limit(self, _n):
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def execute(self):
        if self._op == "insert":
            fila = dict(self._payload)
            fila.setdefault("id", len(self._tabla.filas) + 1)
            self._tabla.filas.append(fila)
            return type("R", (), {"data": [fila]})()
        if self._op == "update":
            coincidentes = [
                f for f in self._tabla.filas
                if all(f.get(k) == v for k, v in self._filtros.items())
            ]
            for f in coincidentes:
                f.update(self._payload)
            return type("R", (), {"data": coincidentes})()
        # select
        coincidentes = [
            f for f in self._tabla.filas
            if all(f.get(k) == v for k, v in self._filtros.items())
        ]
        return type("R", (), {"data": coincidentes})()


class _Tabla:
    def __init__(self, filas=None):
        self.filas: list[dict] = filas or []

    def select(self, *_a, **_k):
        return _Query(self)

    def insert(self, payload):
        return _Query(self).insert(payload)

    def update(self, payload):
        return _Query(self).update(payload)


class _Client:
    def __init__(self, filas=None):
        self._t = _Tabla(filas)

    def table(self, _name):
        return self._t


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def test_sincronizar_creacion_nuevo_usuario():
    cli = _Client()
    ok, _detalle = repo.sincronizar_creacion("ana", "Clave123", "Ana Pérez", {"editor"}, cliente=cli)
    assert ok
    assert cli._t.filas[0]["username"] == "ana"
    assert cli._t.filas[0]["password_hash"] == _hash("Clave123")
    assert cli._t.filas[0]["rol"] == "rrhh"
    assert cli._t.filas[0]["origen_sync"] == "insevig_web"


def test_sincronizar_creacion_respeta_rol_admin():
    cli = _Client()
    ok, _ = repo.sincronizar_creacion("jefe", "Clave123", "Jefe", {"admin"}, cliente=cli)
    assert ok
    assert cli._t.filas[0]["rol"] == "admin"


def test_sincronizar_creacion_no_pisa_usuario_ajeno():
    """BUG REAL evitado a propósito: 'admin' ya existe en usuarios_rrhh como
    cuenta real de otro sistema -- nunca debe sobrescribirse."""
    cli = _Client(filas=[{"id": 13, "username": "admin", "password_hash": "otro-hash"}])
    ok, detalle = repo.sincronizar_creacion("admin", "ClaveNueva", "Admin INSEVIG", {"admin"}, cliente=cli)
    assert not ok
    assert "ya existe" in detalle
    assert len(cli._t.filas) == 1
    assert cli._t.filas[0]["password_hash"] == "otro-hash"  # sin tocar


def test_sincronizar_clave_actualiza_solo_filas_propias():
    cli = _Client(filas=[
        {"id": 1, "username": "ana", "password_hash": "viejo", "origen_sync": "insevig_web"},
    ])
    ok, _ = repo.sincronizar_clave("ana", "ClaveNueva1", cliente=cli)
    assert ok
    assert cli._t.filas[0]["password_hash"] == _hash("ClaveNueva1")


def test_sincronizar_clave_no_toca_fila_preexistente_del_legado():
    """Fila sin origen_sync='insevig_web' (cuenta legado) -- no se actualiza,
    aunque el username coincida con un usuario local que se está reseteando."""
    cli = _Client(filas=[{"id": 13, "username": "admin", "password_hash": "hash-legado"}])
    ok, detalle = repo.sincronizar_clave("admin", "ClaveNueva1", cliente=cli)
    assert not ok
    assert "no fue creado por esta app" in detalle
    assert cli._t.filas[0]["password_hash"] == "hash-legado"


def test_sincronizar_activo_actualiza_solo_filas_propias():
    cli = _Client(filas=[
        {"id": 1, "username": "ana", "activo": True, "origen_sync": "insevig_web"},
    ])
    ok, _ = repo.sincronizar_activo("ana", False, cliente=cli)
    assert ok
    assert cli._t.filas[0]["activo"] is False


def test_sincronizar_maneja_error_de_red_sin_lanzar():
    class _ClientRoto:
        def table(self, _name):
            raise RuntimeError("sin conexión")

    ok, detalle = repo.sincronizar_creacion("ana", "Clave123", "Ana", {"editor"}, cliente=_ClientRoto())
    assert not ok
    assert "No se pudo sincronizar" in detalle
