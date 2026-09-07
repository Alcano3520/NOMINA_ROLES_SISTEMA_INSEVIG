"""Compara los datos que produce `core/` desde SQL Server vs Supabase.

    python -m scripts.validar_datos --periodo 2026-06 1012 1035 0920116811
    python -m scripts.validar_datos --periodo 2026-06 --muestra 15

Para cada empleado:
  - `core.datos.service.datos_empleado` desde ambas fuentes -> compara campo a
    campo (tolerancia de redondeo en los montos).
  - `core.repos.prestamos.saldo_total` desde ambas fuentes.

Sale con código 0 si todo coincide dentro de la tolerancia, 1 si hay diferencias
(o no se encontró un empleado en alguna fuente). No escribe nada.
"""

from __future__ import annotations

import argparse
import sys

from core.datos.service import datos_empleado
from core.repos import prestamos

TOLERANCIA = 0.02  # centavos


def _muestra(n: int, fuente: str) -> list[str]:
    from core.repos.empleados import buscar

    return [str(e["empleado"]).strip() for e in buscar("", fuente, limite=n) if e.get("empleado")]


def _difs_dict(a: dict, b: dict) -> list[str]:
    difs: list[str] = []
    for k in sorted(set(a) | set(b)):
        va, vb = a.get(k), b.get(k)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            if abs(float(va) - float(vb)) > TOLERANCIA:
                difs.append(f"{k}: SQL={va!r}  SUP={vb!r}")
        elif str(va or "").strip() != str(vb or "").strip():
            difs.append(f"{k}: SQL={va!r}  SUP={vb!r}")
    return difs


def _validar_uno(periodo: str, ident: str) -> list[str]:
    problemas: list[str] = []
    try:
        sq = datos_empleado(periodo, ident, "sqlserver")
        su = datos_empleado(periodo, ident, "supabase")
    except Exception as e:  # noqa: BLE001
        return [f"error consultando: {e}"]
    if sq is None:
        problemas.append("no está en SQL Server")
    if su is None:
        problemas.append("no está en Supabase")
    if sq is not None and su is not None:
        problemas += _difs_dict(sq.to_dict(), su.to_dict())
    try:
        s_sq = prestamos.saldo_total(ident, "sqlserver")
        s_su = prestamos.saldo_total(ident, "supabase")
        if abs(s_sq - s_su) > TOLERANCIA:
            problemas.append(f"saldo préstamos: SQL={s_sq:.2f}  SUP={s_su:.2f}")
    except Exception as e:  # noqa: BLE001
        problemas.append(f"error en saldo de préstamos: {e}")
    return problemas


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("identificadores", nargs="*", help="códigos de empleado o cédulas")
    p.add_argument("--periodo", required=True, help="AAAA-MM")
    p.add_argument("--muestra", type=int, default=0, help="tomar N empleados automáticamente")
    args = p.parse_args()

    idents = list(args.identificadores)
    if args.muestra:
        idents += [x for x in _muestra(args.muestra, "supabase") if x not in idents]
    if not idents:
        print("Pasa identificadores o --muestra N.", file=sys.stderr)
        return 2

    print(f"Período {args.periodo} · {len(idents)} empleados · tolerancia {TOLERANCIA}\n")
    con_difs = 0
    for ident in idents:
        problemas = _validar_uno(args.periodo, ident)
        if problemas:
            con_difs += 1
            print(f"[DIF] {ident}")
            for x in problemas:
                print(f"      - {x}")
        else:
            print(f"[OK ] {ident}")

    print(f"\n{len(idents) - con_difs}/{len(idents)} coinciden. {con_difs} con diferencias.")
    return 1 if con_difs else 0


if __name__ == "__main__":
    sys.exit(main())
