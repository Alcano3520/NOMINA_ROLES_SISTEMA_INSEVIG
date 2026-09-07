"""Regresión de `_buscar_empleado`: un código corto no debe casar por
substring dentro de la cédula de otra persona (paridad con el legado)."""

from __future__ import annotations

from core.datos.fuente_sqlserver import _buscar_empleado


class _FakeCursor:
    """Registra cada execute; devuelve fila solo para la consulta indicada."""

    def __init__(self, responder_si_contiene: str, fila: dict):
        self._trigger = responder_si_contiene
        self._fila = fila
        self.queries: list[str] = []
        self._ultimo: str = ""

    def execute(self, query: str, params: tuple):
        self.queries.append(query)
        self._ultimo = query

    @property
    def description(self):
        return [(k,) for k in self._fila]

    def fetchall(self):
        return [tuple(self._fila.values())] if self._trigger in self._ultimo else []


def test_codigo_corto_no_hace_like_sobre_cedula():
    cur = _FakeCursor("CEDULA AS VARCHAR", {"EMPLEADO": "x"})  # nunca se dispara
    assert _buscar_empleado(cur, "CODEMP='10'", "4086") is None
    unida = " || ".join(cur.queries)
    assert "[EMPLEADO] = ?" in unida
    assert "[CEDULA] = ?" in unida
    assert "NOMBRES] LIKE" in unida
    assert "CEDULA] AS VARCHAR" not in unida  # <- la regresión que se corrige


def test_identificador_largo_si_permite_like_sobre_cedula():
    cur = _FakeCursor("nunca", {"EMPLEADO": "x"})
    _buscar_empleado(cur, "CODEMP='10'", "PEREIRA JUAN")
    assert any("CEDULA] AS VARCHAR" in q for q in cur.queries)


def test_codigo_corto_resuelve_por_empleado_exacto():
    cur = _FakeCursor("[EMPLEADO] = ?", {"EMPLEADO": "1012", "APELLIDOS": "PEREIRA"})
    fila = _buscar_empleado(cur, "CODEMP='10'", "1012")
    assert fila is not None and fila["EMPLEADO"] == "1012"
    assert len(cur.queries) == 1  # paró en el primer intento
