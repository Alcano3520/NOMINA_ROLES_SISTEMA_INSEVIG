"""Registrador: cálculo de cuotas y catálogo de clases. Portado de
REGISTRAR_PRESTAMOS_UNIFICADO.pyw — debe coincidir.
"""

import datetime as dt

from core.repos import registrador as rg


def test_cuotas_tradicional_suman_el_total():
    c = rg.cuotas_tradicional(1000.0, 3, dt.date(2026, 7, 10))
    assert [x.secuencia for x in c] == [1, 2, 3]
    assert round(sum(x.valor for x in c), 2) == 1000.0
    # el ajuste va en la primera cuota
    assert c[0].valor == 333.34
    # vencen el último día de cada mes
    assert c[0].fecha_vencimiento == "2026-07-31"
    assert c[1].fecha_vencimiento == "2026-08-31"
    assert c[2].fecha_vencimiento == "2026-09-30"


def test_cuotas_por_valor_respeta_carga_existente():
    cuotas, aviso = rg.cuotas_por_valor(
        1000.0, 300.0, dt.date(2026, 7, 1), proyeccion_existente={(2026, 8): 100.0}
    )
    valores = [x.valor for x in cuotas]
    assert valores == [300.0, 200.0, 300.0, 200.0]  # agosto solo admite 200
    assert round(sum(valores), 2) == 1000.0
    assert aviso == ""


def test_cuotas_por_valor_sin_carga_previa():
    cuotas, aviso = rg.cuotas_por_valor(1000.0, 250.0, dt.date(2026, 7, 1))
    assert [x.valor for x in cuotas] == [250.0, 250.0, 250.0, 250.0]
    assert aviso == ""


def test_clases_simplificadas_y_nombres():
    assert rg.CLASE_PRESTAMO == "205"
    assert rg.CLASES_SIMPLIFICADAS["203"]["concepto"] == "MULTAS"
    assert rg.CLASES_SIMPLIFICADAS["203"]["tipo"] == "EGR"
    assert rg.CLASES_SIMPLIFICADAS["110"]["tipo"] == "ING"
    assert rg.NOMBRE_CLASE["205"] == "Préstamo"


def test_registrar_prestamo_dry_run_valida_suma():
    from core.repos.registrador import Cuota

    ok = rg.registrar_prestamo(
        "1012", 600.0, "2026-07-01", "test",
        [Cuota(1, "2026-07-31", 300.0), Cuota(2, "2026-08-31", 300.0)],
        usuario="t", roles=set(), dry_run=True,
    )
    assert ok.ok and "2 cuotas" in ok.detalle
    mal = rg.registrar_prestamo(
        "1012", 600.0, "2026-07-01", "test",
        [Cuota(1, "2026-07-31", 100.0)],
        usuario="t", roles=set(), dry_run=True,
    )
    assert not mal.ok


def test_registrar_movimiento_dry_run():
    r = rg.registrar_movimiento("1012", "203", 25.0, "2026-07-01", "atraso", usuario="t", roles=set(), dry_run=True)
    assert r.ok and "Multa" in r.detalle
    mal = rg.registrar_movimiento("1012", "999", 25.0, "2026-07-01", "", usuario="t", roles=set(), dry_run=True)
    assert not mal.ok
