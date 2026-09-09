"""core/repos/faltas.py — orquestación de escritura (dry_run, sin SQL Server).

Verifica las decisiones sobre los bugs del legado tomadas en el trasplante:
bug #2 replicado (+1 día), bug #3 corregido (clamp siempre), bug #4 corregido
(levantamiento resta).
"""

from __future__ import annotations

import pytest

from core.repos import faltas as repo


@pytest.fixture(autouse=True)
def _sin_sqlserver(monkeypatch):
    """Ningún test de este módulo debe tocar SQL Server."""
    monkeypatch.setattr(repo, "_seccion_empleado", lambda emp: "SEC1")


def _sin_registro(monkeypatch):
    monkeypatch.setattr(repo, "_registro_existente", lambda emp, fv: None)


def _con_registro(monkeypatch, totaus, observ="previo"):
    monkeypatch.setattr(repo, "_registro_existente", lambda emp, fv: {"TOTAUS": totaus, "OBSERV": observ})


def _horas(monkeypatch, h25=0, h50=0, h100=0):
    monkeypatch.setattr(repo, "horas_extra_empleado",
                        lambda emp: {"HOR25": h25, "HOR50": h50, "HOR100": h100})


# ── falta simple ────────────────────────────────────────────────────────────

def test_falta_simple_insertar(monkeypatch):
    _sin_registro(monkeypatch)
    v = repo.registrar("1001", "FALTA", 1, "05/09/2026", 2026, 9, "llegó tarde")
    assert v.ok and v.accion == "INSERTADO"
    assert v.horas == 16
    assert v.observ == "FALTA: 16h (2d) - 05/09/2026 - llegó tarde"


def test_falta_acumula_y_alerta(monkeypatch):
    _con_registro(monkeypatch, totaus=48)
    v = repo.registrar("1001", "FALTA", 1, "05/09/2026", 2026, 9, "otra")
    assert v.accion == "ACTUALIZADO"
    assert v.alerta["nivel"] == "ya_supero"
    assert v.observ.startswith("previo + FALTA: 16h")


# ── suspensión con descuento (bug #2 y #3) ──────────────────────────────────

def test_suspension_dias_mas_uno(monkeypatch):
    _sin_registro(monkeypatch)
    _horas(monkeypatch, 0, 0, 0)
    v = repo.registrar("1001", "SUSPENSIÓN", 0, "01/09/2026", 2026, 9, "x",
                       descontar_horas_extra=False)
    # 01/09 -> 30/09 = 30 días (bug #2: +1). horas = 30*8 = 240
    assert v.horas == 240
    assert "30 días (240h)" in v.observ


def test_suspension_descuento_siempre_acotado(monkeypatch):
    # bug #3 CORREGIDO: suspensión larga, porcentaje > 100, pero el descuento
    # nunca supera las horas disponibles.
    _sin_registro(monkeypatch)
    _horas(monkeypatch, h25=10, h50=20, h100=5)
    v = repo.registrar("1001", "SUSPENSIÓN", 0, "01/08/2026", 2026, 9, "larga")
    # del 01/08 al 30/09 => 61 días => pct = int(61/30*100) = 203
    assert v.descuento["pct"] > 100
    assert v.descuento["HOR25"] == 10   # acotado a lo disponible
    assert v.descuento["HOR50"] == 20
    assert v.descuento["HOR100"] == 5


# ── levantamiento de suspensión (bug #4) ────────────────────────────────────

def test_levantamiento_resta_horas(monkeypatch):
    _con_registro(monkeypatch, totaus=200)
    v = repo.registrar("1001", "LEVANTAMIENTO SUSPENSIÓN", 3, "10/09/2026", 2026, 9, "vuelve")
    assert v.ok and v.accion == "ACTUALIZADO"
    assert v.horas == 24
    # bug #4 CORREGIDO: resta -> el after registra -24
    assert v.detalle.startswith("LEVANTAMIENTO SUSPENSIÓN · 24h")


def test_levantamiento_sin_registro_previo_falla(monkeypatch):
    _sin_registro(monkeypatch)
    v = repo.registrar("1001", "LEVANTAMIENTO SUSPENSIÓN", 3, "10/09/2026", 2026, 9, "x")
    assert not v.ok and "restar" in v.error


# ── validaciones ───────────────────────────────────────────────────────────

def test_fecha_evento_invalida(monkeypatch):
    _sin_registro(monkeypatch)
    v = repo.registrar("1001", "FALTA", 1, "no-fecha", 2026, 9, "x")
    assert not v.ok and "Fecha del evento" in v.error


def test_observacion_muy_larga(monkeypatch):
    _sin_registro(monkeypatch)
    v = repo.registrar("1001", "PERMISO", 1, "05/09/2026", 2026, 9, "z" * 300)
    assert not v.ok and "255" in v.error


# ── restas: solo prepara el resumen en dry_run ─────────────────────────────

def test_aplicar_restas_dry_run():
    res = repo.aplicar_restas([
        {"ESTADO": "OK", "EMPLEADO": "1001", "HOR50_NUEVO": 10, "HOR100_NUEVO": 0},
        {"ESTADO": "REVISION", "EMPLEADO": "1002"},
    ])
    assert res == {"aplicables": 1, "aplicados": 0, "omitidos": 1}
