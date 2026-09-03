"""Disciplina de arquitectura para poder trabajar un módulo por agente sin cruces.

Ver docs/CONTRATOS.md y docs/modulos/<mod>.md.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CORE = RAIZ / "core"
WEB = RAIZ / "insevig_web"

MODULOS = (
    "reportes", "prestamos", "observaciones", "empleados", "roles",
    "registrador", "bitacora", "admin",
)


def _imports(archivo: pathlib.Path) -> set[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    nombres: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres.add(nodo.module)
    return nombres


def test_core_no_importa_la_app_web():
    """`core/` es UI-agnóstico: nunca importa `insevig_web`."""
    ofensores = [
        p.relative_to(RAIZ)
        for p in CORE.rglob("*.py")
        if any(i == "insevig_web" or i.startswith("insevig_web.") for i in _imports(p))
    ]
    assert not ofensores, f"core importa insevig_web en: {ofensores}"


def test_repos_no_se_importan_entre_si():
    repos = CORE / "repos"
    if not repos.exists():
        pytest.skip("core/repos aún no existe")
    for p in repos.glob("*.py"):
        if p.stem == "__init__":
            continue
        otros = {f"core.repos.{q.stem}" for q in repos.glob("*.py")} - {f"core.repos.{p.stem}"}
        cruces = _imports(p) & otros
        assert not cruces, f"{p.name} importa otro repo: {cruces}"


def test_state_base_no_importa_el_proyecto():
    """`insevig_web/state.py` solo primitivas — sin imports del proyecto."""
    malos = {
        i for i in _imports(WEB / "state.py")
        if i.split(".")[0] in {"core", "insevig_web"}
    }
    assert not malos, f"state.py importa {malos}"


def test_states_de_feature_no_se_importan_entre_si():
    states = WEB / "states"
    modulos_state = {
        f"insevig_web.states.{p.stem}"
        for p in states.glob("*_state.py")
    }
    for p in states.glob("*_state.py"):
        propio = f"insevig_web.states.{p.stem}"
        cruces = _imports(p) & (modulos_state - {propio})
        # auth_state y datasource_state son compartidos: se permite depender de ellos
        cruces -= {"insevig_web.states.auth_state", "insevig_web.states.datasource_state"}
        assert not cruces, f"{p.name} importa otro state de feature: {cruces}"


def test_todas_las_paginas_compilan():
    """Cada @rx.page se convierte a componente sin error (lo que hace `reflex run`).

    `reflex export --backend-only` NO valida el JSX de las páginas; esto sí.
    """
    from reflex.app import RegistrationContext
    from reflex.compiler.compiler import into_component

    import insevig_web.insevig_web  # noqa: F401  crea la app
    from insevig_web import pages  # noqa: F401  registra las páginas

    decoradas = RegistrationContext.ensure_context().decorated_pages
    assert len(decoradas) >= 20
    fallos = []
    for render_fn, kwargs in decoradas:
        try:
            into_component(render_fn)
        except Exception as e:  # noqa: BLE001
            fallos.append(f"{kwargs.get('route', render_fn.__name__)}: {type(e).__name__}: {e}")
    assert not fallos, "Páginas que no compilan:\n" + "\n".join(fallos)


def test_registry_coherente():
    from insevig_web.registry import MODULES as SPECS

    nombres = [m.nombre for m in SPECS]
    assert sorted(nombres) == sorted(MODULOS)
    for m in SPECS:
        assert m.items, f"{m.nombre} sin items de navegación"
        for it in m.items:
            assert it.ruta.startswith("/")
