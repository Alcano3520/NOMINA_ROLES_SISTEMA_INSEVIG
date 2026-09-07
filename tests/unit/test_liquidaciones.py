"""Módulo 9: fórmulas legales de liquidación (Ecuador). Portadas de
`nucleo_modular` (LIQUIDACIONES_SISTEMA_INSEVIG), extracción fiel y ya
probada del `.pyw` que la empresa usa hoy en producción
(`Generador_Liquidaciones_INSEVIG.pyw`) — deben coincidir exactamente.

Nota histórica: la primera versión de este archivo portaba
`Liquidaciones_generador_CON_VACACIONES.pyw` (versión vieja/deprecada), con
un ancla de vacaciones en el día 1 del mes y un tope de 2 periodos para la
Décima Cuarta. Los tests de `test_periodos_vacaciones_por_mes_de_ingreso` y
`test_periodo_decima_tercera_dic_a_nov` se actualizaron para reflejar las
correcciones ya validadas en producción (ver docstrings de
`core.repos.liquidaciones.periodos_vacaciones`/`periodos_decima_tercera`).
"""

import datetime as dt

from core.excel.liquidaciones_builders import liquidaciones_xlsx
from core.repos import liquidaciones as lq


def test_dias360_como_excel():
    assert lq.dias360(dt.date(2024, 1, 15), dt.date(2024, 2, 15)) == 30
    assert lq.dias360(dt.date(2023, 2, 4), dt.date(2026, 2, 4)) == 3 * 360
    assert lq.dias360(dt.date(2024, 1, 31), dt.date(2024, 3, 31)) == 60


def test_periodos_vacaciones_por_mes_de_ingreso():
    # Ingresó 04/02/2023: el periodo ancla en el DÍA EXACTO de ingreso (04),
    # no en el día 1 del mes -- y como las vacaciones no caducan en Ecuador,
    # se devuelven TODOS los periodos pendientes desde el ingreso, no solo
    # los últimos 2 (el último queda recortado a la fecha de salida).
    p = lq.periodos_vacaciones(dt.date(2023, 2, 4), dt.date(2026, 3, 15))
    assert p == [
        (dt.date(2023, 2, 4), dt.date(2024, 2, 3)),
        (dt.date(2024, 2, 4), dt.date(2025, 2, 3)),
        (dt.date(2025, 2, 4), dt.date(2026, 2, 3)),
        (dt.date(2026, 2, 4), dt.date(2026, 3, 15)),  # periodo en curso, recortado a la salida
    ]
    # sale ANTES del aniversario (04/02) -> el periodo en curso llega solo
    # hasta la fecha de salida, no hasta el aniversario completo.
    p2 = lq.periodos_vacaciones(dt.date(2023, 2, 4), dt.date(2026, 1, 20))
    assert p2[-1] == (dt.date(2025, 2, 4), dt.date(2026, 1, 20))


def test_periodo_decima_tercera_dic_a_nov():
    # El periodo ACTUAL (en curso) se recorta a la fecha de salida -- no se
    # cuentan movimientos de meses que todavía no pasaron.
    p = lq.periodos_decima_tercera(dt.date(2022, 1, 1), dt.date(2026, 3, 10))
    assert p[-1] == (dt.date(2025, 12, 1), dt.date(2026, 3, 10), False)  # pago 24/12/26 > salida


def test_decima_cuarta_costa_vs_sierra():
    costa = lq.periodos_decima_cuarta(dt.date(2024, 1, 1), dt.date(2026, 5, 1), "COSTA")
    assert (dt.date(2025, 3, 1), dt.date(2026, 2, 28), True) in costa  # pagado 15/03/26 < 01/05
    sierra = lq.periodos_decima_cuarta(dt.date(2024, 1, 1), dt.date(2026, 5, 1), "SIERRA")
    assert any(i.month == 8 for i, _, _ in sierra)


def test_decima_cuarta_no_infla_con_mucha_antiguedad():
    # Corregido: antes se recorrían TODOS los años desde el ingreso -- para
    # alguien con 14 años de antigüedad esto sumaba ~13 periodos de décima
    # cuarta (todos ya pagados año a año en su momento) en vez de solo los
    # últimos 2. Caso real documentado: inflaba ~$5895 en vez de los ~$220
    # del único periodo realmente pendiente.
    p = lq.periodos_decima_cuarta(dt.date(2012, 1, 1), dt.date(2026, 5, 1), "COSTA")
    assert len(p) == 2


def test_decima_tercera_recorta_reingreso():
    # Reingreso a mitad del periodo calendario (01/12 -> 30/11): el inicio
    # real a considerar es la fecha de ingreso ACTUAL, no el 01/12 -- si no,
    # se suma sueldo de un ingreso anterior ya liquidado por separado.
    p = lq.periodos_decima_tercera(dt.date(2026, 2, 1), dt.date(2026, 6, 1))
    assert p == [(dt.date(2026, 2, 1), dt.date(2026, 6, 1), False)]


