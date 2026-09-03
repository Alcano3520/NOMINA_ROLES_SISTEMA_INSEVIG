"""Fase 3: helpers de empleados + parsers de Excel (sin BD)."""

import io

import openpyxl

from core.excel.parsers import parse_biess_quirografarios, parse_carga_masiva_empleados
from core.repos import empleados


def _xlsx(filas: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for f in filas:
        ws.append(f)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_token_cambia_si_cambia_un_campo():
    base = {c: "" for c in empleados.CAMPOS_EDITABLES}
    t1 = empleados._token(base)
    base["SUELDO"] = "800"
    assert empleados._token(base) != t1
    assert empleados._token({c: "" for c in empleados.CAMPOS_EDITABLES}) == t1


def test_normalizar_numericos_y_vacios():
    n = empleados._normalizar({"SUELDO": "800", "NOMBRES": "  JUAN ", "TELEFONO": "", "XXX": 1})
    assert n["SUELDO"] == 800.0
    assert n["NOMBRES"] == "JUAN"
    assert n["TELEFONO"] is None
    assert "XXX" not in n  # campo no editable


def test_normalizar_codificacion_de_flags():
    n = empleados._normalizar({
        "INCL_ROL": "1", "INCL_BAN": "",           # S/N texto
        "CAT_PROYECT_7": "S", "RPCAM2": "",        # '1'/'0' texto
        "PRIMARIA": "1", "SER_MIL": "",            # 1/0 entero
        "SEXO": "1",
    })
    assert n["INCL_ROL"] == "S" and n["INCL_BAN"] == "N"
    assert n["CAT_PROYECT_7"] == "1" and n["RPCAM2"] == "0"
    assert n["PRIMARIA"] == 1 and n["SER_MIL"] == 0
    assert n["SEXO"] == "1"


def test_estados_filtro():
    assert empleados._ESTADOS_FILTRO["ACTIVOS"] == ("ACT",)
    assert set(empleados._ESTADOS_FILTRO["INACTIVOS"]) == {"LIQ", "SUS"}
    assert empleados._ESTADOS_FILTRO["TODOS"] == ()


def test_ficha_empleado_pdf_parseable():
    import io

    import pypdf

    from core.pdf.ficha_empleado import ficha_empleado_pdf

    data = ficha_empleado_pdf("1012", {
        "NOMBRES": "JUAN", "APELLIDOS": "PEREZ", "CEDULA": "0920116811",
        "SUELDO": "800", "DIRECCION": "GUAYAQUIL", "CONYUGUE": "MARIA",
    })
    assert data[:4] == b"%PDF"
    txt = pypdf.PdfReader(io.BytesIO(data)).pages[0].extract_text()
    assert "PEREZ JUAN" in txt
    assert "Ficha de empleado" in txt


def test_grupos_cubren_las_6_pestanas_del_legado():
    assert set(empleados.GRUPOS) == {
        "Datos generales", "Ingresos / descuentos", "Otros datos",
        "Certificados / familiares", "Referencias",
    }
    # campos clave del legado presentes
    for c in ("COMPEN", "HOR100", "FONRESER", "CONYUGUE", "INCL_BAN", "NOM_FAM", "CERTVINF", "NUM_AFIL"):
        assert c in empleados.CAMPOS_EDITABLES


def test_parse_carga_masiva_ok_y_errores():
    data = _xlsx([
        ["EMPLEADO", "SUELDO", "TELEFONO"],
        ["1012", 850, "099"],
        ["", 900, ""],          # sin código -> se ignora
        ["2050", None, None],   # sin campos -> error
    ])
    filas, errores = parse_carga_masiva_empleados(data)
    assert len(filas) == 1
    assert filas[0]["EMPLEADO"] == "1012" and filas[0]["SUELDO"] == 850
    assert any("2050" in e for e in errores)


def test_parse_carga_masiva_sin_columna_empleado():
    _, errores = parse_carga_masiva_empleados(_xlsx([["CODIGO", "SUELDO"], ["1", 2]]))
    assert errores and "EMPLEADO" in errores[0]


def test_parse_biess_autodetecta_columnas():
    data = _xlsx([
        ["nombre", "cedula", "monto"],
        ["PEREIRA", "0920116811", "45.50"],
        ["LOPEZ", 1712345678, 120],
        ["basura", "abc", "xyz"],
    ])
    filas, _errores = parse_biess_quirografarios(data)
    ceds = {f["cedula"] for f in filas}
    assert "0920116811" in ceds and "1712345678" in ceds
    assert all(f["valor"] > 0 for f in filas)
