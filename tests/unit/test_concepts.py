"""El mapa de conceptos es "NO CAMBIAR": estos tests lo fijan.

Cualquier cambio intencional al mapa debe actualizar estas expectativas
explícitamente (y re-validarse contra un período real vía la prueba de
integración `test_concepts_cubre_periodo_real`, aún por escribir en Fase 1).
"""

from core import concepts


def test_claves_criticas_no_cambian():
    esperado = {
        100: "SUELDO",
        102: "BONIFICACION",
        104: "FONDO_RESERVA",
        107: "DECIMO_TERCERA",
        108: "DECIMO_CUARTA",
        200: "APORT_IESS",
        202: "ANTICIPO_SUELDO",
        203: "MULTAS",
        204: "PRESTAMOS_QUIROGRAFARIOS",
        205: "PRESTAMOS_COMPANIA",
    }
    for clase, nombre in esperado.items():
        assert concepts.CLASE_A_CONCEPTO[clase] == nombre


def test_es_superconjunto_de_la_variante_base_de_obtener_datos():
    # La variante "estrecha" histórica de shared/obtener_datos.py
    base = {
        100, 102, 104, 107, 108, 110, 111, 113, 114, 115, 120,
        200, 201, 202, 203, 204, 205, 206, 207, 217, 218, 219, 250,
    }
    assert base <= set(concepts.CLASE_A_CONCEPTO)


def test_clases_ignoradas_y_dias():
    assert concepts.CLASES_IGNORADAS == frozenset({105, 126, 199})
    assert concepts.CLASE_DIAS == 101
    assert 101 not in concepts.CLASE_A_CONCEPTO  # 101 no es concepto monetario


def test_ingresos_y_egresos_referencian_conceptos_reales():
    nombres = set(concepts.CLASE_A_CONCEPTO.values())
    assert set(concepts.CAMPOS_INGRESO) <= nombres
    assert set(concepts.CAMPOS_EGRESO) <= nombres
    # ingreso y egreso son disjuntos
    assert not (set(concepts.CAMPOS_INGRESO) & set(concepts.CAMPOS_EGRESO))


def test_decimos_condicionados_por_asentado():
    assert concepts.CONCEPTOS_CONDICIONADOS_ASENTADO == frozenset(
        {"DECIMO_TERCERA", "DECIMO_CUARTA"}
    )


def test_concepto_de_clase_desconocida():
    assert concepts.concepto_de_clase(9999) == "CONCEPTO_9999"
