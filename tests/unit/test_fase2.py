"""Fase 2: helpers de préstamos/observaciones que no tocan BD + migración SQLite."""

import sqlite3

from core.migrations_legacy.sqlite_to_appdb import migrar
from core.repos import prestamos
from core.repos.observaciones import _falta, _fila_obs


def test_fila_obs_filtra_refers_vacios():
    r = {"empleado": "1012", "fecha_ven": "2026-06-01", "APELLIDOS": "PEREIRA", "NOMBRES": "JUAN"}
    fila = _fila_obs(r, ["texto A", "", None, "texto B", "  "])
    assert fila.empleado == "1012"
    assert fila.apellidos_nombres == "PEREIRA JUAN"
    assert fila.textos == ["texto A", "texto B"]


def test_reporte_html_observaciones():
    from core.repos import observaciones as obs

    html = obs.reporte_html(
        "1012", "PEREIRA JUAN",
        [{"fecha_ven": "2026-01-01", "texto": "Atrasos <x>"}],
        [{"fecha": "2026-02-01", "valor": 10.0, "concepto": "MULTA", "observ": "n"}],
        [{"periodo": "2026-01", "ausencias": 1, "faltas_justificadas": 0, "faltas_injustificadas": 1, "total": 2}],
    )
    assert "<title>Observaciones" in html and "PEREIRA JUAN" in html
    assert "&lt;x&gt;" in html  # escapado
    assert "MULTA" in html


def test_falta_suma_total():
    f = _falta({"FECHA_VEN": "2026-06-15", "TOTAUS": 8, "TOTFJ": 0, "TOTFI": 4})
    assert f.periodo == "2026-06"
    assert f.total == 12.0


def test_numeros_migrados_se_excluyen_de_rphistor():
    assert "27958" in prestamos._NUMEROS_MIGRADOS
    assert prestamos.CLASE_PRESTAMO == 205


def test_agrupar_por_numero():
    M = prestamos.MovimientoPrestamo
    movs = [
        M("2025-01-05", 1000.0, "PRESTAMO", "500", "RPHISTOR"),
        M("2025-02-05", -100.0, "CUOTA", "500", "RPHISTOR"),
        M("2025-03-05", -100.0, "CUOTA", "500", "RPHISTOR"),
        M("2025-04-05", 300.0, "PRESTAMO", "700", "RPINGDES"),
    ]
    g = {r.numero: r for r in prestamos.agrupar_por_numero(movs)}
    assert g["500"].prestado == 1000.0
    assert g["500"].abonado == 200.0
    assert g["500"].saldo == 800.0
    assert g["500"].cuotas == 2
    assert g["500"].cuota_promedio == 100.0
    assert g["500"].cancelado is False
    assert g["500"].meses_brecha == 0  # feb -> mar consecutivos
    assert "para cancelar" in g["500"].estado
    assert g["700"].saldo == 300.0


def test_agrupar_detecta_brecha_y_cancelado():
    M = prestamos.MovimientoPrestamo
    movs = [
        M("2025-01-05", 400.0, "P", "9", "RPHISTOR"),
        M("2025-01-31", -200.0, "C", "9", "RPHISTOR"),
        M("2025-04-30", -200.0, "C", "9", "RPHISTOR"),  # brecha feb y mar
    ]
    r = prestamos.agrupar_por_numero(movs)[0]
    assert r.saldo == 0.0 and r.cancelado is True
    assert r.meses_brecha == 2
    assert "Cancelado" in r.estado
    det = prestamos.movimientos_de_numero(movs, "9")
    assert len(det) == 3 and det[0].fecha == "2025-01-05"


def test_historial_xlsx_tiene_hoja_resumen():
    import io

    import openpyxl

    from core.excel.prestamos_builders import historial_xlsx

    M = prestamos.MovimientoPrestamo
    data = historial_xlsx("1012", "PEREIRA", [M("2025-01-05", 500.0, "P", "9", "RPHISTOR")])
    wb = openpyxl.load_workbook(io.BytesIO(data))
    assert {"Historial", "Resumen por préstamo"} <= set(wb.sheetnames)


def test_migracion_sqlite_a_appdb(app_db, tmp_path):
    ruta = tmp_path / "Saldo_prestamos_driver.db"
    con = sqlite3.connect(ruta)
    con.execute(
        "CREATE TABLE historial_prestamos (codigo_empleado TEXT, fecha TEXT, "
        "ingreso REAL, egreso REAL, concepto TEXT, tipo TEXT, numero_fila INTEGER)"
    )
    con.executemany(
        "INSERT INTO historial_prestamos VALUES (?,?,?,?,?,?,?)",
        [
            ("1012", "2020-01-15", 0, 50.0, "PRESTAMO COMPANIA", "NORMAL", 1),
            ("1012", "2020-06-01", 100.0, 0, "CUADRE", "CUADRE", 2),
        ],
    )
    con.commit()
    con.close()

    n = migrar(str(ruta))
    assert n == 2

    movs = prestamos._historial_migrado("1012")
    assert len(movs) == 2
    assert any(m.es_cuadre for m in movs)
    assert any(m.valor == -50.0 for m in movs)  # egreso -> negativo
