"""Cálculos del módulo faltas — trasplante de nucleo_modular/faltas_calculo.py.

Varios tests fijan explícitamente el comportamiento BUGGY del legado (replicado a
propósito, ver docs/modulos/faltas.md §"Los 5 bugs a decidir"). Si un día se
decide corregir alguno, el test que lo ancla debe cambiar en el mismo commit.
"""

from __future__ import annotations

from datetime import date

import pytest

from core.faltas import calculo as c

# ── fechas / horas ──────────────────────────────────────────────────────────

def test_fin_de_mes():
    assert c.obtener_fecha_fin_mes(2026, 2) == date(2026, 2, 28)
    assert c.obtener_fecha_fin_mes(2026, 12) == date(2026, 12, 31)
    assert c.obtener_fecha_fin_mes(2024, 2) == date(2024, 2, 29)


@pytest.mark.parametrize("s,esperado", [
    ("05/09/2026", date(2026, 9, 5)),
    ("2026-09-05", date(2026, 9, 5)),
    ("05-09-2026", date(2026, 9, 5)),
    ("no es fecha", None),
])
def test_parse_fecha(s, esperado):
    assert c.parse_fecha(s) == esperado


def test_formatear_cedula():
    assert c.formatear_cedula("920116811") == "0920116811"
    assert c.formatear_cedula(920116811.0) == "0920116811"
    assert c.formatear_cedula(None) == ""
    assert c.formatear_cedula("abc") == ""


def test_calcular_horas():
    assert c.calcular_horas("FALTA", 1) == (16, 2)
    assert c.calcular_horas("FALTA", 3) == (48, 6)
    assert c.calcular_horas("PERMISO", 2) == (16, 2)
    # PERMISO MÉDICO cae en el mismo else que PERMISO
    assert c.calcular_horas("PERMISO MÉDICO", 1) == (8, 1)


# ── suspensión ──────────────────────────────────────────────────────────────

def test_calcular_suspension_suma_un_dia():
    # LEGADO bug #2: el registro real suma +1 día
    dias, horas = c.calcular_suspension(date(2026, 9, 1), date(2026, 9, 3))
    assert dias == 3
    assert horas == 24


def test_porcentaje_descuento_puede_pasar_de_100():
    # LEGADO bug #3: suspensión > 30 días => porcentaje > 100
    assert c.calcular_porcentaje_descuento_suspension(15) == 50
    assert c.calcular_porcentaje_descuento_suspension(45) == 150


def test_descuento_horas_extra_sin_clamp_deja_negativo_posible():
    # LEGADO bug #3: clamp=False (flujo masivo) NO acota a las horas disponibles
    d25, d50, d100 = c.calcular_descuento_horas_extra(10, 20, 5, 150, clamp=False)
    assert (d25, d50, d100) == (15, 30, 7)  # descuentos > horas disponibles
    # clamp=True (flujo uno a uno) sí acota
    d25, d50, d100 = c.calcular_descuento_horas_extra(10, 20, 5, 150, clamp=True)
    assert (d25, d50, d100) == (10, 20, 5)


def test_descuento_cero_si_porcentaje_no_positivo():
    assert c.calcular_descuento_horas_extra(10, 20, 30, 0) == (0, 0, 0)


def test_observacion_suspension_con_y_sin_descuento():
    simple = c.generar_observacion_suspension("05/09/2026", 3, 24, "reincidencia")
    assert simple == "SUSPENSIÓN desde 05/09/2026 — 3 días (24h) — reincidencia"
    con_desc = c.generar_observacion_suspension("05/09/2026", 3, 24, "x", 50, 1, 2, 0)
    assert "Descuento 50%: HOR25-1h, HOR50-2h, HOR100-0h" in con_desc


# ── alerta de investigación ─────────────────────────────────────────────────

def test_alerta_faltas_niveles():
    assert c.evaluar_alerta_faltas(0, 16)["nivel"] == "ok"
    assert c.evaluar_alerta_faltas(48, 16)["nivel"] == "ya_supero"
    sup = c.evaluar_alerta_faltas(40, 16)
    assert sup["nivel"] == "superara"
    assert sup["totaus_nuevo"] == 56
    assert sup["faltas_nuevo"] == 3


# ── restas de horas ─────────────────────────────────────────────────────────

def test_calcular_resta_horas_solo_hor50():
    assert c.calcular_resta_horas(40, 10, 3) == (16, 10, "OK")  # 3*8=24 <= 40


