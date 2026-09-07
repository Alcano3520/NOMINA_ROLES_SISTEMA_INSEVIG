"""Clasificación de CLASE de scripts/validar_conceptos."""

from __future__ import annotations

from scripts.validar_conceptos import clasificar_clase


def test_clase_mapeada_y_en_total_es_ok():
    estado, se_pierde = clasificar_clase(100)  # SUELDO
    assert estado.startswith("OK") and se_pierde is False


def test_clase_ignorada_a_proposito():
    for c in (101, 105, 126, 199):
        estado, se_pierde = clasificar_clase(c)
        assert "IGNORADA" in estado and se_pierde is False


def test_clase_sin_mapear_se_pierde():
    estado, se_pierde = clasificar_clase(9999)
    assert "SIN MAPEAR" in estado and se_pierde is True


def test_clase_mapeada_fuera_del_total_se_pierde():
    # CLASE 201/217 -> "ANTICIPOS_OTROS", que SÍ está en CAMPOS_EGRESO -> OK.
    # Construyo un caso sintético: si alguna CLASE mapea a un nombre que no está
    # en los totales, se marca. (Hoy todas las mapeadas están en el total; el
    # test documenta el comportamiento esperado si eso cambiara.)
    import scripts.validar_conceptos as vc

    vc.CLASE_A_CONCEPTO[777] = "CONCEPTO_RARO_NO_EN_TOTAL"
    try:
        estado, se_pierde = clasificar_clase(777)
        assert "fuera del total" in estado and se_pierde is True
    finally:
        del vc.CLASE_A_CONCEPTO[777]