def test_desahucio_menos_de_un_anio_es_cero():
    assert lq.desahucio(dt.date(2025, 6, 1), dt.date(2026, 1, 1), 800.0) == 0.0  # 214 días


def test_desahucio_formula():
    # 3 años completos, sueldo 800 -> (800/4)*3 = 600
    d = lq.desahucio(dt.date(2023, 1, 1), dt.date(2026, 2, 1), 800.0)
    assert d == 600.0


def test_indemnizacion_despido():
    # motivo con DESPIDO, <3 años -> 3×sueldo
    assert lq.indemnizacion_despido(dt.date(2025, 1, 1), dt.date(2026, 6, 1), 800.0, "DESPIDO INTEMPESTIVO") == 2400.0
    # >=3 años -> años×sueldo
    assert lq.indemnizacion_despido(dt.date(2020, 1, 1), dt.date(2026, 6, 1), 800.0, "despido") == 6 * 800.0
    # motivo normal -> 0
    assert lq.indemnizacion_despido(dt.date(2020, 1, 1), dt.date(2026, 6, 1), 800.0, "RENUNCIA VOLUNTARIA") == 0.0


def test_procesar_empleado_nunca_autocalcula_indem_despido(monkeypatch):
    """Verificado contra Generador_Liquidaciones_INSEVIG.pyw: "Indemnización
    por Despido" es un campo MANUAL editable (default $0) en la vista
    previa, nunca disparado por el texto del motivo -- ni existe una
    función equivalente en nucleo_modular. Una versión anterior de este
    archivo llamaba a indemnizacion_despido() automáticamente desde
    procesar_empleado (copiado por error de Liquidaciones_generador_
    SUPABASE.py, una variante paralela que el .pyw real no usa), sumando de
    más sin revisión humana en cualquier liquidación con motivo DESPIDO/
    INTEMPESTIVO -- bug real, corregido: procesar_empleado ya no llama a
    indemnizacion_despido() en absoluto, la función queda disponible como
    utilidad standalone únicamente."""
    emp = {
        "EMPLEADO": "999", "APELLIDOS": "PEREZ", "NOMBRES": "JUAN", "CEDULA": "0920116811",
        "SUELDO": 800.0, "CARGO": "GUARDIA", "DEPTO": "OPERACIONES", "SECCION": "MATRIZ",
        "FECHA_ING": "2015-01-01", "FECHA_SAL": "2026-06-01",
        "ESTADO": "A", "HOR25": 0, "HOR50": 0, "HOR100": 0,
    }
    monkeypatch.setattr(lq, "_empleado", lambda cedula, fuente: emp)

    def _raise():
        raise RuntimeError("sin conexión")
    monkeypatch.setattr(lq.supabase_client, "get_client", _raise)
    monkeypatch.setattr(lq, "movimientos_mes", lambda cod, anio, mes, fuente: ([], "RPINGDES"))
    cfg = lq.ConfigLiquidacion()

    con = lq.procesar_empleado(
        "0920116811", "2026-06-01", "DESPIDO INTEMPESTIVO", lq.FUENTE_SUPABASE, cfg,
    )
    assert con.error == ""
    assert con.campos["DESAHUCIO"]  # el desahucio sí se calcula normalmente
    assert con.campos.get("INDEM_DESPIDO", 0.0) == 0.0


def test_sbu_por_anio_fallback():
    cfg = lq.ConfigLiquidacion()
    assert cfg.sbu(2026) == 482.0
    assert cfg.sbu(1999) == cfg.sbu(2020)   # antes del más antiguo
    assert cfg.sbu(2099) == cfg.sbu(2027)   # después del más reciente


def test_parse_linea():
    assert lq._parse_linea("0920116811, 15/02/2026, DESPIDO") == ("0920116811", "15/02/2026", "DESPIDO", "")
    assert lq._parse_linea("0920116811, 15/02/2026") == ("0920116811", "15/02/2026", "", "")
    assert lq._parse_linea("092, 15/02/2026, RENUNCIA, 01/01/2020") == ("092", "15/02/2026", "RENUNCIA", "01/01/2020")
    assert lq._parse_linea("solo_esto") is None


def test_vacaciones_pagadas_gozadas_degradan_sin_supabase(monkeypatch):
    """Si Supabase no responde/no está configurado, se devuelve None (no un
    dict vacío) -- el llamador no debe interpretar esto como "nada pagado"."""
    def _sin_conexion():
        raise RuntimeError("sin conexión")

    monkeypatch.setattr(lq.supabase_client, "get_client", _sin_conexion)
    assert lq.vacaciones_pagadas("0920116811") is None
    assert lq.vacaciones_gozadas("0920116811") is None


