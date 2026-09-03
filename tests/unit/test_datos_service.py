"""Prueba central de la de-duplicación: SQL Server y Supabase, dados datos
equivalentes, deben producir el MISMO `EmpleadoNomina`.

Es la regresión que protege contra que las dos rutas vuelvan a divergir (varios
commits recientes del legado parcheaban a mano esa divergencia).
"""

import pytest

from core.datos.service import datos_empleado
from tests.fixtures import golden


def test_sqlserver_y_supabase_producen_el_mismo_resultado():
    fuentes = golden.fuentes_fake(golden.crudos_sqlserver(), golden.crudos_supabase())
    por_sql = datos_empleado(golden.PERIODO, "1012", "sqlserver", _fuentes=fuentes)
    por_sup = datos_empleado(golden.PERIODO, "1012", "supabase", _fuentes=fuentes)
    assert por_sql is not None
    assert por_sql == por_sup


def test_devuelve_none_si_no_encuentra():
    fuentes = golden.fuentes_fake(None, None)
    assert datos_empleado(golden.PERIODO, "0000", "sqlserver", _fuentes=fuentes) is None


def test_fuente_invalida():
    with pytest.raises(ValueError, match="Fuente desconocida"):
        datos_empleado(golden.PERIODO, "1012", "oracle", _fuentes=golden.fuentes_fake(None, None))


def test_valores_consolidados_por_la_fachada():
    fuentes = golden.fuentes_fake(golden.crudos_sqlserver(), golden.crudos_supabase())
    emp = datos_empleado(golden.PERIODO, "1012", "supabase", _fuentes=fuentes)
    assert emp.total_recibir == golden.RECIBIR_ESPERADO
    assert emp.conceptos["PRESTAMOS_COMPANIA"] == 150.0
