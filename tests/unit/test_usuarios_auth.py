"""core/repos/usuarios_auth.py — carga masiva de usuarios de Supabase Auth.

Cliente Supabase falso (Auth admin + profiles). Sin red.
"""

from __future__ import annotations

from core.repos import usuarios_auth as repo

# ── contraseñas ────────────────────────────────────────────────────────────

def test_generar_password_segura():
    p = repo.generar_password_segura(12)
    assert len(p) == 12
    assert any(c.islower() for c in p)
    assert any(c.isupper() for c in p)
    assert any(c.isdigit() for c in p)
    assert any(c in "!@#$%&*" for c in p)


def test_validar_password():
    assert repo.validar_password("abc123")[0]
    assert not repo.validar_password("abc")[0]
    assert not repo.validar_password("x" * 80)[0]


# ── parseo de pegado ──────────────────────────────────────────────────────

def test_parsear_pegado_autodetecta_sep():
    filas = repo.parsear_pegado(
        "ana@x.com\tAna\tsupervisor\tOps\n"
        "no-email-linea\n"
        "beto@x.com;Beto;rrhh"
    )
    assert [f["email"] for f in filas] == ["ana@x.com", "beto@x.com"]
    assert filas[0]["rol"] == "supervisor"
    assert filas[1]["nombre"] == "Beto"


# ── cliente falso ─────────────────────────────────────────────────────────

class _Admin:
    def __init__(self, users):
        self._users = users
        self.created: list[dict] = []
        self.updated: list[tuple] = []

    def list_users(self, page=1, per_page=100):
        return list(self._users)

    def create_user(self, attrs):
        u = {"id": f"id-{len(self.created) + 1}", "email": attrs["email"]}
        self.created.append(attrs)
        self._users.append(u)
        return type("R", (), {"user": type("U", (), u)()})()

    def update_user_by_id(self, uid, attrs):
        self.updated.append((uid, attrs))


class _Auth:
    def __init__(self, admin):
        self.admin = admin


class _Table:
    def __init__(self):
        self.rows: list[dict] = []
        self.upserts: list[dict] = []

    def select(self, *a, **k):
        return self

    def execute(self):
        return type("R", (), {"data": self.rows})()

    def upsert(self, data):
        self.upserts.append(data)
        return self


class _Client:
    def __init__(self, users=None):
        self.auth = _Auth(_Admin(users or []))
        self._t = _Table()

    def table(self, _name):
        return self._t


def test_crear_usuario_nuevo():
    cli = _Client()
    r = repo.crear_usuario(
        {"email": "ana@x.com", "nombre": "Ana", "rol": "supervisor",
         "password": "Segura123!", "_password_generada": True},
        cliente=cli,
    )
    assert r.ok and r.accion == "CREADO"
    assert r.password == "Segura123!"  # se devuelve porque fue generada
    assert cli._t.upserts[0]["role"] == "supervisor"


def test_crear_usuario_existente_sin_actualizar():
    cli = _Client(users=[{"id": "u1", "email": "ana@x.com"}])
    r = repo.crear_usuario({"email": "ana@x.com", "password": "Segura123!"}, cliente=cli)
    assert not r.ok and "ya existe" in r.detalle


def test_crear_usuario_existente_actualiza():
    cli = _Client(users=[{"id": "u1", "email": "ana@x.com"}])
    r = repo.crear_usuario(
        {"email": "ana@x.com", "password": "Segura123!"},
        actualizar_si_existe=True, cliente=cli,
    )
    assert r.ok and r.accion == "ACTUALIZADO"
    assert cli.auth.admin.updated[0][0] == "u1"


def test_crear_usuario_password_invalida():
    r = repo.crear_usuario({"email": "x@y.com", "password": "abc"}, cliente=_Client())
    assert not r.ok and "contraseña" in r.detalle.lower()


def test_resetear_password():
    cli = _Client(users=[{"id": "u9", "email": "b@x.com"}])
    ok, msg = repo.resetear_password("u9", "NuevaClave1!", cliente=cli)
    assert ok
    assert cli.auth.admin.updated[0] == ("u9", {"password": "NuevaClave1!"})


def test_cargar_masivo_dry_run():
    filas = repo.parsear_pegado("ana@x.com\tAna\tsupervisor\nmal\nbeto@x.com\tBeto\trrhh")
    res = repo.cargar_masivo(filas, generar_passwords=True, dry_run=True)
    assert res.creados == 2
    assert all(r.accion == "CREARÍA" for r in res.resultados)
    assert all(r.password for r in res.resultados)  # generadas en el preview


def test_cargar_masivo_real():
    cli = _Client()
    filas = [{"email": "ana@x.com", "nombre": "Ana", "rol": "supervisor", "password": ""}]
    res = repo.cargar_masivo(filas, generar_passwords=True, dry_run=False, cliente=cli)
    assert res.creados == 1
    assert res.resultados[0].ok
    assert len(cli.auth.admin.created) == 1


def test_carga_usuarios_en_registry():
    from insevig_web.registry import MODULES

    m = {x.nombre: x for x in MODULES}
    assert "carga_usuarios" in m
    assert len(m["carga_usuarios"].items) == 4