def test_total_vacaciones_sin_verificacion_solo_calcula_el_ultimo(monkeypatch):
    """Sin poder verificar contra vac_registros, solo se autocalcula el
    periodo MÁS RECIENTE -- cualquier periodo más antiguo con saldo se deja
    fuera (posible doble pago) y se alerta para revisión manual."""
    monkeypatch.setattr(lq, "vacaciones_pagadas", lambda cedula: None)
    monkeypatch.setattr(lq, "vacaciones_gozadas", lambda cedula: None)
    periodos = [
        (dt.date(2023, 2, 4), dt.date(2024, 2, 3)),
        (dt.date(2024, 2, 4), dt.date(2025, 2, 3)),
        (dt.date(2025, 2, 4), dt.date(2026, 2, 3)),
    ]
    total, alertas, detalle = lq.total_vacaciones_a_pagar("0920116811", [500.0, 500.0, 500.0], periodos)
    assert total == 500.0  # solo el último periodo
    assert len(alertas) == 2  # los 2 periodos más antiguos, con saldo, alertados
    assert detalle[0].estado == "SIN_VERIFICAR"
    assert detalle[-1].estado == "PENDIENTE"


def test_total_vacaciones_descarta_periodo_ya_pagado(monkeypatch):
    monkeypatch.setattr(lq, "vacaciones_pagadas", lambda cedula: {"2025-2026": True})
    monkeypatch.setattr(lq, "vacaciones_gozadas", lambda cedula: {})
    periodos = [(dt.date(2025, 2, 4), dt.date(2026, 2, 3))]
    total, alertas, detalle = lq.total_vacaciones_a_pagar("0920116811", [500.0], periodos)
    assert total == 0.0
    assert detalle[0].estado == "PAGADO"
    assert detalle[0].incluido is False


def test_total_vacaciones_prorratea_goce_parcial(monkeypatch):
    # 3 de los 15 días base ya gozados -> se paga (15-3)/15 = 12/15 del bruto.
    monkeypatch.setattr(lq, "vacaciones_pagadas", lambda cedula: {})
    monkeypatch.setattr(lq, "vacaciones_gozadas", lambda cedula: {"2025-2026": 3})
    periodos = [(dt.date(2025, 2, 4), dt.date(2026, 2, 3))]
    total, alertas, detalle = lq.total_vacaciones_a_pagar("0920116811", [300.0], periodos)
    assert total == 240.0  # 300 * 12/15
    assert detalle[0].estado == "GOZADO_PARCIAL"
    assert len(alertas) == 1


def test_total_vacaciones_suma_todos_los_periodos_pendientes(monkeypatch):
    """Las vacaciones NO caducan: con verificación disponible y ningún
    periodo pagado/gozado, se suman TODOS (no solo los últimos 2)."""
    monkeypatch.setattr(lq, "vacaciones_pagadas", lambda cedula: {})
    monkeypatch.setattr(lq, "vacaciones_gozadas", lambda cedula: {})
    periodos = [
        (dt.date(2023, 2, 4), dt.date(2024, 2, 3)),
        (dt.date(2024, 2, 4), dt.date(2025, 2, 3)),
        (dt.date(2025, 2, 4), dt.date(2026, 2, 3)),
    ]
    total, alertas, _detalle = lq.total_vacaciones_a_pagar("0920116811", [100.0, 200.0, 300.0], periodos)
    assert total == 600.0
    assert alertas == []


def test_decimo_anterior_excluido_por_defecto_en_el_total():
    """Verificado contra Generador_Liquidaciones_INSEVIG.pyw
    (_parsear_entrada_cedulas, _procesar_empleado): el décimo ANTERIOR está
    excluido del total por defecto en las dos pantallas reales -- en modo
    lote el campo va hardcodeado en False (no se puede activar, decisión
    explícita del usuario para no colar un décimo ya pagado en un proceso
    masivo) y en modo individual la casilla nace desmarcada. Una versión
    anterior de este archivo tenía el default en True, lo que hacía que
    procesar_lote() (que no pasa el argumento) incluyera de más el décimo
    anterior en cada liquidación de lote -- corregido."""
    import inspect

    firma = inspect.signature(lq.procesar_empleado)
    assert firma.parameters["incluir_dec13_anterior"].default is False
    assert firma.parameters["incluir_dec14_anterior"].default is False


