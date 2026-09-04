"""Módulo 9: fórmulas legales de liquidación (Ecuador). Portadas de
Liquidaciones_generador_CON_VACACIONES.pyw — deben coincidir exactamente.
"""

import datetime as dt

from core.excel.liquidaciones_builders import liquidaciones_xlsx
from core.repos import liquidaciones as lq


def test_dias360_como_excel():
    assert lq.dias360(dt.date(2024, 1, 15), dt.date(2024, 2, 15)) == 30
    assert lq.dias360(dt.date(2023, 2, 4), dt.date(2026, 2, 4)) == 3 * 360
    assert lq.dias360(dt.date(2024, 1, 31), dt.date(2024, 3, 31)) == 60


def test_periodos_vacaciones_por_mes_de_ingreso():
    # ingresó 04/02/2023 (mes 2). El periodo va del 01/02 al 31/01 del año siguiente.
    # Faithful al legado: día_inicio=1, así que salir en/después del mes de ingreso
    # pone el "último periodo" en el año de salida.
    p = lq.periodos_vacaciones(dt.date(2023, 2, 4), dt.date(2026, 3, 15))
    assert p == [
        (dt.date(2025, 2, 1), dt.date(2026, 1, 31)),
        (dt.date(2026, 2, 1), dt.date(2027, 1, 31)),
    ]
    # sale ANTES del mes de ingreso -> último periodo es el año anterior
    p2 = lq.periodos_vacaciones(dt.date(2023, 2, 4), dt.date(2026, 1, 20))
    assert p2[-1] == (dt.date(2025, 2, 1), dt.date(2026, 1, 31))


def test_periodo_decima_tercera_dic_a_nov():
    p = lq.periodos_decima_tercera(dt.date(2022, 1, 1), dt.date(2026, 3, 10))
    assert p[-1] == (dt.date(2025, 12, 1), dt.date(2026, 11, 30), False)  # pago 24/12/26 > salida


def test_decima_cuarta_costa_vs_sierra():
    costa = lq.periodos_decima_cuarta(dt.date(2024, 1, 1), dt.date(2026, 5, 1), "COSTA")
    assert (dt.date(2025, 3, 1), dt.date(2026, 2, 28), True) in costa  # pagado 15/03/26 < 01/05
    sierra = lq.periodos_decima_cuarta(dt.date(2024, 1, 1), dt.date(2026, 5, 1), "SIERRA")
    assert any(i.month == 8 for i, _, _ in sierra)


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
