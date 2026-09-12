"""Parámetros de negocio editables desde /admin/parametros.

`get_liquidaciones_params`/`set_liquidaciones_params`/`config_liquidacion`
son la versión web de "⚙ Configuración de Parámetros Anuales" del
`.pyw` original -- IESS%, Fondo de Reserva%, Región por defecto y
Anticipo (días umbral/divisor), antes fijos en `core.repos.liquidaciones`."""

from __future__ import annotations

import core.parametros as p
from core.repos import liquidaciones as lq


def test_get_liquidaciones_params_defaults_sin_configurar(app_db):
    d = p.get_liquidaciones_params()
    assert d["iess_personal_pct"] == lq.IESS_PCT
    assert d["fondo_reserva_pct"] == lq.FONDO_RESERVA_PCT
    assert d["region_defecto"] == "COSTA"
    assert d["anticipo_dias_umbral"] == lq.ANTICIPO_DIAS_UMBRAL
    assert d["anticipo_divisor"] == lq.ANTICIPO_DIVISOR


def test_set_liquidaciones_params_solo_cambia_lo_pasado(app_db):
    p.set_liquidaciones_params(iess_personal_pct=0.10)
    d = p.get_liquidaciones_params()
    assert d["iess_personal_pct"] == 0.10
    assert d["fondo_reserva_pct"] == lq.FONDO_RESERVA_PCT  # sin tocar

    p.set_liquidaciones_params(region_defecto="sierra")
    d = p.get_liquidaciones_params()
    assert d["region_defecto"] == "SIERRA"  # normalizada a mayúsculas
    assert d["iess_personal_pct"] == 0.10  # el cambio anterior se conserva


def test_config_liquidacion_usa_los_parametros_guardados(app_db):
    p.set_liquidaciones_params(
        iess_personal_pct=0.11, fondo_reserva_pct=0.09,
        anticipo_dias_umbral=60, anticipo_divisor=4.0, region_defecto="sierra",
    )
    cfg = p.config_liquidacion()
    assert cfg.region == "SIERRA"
    assert cfg.iess_personal_pct == 0.11
    assert cfg.fondo_reserva_pct == 0.09
    assert cfg.anticipo_dias_umbral == 60
    assert cfg.anticipo_divisor == 4.0


def test_config_liquidacion_region_explicita_gana_a_la_guardada(app_db):
    p.set_liquidaciones_params(region_defecto="sierra")
    cfg = p.config_liquidacion("COSTA")
    assert cfg.region == "COSTA"


def test_config_liquidacion_sin_nada_guardado_usa_defaults(app_db):
    cfg = p.config_liquidacion()
    assert cfg.region == "COSTA"
    assert cfg.iess_personal_pct == lq.IESS_PCT
    assert cfg.fondo_reserva_pct == lq.FONDO_RESERVA_PCT
    assert cfg.anticipo_dias_umbral == lq.ANTICIPO_DIAS_UMBRAL
    assert cfg.anticipo_divisor == lq.ANTICIPO_DIVISOR