def _emp_ejemplo():
    return {
        "EMPLEADO": "999", "APELLIDOS": "PEREZ", "NOMBRES": "JUAN", "CEDULA": "0920116811",
        "SUELDO": 500.0, "CARGO": "GUARDIA", "DEPTO": "OPERACIONES", "SECCION": "MATRIZ",
        "FECHA_ING": "2020-01-15", "FECHA_SAL": "2026-06-15",
        "ESTADO": "A", "HOR25": 0, "HOR50": 0, "HOR100": 0,
    }


def _sin_supabase(monkeypatch):
    def _raise():
        raise RuntimeError("sin conexión")
    monkeypatch.setattr(lq.supabase_client, "get_client", _raise)


def test_incluir_sueldo_false_excluye_rol_del_mes_de_salida_no_el_sueldo_base(monkeypatch):
    """Verificado contra Generador_Liquidaciones_INSEVIG.pyw (constante
    CAMPOS_ROL_MES): con incluir_sueldo=False se excluyen Sueldo,
    sobretiempos y los descuentos del MES DE SALIDA -- pero sueldo_base
    (RPEMPLEA, columna "Sueldo"/REMUNERACION) no se ve afectado."""
    monkeypatch.setattr(lq, "_empleado", lambda cedula, fuente: _emp_ejemplo())
    _sin_supabase(monkeypatch)

    def _movs(cod, anio, mes, fuente):
        if (anio, mes) == (2026, 6):
            return ([
                {"clase": 100, "valor": 500.0, "dias": 30, "codigo": ""},
                {"clase": 203, "valor": 20.0, "dias": None, "codigo": ""},
            ], "RPINGDES")
        return ([], "RPINGDES")

    monkeypatch.setattr(lq, "movimientos_mes", _movs)
    cfg = lq.ConfigLiquidacion()

    con = lq.procesar_empleado(
        "0920116811", "2026-06-15", "RENUNCIA VOLUNTARIA", lq.FUENTE_SUPABASE, cfg,
        incluir_sueldo=False,
    )
    assert con.error == ""
    assert con.campos["SUELDO"] == 0.0
    assert con.campos["MULTAS"] == 0.0
    assert con.sueldo_base == 500.0  # sin afectar


def test_usar_ingresos_reales_desahucio_usa_promedio_del_ultimo_periodo(monkeypatch):
    """Verificado contra Generador_Liquidaciones_INSEVIG.pyw (comentario
    "CÁLCULO DE DESAHUCIO"): con usar_ingresos_reales_desahucio=True, la base
    mensual del desahucio deja de ser el sueldo básico y pasa a ser el total
    del último periodo de vacaciones dividido por los MESES que ese periodo
    realmente abarca (no siempre 12)."""
    emp = _emp_ejemplo()
    emp["FECHA_ING"] = "2015-01-15"  # varios periodos completos de antigüedad
    monkeypatch.setattr(lq, "_empleado", lambda cedula, fuente: emp)
    _sin_supabase(monkeypatch)
    monkeypatch.setattr(lq, "movimientos_mes", lambda cod, anio, mes, fuente: ([], "RPINGDES"))
    # El último periodo de vacaciones (anclado en el ingreso, 15/01) para una
    # salida el 15/06/2026 es 15/01/2026 -> 15/06/2026: 6 meses exactos.
    monkeypatch.setattr(lq, "_suma_base", lambda cod, i, f, fuente: 1200.0)
    cfg = lq.ConfigLiquidacion()

    con_default = lq.procesar_empleado(
        "0920116811", "2026-06-15", "RENUNCIA VOLUNTARIA", lq.FUENTE_SUPABASE, cfg,
    )
    con_reales = lq.procesar_empleado(
        "0920116811", "2026-06-15", "RENUNCIA VOLUNTARIA", lq.FUENTE_SUPABASE, cfg,
        usar_ingresos_reales_desahucio=True,
    )
    assert con_default.error == "" and con_reales.error == ""
    # Default: base = sueldo básico (500.0)
    assert con_default.campos["DESAHUCIO"] == lq.desahucio(
        dt.date(2015, 1, 15), dt.date(2026, 6, 15), 500.0)
    # usar_ingresos_reales_desahucio: base = 1200.0 / 6 meses = 200.0
    assert con_reales.campos["DESAHUCIO"] == lq.desahucio(
        dt.date(2015, 1, 15), dt.date(2026, 6, 15), 200.0)
    assert con_reales.campos["DESAHUCIO"] != con_default.campos["DESAHUCIO"]


