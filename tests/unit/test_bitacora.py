from core.repos import bitacora


def test_limpiar_deja_solo_campos_conocidos_no_vacios():
    d = bitacora._limpiar(
        {"apellidos_nombres": "PEREIRA JUAN", "cedula": "", "banco": "PICHINCHA", "xxx": 1}
    )
    assert d == {"apellidos_nombres": "PEREIRA JUAN", "banco": "PICHINCHA"}


def test_estados_validos():
    assert "cobrado" in bitacora.ESTADOS
    assert "pendiente" in bitacora.ESTADOS


def test_cambiar_estado_rechaza_invalido(monkeypatch):
    import pytest

    with pytest.raises(ValueError, match="Estado inválido"):
        bitacora.cambiar_estado(1, "inexistente", usuario="t", roles=set())
