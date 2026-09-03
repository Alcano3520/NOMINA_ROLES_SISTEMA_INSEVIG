from core.utils import a_float, a_int, normalizar_cedula


class TestNormalizarCedula:
    def test_float_de_sql_server(self):
        assert normalizar_cedula(920116811.0) == "0920116811"

    def test_string_de_10_digitos(self):
        assert normalizar_cedula("1712345678") == "1712345678"

    def test_string_con_punto_decimal(self):
        assert normalizar_cedula("920116811.0") == "0920116811"

    def test_none_y_vacio(self):
        assert normalizar_cedula(None) == ""
        assert normalizar_cedula("  ") == ""

    def test_con_guiones_o_espacios(self):
        assert normalizar_cedula(" 171-234-5678 ") == "1712345678"

    def test_no_numerico_se_devuelve_tal_cual(self):
        assert normalizar_cedula("N/A") == "N/A"


class TestCoerciones:
    def test_a_int(self):
        assert a_int("205") == 205
        assert a_int("205.0") == 205
        assert a_int(None) == 0
        assert a_int("", default=-1) == -1
        assert a_int("basura", default=7) == 7

    def test_a_float(self):
        assert a_float("120.5") == 120.5
        assert a_float(None) == 0.0
        assert a_float("x", default=1.0) == 1.0