def test_excel_liquidaciones_valido():
    import io

    import openpyxl

    liq = lq.Liquidacion(
        empleado="1012", nombre="PEREIRA JUAN", cedula="0920116811", cargo="01",
        depto="10", seccion="", sueldo_base=800.0, fecha_ingreso="2023-01-01",
        fecha_salida="2026-02-01", motivo_salida="RENUNCIA", dias_trabajados=1127,
        campos={"TOTAL_INGRESOS": 1500.0, "TOTAL_DESCUENTOS": 200.0, "TOTAL_A_RECIBIR": 1300.0,
                "DESAHUCIO": 600.0, "VACACIONES_CALCULADAS": 400.0},
    )
    data = liquidaciones_xlsx([liq])
    wb = openpyxl.load_workbook(io.BytesIO(data))
    ws = wb["FORMATO"]
    headers = [c.value for c in ws[1]]
    assert "MOTIVO DE SALIDA" in headers
    assert "INDEM. DESPIDO" in headers
    assert "TOTAL VALORES A LIQUIDAR" in headers
    assert ws.max_row == 2


def _liq_ejemplo(**overrides) -> "lq.Liquidacion":
    base = dict(
        empleado="1012", nombre="PEREIRA JUAN", cedula="0920116811",
        cargo="GUARDIA", depto="OPERACIONES", seccion="SEC1", sueldo_base=460.0,
        fecha_ingreso="2020-03-15", fecha_salida="2026-06-30", motivo_salida="RENUNCIA VOLUNTARIA",
        dias_trabajados=2298, apellidos="PEREIRA", nombres="JUAN",
        campos={
            "SUELDO": 460.0, "HORAS_25": 10, "HORAS_50": 0, "HORAS_100": 0,
            "VAL_SOBT_25": 15.6, "VAL_SOBT_50": 0.0, "VAL_SOBT_100": 0.0,
            "FONDO_RESERVA": 38.3, "MANIOBRAS": 0.0, "MOVILIZACION": 0.0,
            "REEMBOLSOS": 0.0, "BONIFICACION": 0.0,
            "VACACIONES_ANTERIOR": 200.0, "VACACIONES_ULTIMO": 220.0, "VACACIONES_CALCULADAS": 18.33,
            "DECIMA_TERCERA_ANTERIOR": 38.3, "DECIMA_TERCERA_ACTUAL": 38.3,
            "DECIMA_CUARTA_ANTERIOR": 0.0, "DECIMA_CUARTA_ACTUAL": 240.0,
            "DESAHUCIO": 690.0, "INDEM_DESPIDO": 0.0,
            "APORT_IESS": 43.47, "PRESTAMOS_QUIROGRAFARIOS": 0.0, "PRESTAMOS_COMPANIA": 0.0,
            "ANTICIPO_SUELDO": 0.0, "ANTICIPOS_OTROS": 0.0, "ANTICIPOS_SURTIDOS": 0.0,
            "APORT_IESS_CONYUGE": 0.0, "PENSION_ALIMENTICIA": 0.0, "PRESTAMO_HIPOTECARIO": 0.0,
            "IMPUESTO_RENTA": 0.0, "ANTICIPOS_OTROS_L": 0.0, "ANTICIPO_L_DESAHUCIO": 0.0,
            "TOTAL_INGRESOS": 1000.0, "TOTAL_DESCUENTOS": 43.47, "TOTAL_A_RECIBIR": 956.53,
        },
    )
    base.update(overrides)
    return lq.Liquidacion(**base)


def test_clasificar_tipo_liquidacion():
    assert lq.clasificar_tipo_liquidacion("RENUNCIA VOLUNTARIA") == "renuncia"
    assert lq.clasificar_tipo_liquidacion("DESPIDO INTEMPESTIVO") == "despido"
    assert lq.clasificar_tipo_liquidacion("VISTO BUENO") == "visto_bueno"
    assert lq.clasificar_tipo_liquidacion("FIN DE CONTRATO") == "termino_contrato"
    assert lq.clasificar_tipo_liquidacion("FALLECIMIENTO") == "muerte"
    assert lq.clasificar_tipo_liquidacion("JUBILACION") == "jubilacion"
    assert lq.clasificar_tipo_liquidacion(None) == "otro"
    assert lq.clasificar_tipo_liquidacion("motivo raro") == "otro"


def test_mapear_registro_totales_y_horas():
    liq = _liq_ejemplo()
    cfg = lq.ConfigLiquidacion()
    registro = lq._mapear_registro(liq, "generada", cfg, usuario="tester")
    assert registro["empleado_codigo"] == "1012"
    assert registro["empleado_cedula"] == "0920116811"
    assert registro["empleado_apellidos"] == "PEREIRA" and registro["empleado_nombres"] == "JUAN"
    assert registro["tipo_liquidacion"] == "renuncia"
    assert registro["estado"] == "generada"
    assert registro["total_liquido"] == 956.53
    assert registro["decimo_tercero"] == 76.6  # 38.3 + 38.3
    assert registro["horas_25_cantidad"] == 10
    assert registro["horas_25_valor_hora"] == round(15.6 / 10, 2)
    assert registro["created_by"] == "tester" and registro["updated_by"] == "tester"


