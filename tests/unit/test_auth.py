"""Hash de contraseñas (usado por login y cambio de contraseña)."""

from insevig_web import auth


def test_hash_verify_roundtrip():
    h = auth.hash_password("Secreta123")
    assert auth.verify_password("Secreta123", h)
    assert not auth.verify_password("otra", h)


def test_hash_admite_claves_largas():
    clave = "x" * 200
    assert auth.verify_password(clave, auth.hash_password(clave))
