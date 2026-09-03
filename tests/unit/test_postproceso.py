from core.datos.postproceso import (
    consolidar_conceptos,
    construir_empleado_nomina,
    dias_del_periodo,
)
from tests.fixtures import golden


def test_consolida_y_suma_repetidos():
    c = consolidar_conceptos(golden.MOVIMIENTOS_GOLDEN)
    assert c["SUELDO"] == 800.0
    assert c["PRESTAMOS_COMPANIA"] == 150.0  # 120 + 30
    assert c["CONCEPTO_333"] == 12.0


def test_ignora_clases_ignoradas():
    c = consolidar_conceptos([{"clase": 105, "valor": 999.0, "asentado": True}])
    assert c == {}


def test_decimo_solo_si_asentado():
    movs = [
        {"clase": 107, "valor": 100.0, "asentado": False},
        {"clase": 108, "valor": 50.0, "asentado": True},
    ]
    c = consolidar_conceptos(movs)
    assert "DECIMO_TERCERA" not in c
    assert c["DECIMO_CUARTA"] == 50.0


def test_dias_desde_clase_101():
    assert dias_del_periodo(golden.MOVIMIENTOS_GOLDEN) == 28.0
    assert dias_del_periodo([{"clase": 100, "valor": 1.0}]) == 30.0  # default


def test_construir_empleado_nomina_totales():
    emp = construir_empleado_nomina(golden.crudos_sqlserver())
    assert emp.empleado == "1012"
    assert emp.cedula == golden.CEDULA_ESPERADA
    assert emp.cargo == "GUARDIA"
    assert emp.depto == "OPERACIONES"
    assert emp.dias == golden.DIAS_ESPERADOS
    assert emp.total_ingresos == golden.INGRESOS_ESPERADOS
    assert emp.total_egresos == golden.EGRESOS_ESPERADOS
    assert emp.total_recibir == golden.RECIBIR_ESPERADO


def test_to_series_aplana_conceptos():
    serie = construir_empleado_nomina(golden.crudos_sqlserver()).to_series()
    assert serie["SUELDO"] == 800.0
    assert serie["TOTAL_RECIBIR"] == golden.RECIBIR_ESPERADO
    assert serie["CEDULA"] == golden.CEDULA_ESPERADA


def test_cargo_sin_traduccion_usa_codigo():
    crudos = golden.crudos_sqlserver()
    crudos.cargo_codigo = "99"  # no está en el catálogo
    emp = construir_empleado_nomina(crudos)
    assert emp.cargo == "99"