def test_calcular_resta_horas_pasa_a_hor100():
    # 4*8=32; HOR50=8 -> faltan 24 -> 24*0.75=18 de HOR100(20) -> 2
    assert c.calcular_resta_horas(8, 20, 4) == (0, 2, "OK")


def test_calcular_resta_horas_error_si_no_alcanza():
    assert c.calcular_resta_horas(0, 1, 5) == (0, 0, "ERROR")


def test_contar_faltas_por_cedula_filtra_periodo():
    regs = [
        {"cedula": "0912345678", "fecha": date(2026, 9, 1)},
        {"cedula": "0912345678", "fecha": date(2026, 9, 15)},
        {"cedula": "0912345678", "fecha": date(2026, 8, 30)},  # otro mes
        {"cedula": "999", "fecha": None},                       # descartada
    ]
    assert c.contar_faltas_por_cedula(regs, 2026, 9) == {"912345678": 2}


def test_calcular_resultados_resta_estados():
    conteo = {"912345678": 2, "111": 5, "222": 1, "333": 1}
    empleados = [
        {"CED_N": "912345678", "EMPLEADO": "1001", "CEDULA": "0912345678",
         "APELLIDOS": "PEREZ", "NOMBRES": "ANA", "HOR50": 40, "HOR100": 0},
        {"CED_N": "111", "EMPLEADO": "1002", "CEDULA": "0000000111",
         "APELLIDOS": "X", "NOMBRES": "Y", "HOR50": 40, "HOR100": 0},
        {"CED_N": "222", "EMPLEADO": "1003", "CEDULA": "0000000222",
         "APELLIDOS": "Z", "NOMBRES": "W", "HOR50": 0, "HOR100": 0},
        # 333 no está -> ERROR_CEDULA
    ]
    filas = c.calcular_resultados_resta(conteo, empleados)
    por_emp = {r["EMPLEADO"]: r["ESTADO"] for r in filas if r["EMPLEADO"]}
    assert por_emp["1001"] == "OK"
    assert por_emp["1002"] == "REVISION"   # 5 > MAX_FALTAS
    assert por_emp["1003"] == "SIN_HORAS"
    # cédula 333 sin empleado -> ERROR_CEDULA
    assert [r["ESTADO"] for r in filas if not r["EMPLEADO"]] == ["ERROR_CEDULA"]


# ── parsing de pegado ───────────────────────────────────────────────────────

def test_parse_linea_pegado_separadores():
    assert c.parse_linea_pegado("1234\tFALTA\t1") == ["1234", "FALTA", "1"]
    assert c.parse_linea_pegado("1234  FALTA  1") == ["1234", "FALTA", "1"]
    assert c.parse_linea_pegado("1234|FALTA|1") == ["1234", "FALTA", "1"]


def test_parse_line_no_detecta_espacios():
    # LEGADO bug #21: parse_line (legado no usado) NO parte por 2 espacios
    assert c.parse_line("1234  FALTA  1") == ["1234  FALTA  1"]


def test_mapear_pegado_salta_columna_nombre():
    # pegar desde Código: j=0 -> col 0 (codigo), j=1 -> col 2 (tipo), ...
    campos = c.mapear_pegado_a_campos(0, ["1234", "FALTA", "1", "05/09/2026", "tarde"])
    assert campos == {"codigo": "1234", "tipo": "FALTA", "cant": "1",
                      "fecha": "05/09/2026", "observ": "tarde"}


# ── validación de filas ─────────────────────────────────────────────────────

def test_validar_fila_grid_masivo_rechaza_suspension_con_tilde():
    # LEGADO bug #1: el set de VALIDAR es SIN tilde
    ok, err = c.validar_fila_grid_masivo("1234", "SUSPENSIÓN", "3", "05/09/2026")
    assert not ok and "tipo" in err
    ok, err = c.validar_fila_grid_masivo("1234", "FALTA", "1", "05/09/2026")
    assert ok and err is None


def test_validar_fila_registro_acepta_suspension_con_tilde():
    ok, err, f = c.validar_fila_registro("1234", "SUSPENSIÓN", "3", "05/09/2026")
    assert ok and f == date(2026, 9, 5)
    ok, err, f = c.validar_fila_registro("1234", "FALTA", "0", "05/09/2026")
    assert not ok and "cantidad" in err
