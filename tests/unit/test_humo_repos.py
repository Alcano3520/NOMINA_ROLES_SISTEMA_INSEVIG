"""El helper de scripts/humo_repos reporta OK/FALLA sin propagar excepciones."""

from __future__ import annotations

from scripts.humo_repos import _run


def test_run_ok(capsys):
    assert _run("x", lambda: [1, 2, 3]) is True
    assert "OK    x  (3)" in capsys.readouterr().out


def test_run_captura_el_error(capsys):
    def _boom():
        raise RuntimeError("Invalid column name 'creado_por'")

    assert _run("y", _boom) is False
    assert "FALLA y: RuntimeError: Invalid column name" in capsys.readouterr().out


def test_run_none(capsys):
    assert _run("z", lambda: None) is True
    assert "(None)" in capsys.readouterr().out
