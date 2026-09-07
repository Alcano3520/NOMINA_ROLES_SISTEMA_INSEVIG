"""¿El mapa `core.concepts.CLASE_A_CONCEPTO` cubre todas las CLASE de un período real?

    python -m scripts.validar_conceptos --periodo 2026-06
    python -m scripts.validar_conceptos --periodo 2026-06 --fuente supabase

Consulta las CLASE distintas que aparecen en RPINGDES y RPHISTOR para el período
y las clasifica:
  - mapeada + entra en los totales  → OK
  - en CLASES_IGNORADAS / == CLASE_DIAS (101) → IGNORADA (a propósito)
  - mapeada pero NO está en CAMPOS_INGRESO/EGRESO → SE PIERDE DEL TOTAL
  - sin mapear → `CONCEPTO_<n>`, SE PIERDE DEL TOTAL

Sale con código ≠ 0 si alguna CLASE con dinero se pierde del total. No escribe nada.
"""

from __future__ import annotations

import argparse
import contextlib
import sys

with contextlib.suppress(Exception):  # consola de Windows (cp1252) no imprime Σ/→
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from core.concepts import (
    CAMPOS_EGRESO,
    CAMPOS_INGRESO,
    CLASE_A_CONCEPTO,
    CLASE_DIAS,
    CLASES_IGNORADAS,
)

_EN_TOTAL = set(CAMPOS_INGRESO) | set(CAMPOS_EGRESO)


def clasificar_clase(clase: int) -> tuple[str, bool]:
    """(texto de estado, se_pierde_del_total)."""
    if clase == CLASE_DIAS or clase in CLASES_IGNORADAS:
        return "IGNORADA (a propósito)", False
    if clase in CLASE_A_CONCEPTO:
        con = CLASE_A_CONCEPTO[clase]
        if con in _EN_TOTAL:
            return f"OK  → {con}", False
        return f"MAPEADA pero fuera del total → {con}  ⚠", True
    return "SIN MAPEAR → se pierde del total  ⚠", True


def _rango(periodo: str) -> tuple[str, str]:
    anio, mes = periodo.split("-")
    ini = f"{anio}-{int(mes):02d}-01"
    fin = f"{int(anio) + 1}-01-01" if int(mes) == 12 else f"{anio}-{int(mes) + 1:02d}-01"
    return ini, fin


def _clases_sqlserver(periodo: str) -> dict[int, tuple[int, float]]:
    from core.config import get_settings
    from core.db import sqlserver

    flt = get_settings().sqlserver_filter
    ini, fin = _rango(periodo)
    acc: dict[int, tuple[int, float]] = {}
    for tabla in ("RPINGDES", "RPHISTOR"):
        filas = sqlserver.filas(
            f"""SELECT [CLASE], COUNT(*) n, ISNULL(SUM([VALOR]),0) s
                FROM [insevig].[dbo].[{tabla}]
                WHERE {flt} AND [FECHA_VEN] IS NOT NULL
                  AND CAST([FECHA_VEN] AS DATE) >= CAST(? AS DATE)
                  AND CAST([FECHA_VEN] AS DATE) <  CAST(? AS DATE)
                GROUP BY [CLASE]""",
            (ini, fin),
        )
        for r in filas:
            c = int(r["CLASE"])
            n0, s0 = acc.get(c, (0, 0.0))
            acc[c] = (n0 + int(r["n"]), round(s0 + float(r["s"]), 2))
    return acc


def _clases_supabase(periodo: str) -> dict[int, tuple[int, float]]:
    from core.db import supabase_client

    sb = supabase_client.get_client()
    ini, fin = _rango(periodo)
    acc: dict[int, tuple[int, float]] = {}
    for tabla in ("rpingdesres", "rphistor_temp"):
        filas = (
            sb.table(tabla).select("clase,valor")
            .eq("codemp", "10").gte("fecha_ven", ini).lt("fecha_ven", fin)
            .execute().data or []
        )
        for r in filas:
            c = int(r["clase"])
            n0, s0 = acc.get(c, (0, 0.0))
            acc[c] = (n0 + 1, round(s0 + float(r.get("valor") or 0), 2))
    return acc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--periodo", required=True, help="AAAA-MM")
    p.add_argument("--fuente", default="sqlserver", choices=("sqlserver", "supabase"))
    args = p.parse_args()

    clases = _clases_sqlserver(args.periodo) if args.fuente == "sqlserver" else _clases_supabase(args.periodo)
    if not clases:
        print(f"Sin movimientos para {args.periodo} en {args.fuente}.", file=sys.stderr)
        return 2

    perdidas = 0
    print(f"Período {args.periodo} · fuente {args.fuente} · {len(clases)} CLASE distintas\n")
    for c in sorted(clases):
        n, s = clases[c]
        estado, se_pierde = clasificar_clase(c)
        if se_pierde and abs(s) > 0.01:
            perdidas += 1
        print(f"  CLASE {c:>4}  n={n:>6}  Σ={s:>14,.2f}   {estado}")

    print(f"\n{perdidas} CLASE con dinero que NO entra en los totales.")
    return 1 if perdidas else 0


if __name__ == "__main__":
    sys.exit(main())
