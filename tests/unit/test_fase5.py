"""Fase 5: email (render + idempotencia) + registrador (dedupe/dry-run)."""

from core.email.envio_lote import _HTML_DEFECTO
from core.email.service import ConsoleSender, EmailMensaje, render_plantilla
from core.repos import registrador


def test_render_plantilla_placeholders_legado_y_jinja():
    html = render_plantilla(
        "Hola {{StrNombres}}, rol {{mes}}/{{año}}. {{ 'ok' if activo else 'no' }}",
        {"StrNombres": "JUAN", "mes": "06", "año": "2026", "activo": True},
    )
    assert "Hola JUAN" in html
    assert "06/2026" in html
    assert html.endswith("ok")


def test_html_defecto_renderiza():
    out = render_plantilla(_HTML_DEFECTO, {"StrNombres": "ANA", "StrCedula": "0920116811", "StrEmpleado": "1012", "mes": "6", "anio": "2026"})
    assert "ANA" in out and "0920116811" in out and "6/2026" in out


def test_console_sender_no_lanza():
    ConsoleSender().enviar(EmailMensaje(para="x@y.com", asunto="t", html="<p>h</p>"))


def test_email_plantilla_guarda_y_recupera(app_db):
    from core import parametros

    assert parametros.get_email_plantilla()["asunto"] == "ROL {{mes}}/{{anio}}"
    parametros.set_email_plantilla("Rol de {{StrNombres}}", "<p>Hola {{StrNombres}}</p>")
    p = parametros.get_email_plantilla()
    assert p["asunto"] == "Rol de {{StrNombres}}"
    assert "Hola {{StrNombres}}" in p["html"]
    # asunto vacío vuelve al valor por defecto
    parametros.set_email_plantilla("", "")
    assert parametros.get_email_plantilla()["asunto"] == "ROL {{mes}}/{{anio}}"


def test_ia_config_override_desde_bd_sin_tocar_api_key(app_db, monkeypatch):
    from core import parametros

    monkeypatch.setenv("IA_API_KEY", "secreta-del-env")
    import core.config as config
    config.get_settings.cache_clear()

    parametros.set_ia_config("ollama", "http://ollama.local:11434", "llama3.1")
    cfg = parametros.get_ia_config()
    assert cfg["provider"] == "ollama"
    assert cfg["base_url"] == "http://ollama.local:11434"
    assert cfg["model"] == "llama3.1"
    assert cfg["api_key"] == "secreta-del-env"  # siempre del .env, nunca de la BD
    config.get_settings.cache_clear()


def test_biess_preparar_marca_no_encontrado(monkeypatch):
    monkeypatch.setattr(registrador, "_empleados_por_cedulas", lambda cs: {})
    movs, avisos = registrador.preparar_biess([{"cedula": "0920116811", "valor": 45.5}], "2026-06")
    assert movs[0].empleado == ""
    assert movs[0].estado_biess == "no_encontrado"
    assert movs[0].cedula == "0920116811"
    assert avisos


def test_biess_preparar_empareja_activo_y_liquidado(monkeypatch):
    monkeypatch.setattr(
        registrador, "_empleados_por_cedulas",
        lambda cs: {
            "0920116811": {"EMPLEADO": "1012", "APELLIDOS": "P", "NOMBRES": "J",
                           "ESTADO": "ACT", "CEDULA": 920116811.0},
            "0912345678": {"EMPLEADO": "1013", "APELLIDOS": "X", "NOMBRES": "Y",
                           "ESTADO": "LIQ", "CEDULA": 912345678.0},
        },
    )
    movs, avisos = registrador.preparar_biess(
        [{"cedula": "0920116811", "valor": 45.5}, {"cedula": "0912345678", "valor": 10}],
        "2026-06", clase=207,
    )
    assert movs[0].empleado == "1012" and movs[0].estado_biess == "activo"
    assert movs[0].clase == 207 and movs[0].nombre == "P J"
    assert movs[1].estado_biess == "liquidado"
    assert any("liquidado" in a for a in avisos)


def test_observacion_biess():
    assert registrador.observacion_biess("204", "2026-07-15") == "PRESTAMOS QUIROGRAFARIOS MES: JULIO 2026"
    assert registrador.observacion_biess(207, "2026-12-01") == "PRESTAMOS HIPOTECARIOS MES: DICIEMBRE 2026"


def test_postear_biess_dry_run_cuenta_por_estado():
    movs = [
        registrador.Movimiento("1012", 204, 10.0, "X", "2026-06", "activo", "0920116811", "P J"),
        registrador.Movimiento("1013", 204, 5.0, "X", "2026-06", "liquidado", "0912345678", "X Y"),
        registrador.Movimiento("", 204, 3.0, "X", "2026-06", "no_encontrado", "0900000000", "?"),
    ]
    res = registrador.postear_biess(
        movs, clase=204, fecha="2026-06-30", observacion="obs", usuario="t", roles=set(), dry_run=True,
    )
    assert res["a_insertar"] == 1 and res["liquidados"] == 1 and res["no_encontrados"] == 1
    assert res["total"] == 10.0 and res["insertados"] == 0


def test_postear_dry_run_sin_empleado_cuenta():
    movs = [registrador.Movimiento("", 204, 10.0, "X", "2026-06", "no_encontrado")]
    res = registrador.postear(movs, usuario="t", roles=set(), dry_run=True)
    assert res == {"insertados": 0, "omitidos_dedupe": 0, "sin_empleado": 1}