def test_mapear_registro_sin_usuario_usa_sistema():
    registro = lq._mapear_registro(_liq_ejemplo(), "borrador", lq.ConfigLiquidacion(), usuario="")
    assert registro["created_by"] == "Sistema"
    assert "Simulación" in registro["observaciones"]


def test_construir_conceptos_omite_valores_en_cero():
    conceptos = lq._construir_conceptos(_liq_ejemplo())
    codigos = {c["concepto_codigo"] for c in conceptos}
    assert "SUELDO" in codigos and "DESAHUCIO" in codigos
    assert "MANIOBRAS" not in codigos  # viene en 0.0 -> se omite
    assert all(c["valor_total"] != 0 for c in conceptos)
    assert [c["orden"] for c in conceptos] == list(range(len(conceptos)))


def test_previsualizar_conceptos_es_wrapper_publico():
    liq = _liq_ejemplo()
    assert lq.previsualizar_conceptos(liq) == lq._construir_conceptos(liq)


class _FakeExec:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Encadenable como el cliente real de Supabase (select/eq/or_/order/limit)."""

    def __init__(self, data):
        self._data = data

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def or_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return _FakeExec(self._data)


class _FakeClient:
    def __init__(self, data):
        self._data = data

    def table(self, _nombre):
        return _FakeQuery(self._data)


def test_resumen_liquidaciones_cuenta_por_estado(monkeypatch):
    filas = [
        {"estado": "generada"}, {"estado": "generada"}, {"estado": "pagada"},
        {"estado": "estado_desconocido"},
    ]
    monkeypatch.setattr(lq.supabase_client, "get_client", lambda: _FakeClient(filas))
    resumen = lq.resumen_liquidaciones()
    assert resumen == {"borrador": 0, "generada": 2, "pagada": 1, "anulada": 0}


def test_buscar_empleado_preview_por_cedula_supabase(monkeypatch):
    fila = {
        "cedula": 920116811.0, "empleado": "1012", "apellidos": "PEREIRA", "nombres": "JUAN",
        "cargo": "GUARDIA", "seccion": "SEC1", "fecha_ing": "2020-03-15", "sueldo": 460.0,
    }
    monkeypatch.setattr(lq.supabase_client, "get_client", lambda: _FakeClient([fila]))
    r = lq.buscar_empleado_preview("0920116811", "cedula", lq.FUENTE_SUPABASE)
    assert r is not None
    assert r["nombre"] == "PEREIRA JUAN" and r["cedula"] == "0920116811" and r["sueldo"] == 460.0


def test_buscar_empleado_preview_por_nombre_supabase(monkeypatch):
    fila = {
        "cedula": 920116811.0, "empleado": "1012", "apellidos": "PEREIRA", "nombres": "JUAN",
        "cargo": "GUARDIA", "seccion": "SEC1", "fecha_ing": "2020-03-15", "sueldo": 460.0,
    }
    monkeypatch.setattr(lq.supabase_client, "get_client", lambda: _FakeClient([fila]))
    r = lq.buscar_empleado_preview("PEREIRA", "nombre", lq.FUENTE_SUPABASE)
    assert r is not None and r["empleado"] == "1012"


def test_buscar_empleado_preview_sin_identificador_es_none():
    assert lq.buscar_empleado_preview("   ", "cedula", lq.FUENTE_SUPABASE) is None


def test_totales_desde_valores_recalcula_ingresos_descuentos_y_derivados():
    tot = lq._totales_desde_valores({
        "SUELDO": 500.0, "VACACIONES": 100.0, "DEC_TERCERA_ANT": 40.0, "DEC_TERCERA_ACT": 45.0,
        "IESS": 60.0, "PREST_COMPANIA": 30.0, "MULTAS": 10.0,
    })
    assert tot["total_ingresos"] == 685.0        # 500 + 100 + 40 + 45
    assert tot["total_descuentos"] == 100.0      # 60 + 30 + 10
    assert tot["total_liquido"] == 585.0
    assert tot["decimo_tercero"] == 85.0
    assert tot["prestamos"] == 30.0 and tot["multas"] == 10.0
    assert tot["otros_descuentos"] == 60.0       # IESS


class _FakeRecTable:
    def __init__(self, nombre, log, datos):
        self.n, self.log, self.datos = nombre, log, datos
        self.op = None
        self.payload = None

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    def execute(self):
        if self.op:
            self.log.append((self.n, self.op, self.payload))
            if self.op == "insert" and self.n == "liquidaciones":
                return _FakeExec([{"id": "NEW1"}])
            return _FakeExec([{"ok": 1}] if self.op == "update" else [])
        return _FakeExec(self.datos.get(self.n, []))


class _FakeRecClient:
    def __init__(self, datos):
        self.datos = datos
        self.log: list = []

    def table(self, nombre):
        return _FakeRecTable(nombre, self.log, self.datos)


def test_editar_valores_liquidacion(monkeypatch, app_db):
    registro = {"id": "L1", "estado": "generada", "total_liquido": 585.0}
    conceptos = [
        {"concepto_codigo": "SUELDO", "concepto_tipo": "ingreso", "valor_total": 500.0},
        {"concepto_codigo": "VACACIONES", "concepto_tipo": "ingreso", "valor_total": 100.0},
        {"concepto_codigo": "IESS", "concepto_tipo": "descuento", "valor_total": 60.0},
        {"concepto_codigo": "MULTAS", "concepto_tipo": "descuento", "valor_total": 10.0},
    ]
    monkeypatch.setattr(lq, "obtener_liquidacion", lambda _id: (registro, conceptos))
    cliente = _FakeRecClient({})
    monkeypatch.setattr(lq.supabase_client, "get_client", lambda: cliente)

    ok, err = lq.editar_valores_liquidacion(
        "L1", {"MULTAS": 25.0, "VACACIONES": 0.0}, usuario="ana", roles={"editor"}
    )
    assert ok and err == ""

    detalle_ops = [(op, pl) for (t, op, pl) in cliente.log if t == lq.TABLA_LIQ_DETALLE]
    assert ("update", {"valor_total": 25.0}) in detalle_ops       # MULTAS 10 -> 25
    assert any(op == "delete" for op, _ in detalle_ops)           # VACACIONES 100 -> 0 => borrar
    liq_upd = next(pl for (t, op, pl) in cliente.log if t == lq.TABLA_LIQ and op == "update")
    assert liq_upd["total_ingresos"] == 500.0                     # 500 (vac quitada)
    assert liq_upd["total_descuentos"] == 85.0                    # 60 + 25
    assert liq_upd["total_liquido"] == 415.0
    assert liq_upd["updated_by"] == "ana"


def test_editar_valores_liquidacion_no_toca_pagada(monkeypatch):
    monkeypatch.setattr(lq, "obtener_liquidacion", lambda _id: ({"estado": "pagada"}, []))
    ok, err = lq.editar_valores_liquidacion("L1", {"MULTAS": 5.0}, usuario="x", roles=set())
    assert not ok and "pagada" in err


class _FakeQueryPorTabla:
    def __init__(self, datos_por_tabla, tabla):
        self._d, self._t = datos_por_tabla, tabla

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return _FakeExec(list(self._d.get(self._t, [])))


class _FakeClientPorTabla:
    def __init__(self, datos_por_tabla):
        self._d = datos_por_tabla

    def table(self, nombre):
        return _FakeQueryPorTabla(self._d, nombre)


def test_bot_mrl_xlsx_genera_excel_con_encabezados(monkeypatch):
    import io

    import openpyxl

    from core.excel import liquidaciones_bot_mrl as bm

    datos = {
        "liquidaciones": [{
            "id": "L1", "empleado_codigo": "9091", "empleado_cedula": "1207158815.0",
            "empleado_apellidos": "ACOSTA FLORES", "empleado_nombres": "ALCI",
            "fecha_salida": "2026-06-24", "dias_trabajados": 24, "seccion": "S1",
            "total_descuentos": 60.0, "total_liquido": 540.0, "vacaciones_pendientes": 10.0,
        }],
        "liquidaciones_detalle": [
            {"concepto_codigo": "SUELDO", "valor_total": 400.0},
            {"concepto_codigo": "DEC_TERCERA_ACT", "valor_total": 33.0},
            {"concepto_codigo": "IESS", "valor_total": 60.0},
        ],
        "liquidaciones_periodos_calculo": [],
    }
    monkeypatch.setattr(bm.supabase_client, "get_client", lambda: _FakeClientPorTabla(datos))
    monkeypatch.setattr(bm, "_sueldo_basico_rpemplea", lambda c: 450.0)

    data, advertencias, error = bm.bot_mrl_xlsx(["L1"])
    assert error is None and data is not None
    ws = openpyxl.load_workbook(io.BytesIO(data)).active
    cab = [c.value for c in next(ws.iter_rows())]
    assert cab[:3] == ["Cod", "Nombres", "cedula"]
    fila = [c.value for c in list(ws.iter_rows())[1]]
    assert fila[0] == "9091" and fila[2] == "1207158815"
    assert any("desglose mensual" in a for a in advertencias)  # periodos_calculo vacío


def test_bot_mrl_xlsx_sin_ids():
    from core.excel.liquidaciones_bot_mrl import bot_mrl_xlsx

    data, _, error = bot_mrl_xlsx([])
    assert data is None and "una o más" in error


def test_guardar_liquidacion_persiste_desglose_mensual_del_decimo(monkeypatch, app_db):
    liq = _liq_ejemplo()
    liq.detalle_decimo_tercera = [
        lq.DetalleMesDecimo(label="mayo -2026", valor=40.0),
        lq.DetalleMesDecimo(label="junio -2026", valor=45.0),
    ]
    cliente = _FakeRecClient({})
    monkeypatch.setattr(lq.supabase_client, "get_client", lambda: cliente)

    ok, _id = lq.guardar_liquidacion(liq, "generada", lq.ConfigLiquidacion(), usuario="ana", roles=set())
    assert ok

    periodos_ins = [
        pl for (t, op, pl) in cliente.log
        if t == lq.TABLA_LIQ_PERIODOS and op == "insert"
    ]
    assert len(periodos_ins) == 1
    p = periodos_ins[0]
    assert p["tipo"] == "DEC_TERCERA"
    assert p["meses"] == [
        {"label": "mayo -2026", "valor": 40.0},
        {"label": "junio -2026", "valor": 45.0},
    ]


def test_guardar_liquidacion_rechaza_estado_invalido():
    ok, msg = lq.guardar_liquidacion(
        _liq_ejemplo(), "estado_invalido", lq.ConfigLiquidacion(), usuario="t", roles=set()
    )
    assert not ok and "inválido" in msg


def test_guardar_liquidacion_rechaza_si_hay_error():
    liq = _liq_ejemplo(error="empleado no encontrado")
    ok, msg = lq.guardar_liquidacion(liq, "borrador", lq.ConfigLiquidacion(), usuario="t", roles=set())
    assert not ok and msg == "empleado no encontrado"


def test_liquidacion_pdf_genera_documento_valido():
    from core.pdf.liquidacion_individual import liquidacion_pdf

    liq = _liq_ejemplo(detalle_vacaciones=[
        lq.DetalleVacacionesPeriodo("2024-2025", "PAGADO", 0.0, 200.0, False),
        lq.DetalleVacacionesPeriodo("2025-2026", "GOZADO_PARCIAL", 5.0, 220.0, True),
    ])
    data = liquidacion_pdf(liq, mostrar_insumos=True, es_simulacion=True)
    assert data[:4] == b"%PDF"
    assert len(data) > 500

    data_real = liquidacion_pdf(liq, es_simulacion=False)
    assert data_real[:4] == b"%PDF"


def test_reconstruir_liquidacion_desde_supabase():
    registro = {
        "empleado_codigo": "1012", "empleado_cedula": "0920116811",
        "empleado_apellidos": "PEREIRA", "empleado_nombres": "JUAN",
        "cargo": "GUARDIA", "puesto_servicio": "OPERACIONES", "seccion": "SEC1",
        "fecha_ingreso": "2020-03-15", "fecha_salida": "2026-06-30",
        "motivo": "RENUNCIA VOLUNTARIA", "dias_trabajados": 2298,
        "fondo_reserva": 38.3, "vacaciones_pendientes": 18.33,
        "bonificacion_desahucio": 690.0, "total_descuentos": 43.47, "total_liquido": 956.53,
        "horas_25_cantidad": 10, "horas_50_cantidad": 0, "horas_100_cantidad": 0,
    }
    conceptos = [
        {"concepto_codigo": "SUELDO", "valor_total": 460.0},
        {"concepto_codigo": "SOBT_25", "valor_total": 15.6},
        {"concepto_codigo": "DESAHUCIO", "valor_total": 690.0},
        {"concepto_codigo": "IESS", "valor_total": 43.47},
    ]
    liq = lq.reconstruir_liquidacion(registro, conceptos)
    assert liq.empleado == "1012" and liq.cedula == "0920116811"
    assert liq.nombre == "PEREIRA JUAN"
    assert liq.campos["SUELDO"] == 460.0
    assert liq.campos["VAL_SOBT_25"] == 15.6
    assert liq.campos["DESAHUCIO"] == 690.0
    assert liq.campos["APORT_IESS"] == 43.47
    assert liq.campos["TOTAL_A_RECIBIR"] == 956.53
    assert liq.campos["HORAS_25"] == 10

    from core.pdf.liquidacion_individual import liquidacion_pdf

    data = liquidacion_pdf(liq, es_simulacion=False)
    assert data[:4] == b"%PDF"


def test_liquidacion_pdf_con_error_no_revienta():
    from core.pdf.liquidacion_individual import liquidacion_pdf

    liq = lq.Liquidacion("", "", "0900000000", "", "", "", 0.0, "", "", "", 0,
                         error="empleado no encontrado")
    data = liquidacion_pdf(liq)
    assert data[:4] == b"%PDF"
