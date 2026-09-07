"""CRUD de descuentos_pendientes (módulo liquidaciones)."""

from __future__ import annotations

import datetime as dt

from core.repos import descuentos_pendientes as dp


class _FakeExec:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, log, datos):
        self.log, self.datos = log, datos
        self.op = self.payload = None

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    def execute(self):
        if self.op:
            self.log.append((self.op, self.payload))
            return _FakeExec([])
        return _FakeExec(self.datos)


class _FakeClient:
    def __init__(self, datos=None):
        self.datos = datos or []
        self.log: list = []

    def table(self, _n):
        return _FakeTable(self.log, self.datos)


def test_fecha_iso_acepta_varios_formatos():
    assert dp._fecha_iso("05-03-2026") == "2026-03-05"
    assert dp._fecha_iso("5/3/2026") == "2026-03-05"
    assert dp._fecha_iso("2026-03-05") == "2026-03-05"
    assert dp._fecha_iso("") == dt.date.today().isoformat()
    assert dp._fecha_iso("basura") == dt.date.today().isoformat()


def test_crear_valida(monkeypatch):
    monkeypatch.setattr(dp.supabase_client, "get_client", lambda: _FakeClient())
    assert dp.crear(cedula="0912345678", nombre="", motivo="", monto=10, usuario="u") == (False, "El motivo es obligatorio.")
    assert dp.crear(cedula="0912345678", nombre="", motivo="Uniforme", monto=0, usuario="u")[0] is False
    assert dp.crear(cedula="abc", nombre="", motivo="x", monto=5, usuario="u")[0] is False
    ok, err = dp.crear(cedula="0912345678", nombre="ANA", motivo="Uniforme", monto=25.5, usuario="u")
    assert ok and err == ""


def test_crear_masivo_parsea_y_reporta_errores(monkeypatch):
    cli = _FakeClient()
    monkeypatch.setattr(dp.supabase_client, "get_client", lambda: cli)
    creados, errores = dp.crear_masivo(
        "0912345678, 25.50, Uniforme\n0923456789 ; 40 ; Anticipo\nmalo\n0999, xx, y",
        usuario="u",
    )
    assert creados == 2
    assert len(errores) == 2  # "malo" (faltan campos) y "xx" (monto no numérico)


def test_marcar_aplicados_y_eliminar(monkeypatch):
    cli = _FakeClient()
    monkeypatch.setattr(dp.supabase_client, "get_client", lambda: cli)
    dp.marcar_aplicados(["a", "b"], usuario="u")
    dp.eliminar(["c"], usuario="u")
    ops = [op for op, _ in cli.log]
    assert "update" in ops and "delete" in ops
    upd = next(pl for op, pl in cli.log if op == "update")
    assert upd["estado"] == "aplicado" and "fecha_aplicado" in upd


def test_marcar_aplicados_lista_vacia_no_llama(monkeypatch):
    cli = _FakeClient()
    monkeypatch.setattr(dp.supabase_client, "get_client", lambda: cli)
    dp.marcar_aplicados([], usuario="u")
    assert cli.log == []


def test_mes_de_fecha():
    from insevig_web.states.liquidaciones_state import _mes_de_fecha

    assert _mes_de_fecha("30/06/2026") == "2026-06"
    assert _mes_de_fecha("2026-06-30") == "2026-06"
    assert _mes_de_fecha("2026-06") == "2026-06"
    assert _mes_de_fecha("") == ""
    assert _mes_de_fecha("basura") == ""


def test_state_helper_marca_los_ids_de_la_liquidacion(monkeypatch):
    from core.repos.liquidaciones import Liquidacion
    from insevig_web.states import liquidaciones_state as st

    llamado: list = []
    monkeypatch.setattr(
        "core.repos.descuentos_pendientes.marcar_aplicados",
        lambda ids, *, usuario: llamado.append((list(ids), usuario)),
    )
    liq = Liquidacion("1", "X", "0912345678", "", "", "", 0.0, "", "", "", 0)
    liq.descuentos_aplicados = ["d1", "d2"]
    st._marcar_descuentos_aplicados(liq, "ana")
    assert llamado == [(["d1", "d2"], "ana")]

    # sin descuentos -> no llama
    llamado.clear()
    st._marcar_descuentos_aplicados(Liquidacion("1", "X", "c", "", "", "", 0.0, "", "", "", 0), "ana")
    assert llamado == []
