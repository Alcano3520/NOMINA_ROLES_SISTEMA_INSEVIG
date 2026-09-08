"""`test_concepts_cubre_periodo_real` (Fase 1): el mapa CLASE->concepto de
`core.concepts` cubre TODAS las CLASE con dinero de un período real.

Requiere SQL Server o Supabase reales -> marcado `integration` (excluido por
defecto). Correr en el NAS:

    pytest -m integration tests/integration/test_reportes_conceptos.py
    INSEVIG_TEST_PERIODO=2026-06 INSEVIG_TEST_FUENTE=supabase pytest -m integration ...
"""

from __future__ import annotations

import os

import pytest

from scripts.validar_conceptos import (
    _clases_sqlserver,
    _clases_supabase,
    clasificar_clase,
)

pytestmark = pytest.mark.integration

_PERIODO = os.environ.get("INSEVIG_TEST_PERIODO", "2026-06")
_FUENTE = os.environ.get("INSEVIG_TEST_FUENTE", "sqlserver")


def test_concepts_cubre_periodo_real():
    clases = _clases_sqlserver(_PERIODO) if _FUENTE == "sqlserver" else _clases_supabase(_PERIODO)
    if not clases:
        pytest.skip(f"Sin movimientos para {_PERIODO} en {_FUENTE} (¿fuente inalcanzable?).")

    perdidas = []
    for c, (n, s) in sorted(clases.items()):
        estado, se_pierde = clasificar_clase(c)
        if se_pierde and abs(s) > 0.01:
            perdidas.append(f"CLASE {c}: n={n} Σ={s:,.2f} — {estado}")

    assert not perdidas, (
        f"CLASE con dinero que NO entra en los totales ({_PERIODO}/{_FUENTE}):\n  "
        + "\n  ".join(perdidas)
    )
