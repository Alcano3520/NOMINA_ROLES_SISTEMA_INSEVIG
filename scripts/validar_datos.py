"""Compara los datos que produce `core/` desde SQL Server vs Supabase.

    python -m scripts.validar_datos --periodo 2026-06 1012 1035 0920116811
    python -m scripts.validar_datos --periodo 2026-06 --muestra 20
    python -m scripts.validar_datos --periodo 2026-06 --muestra 20 --muestra-de supabase

La muestra sale por defecto de **SQL Server** (la fuente de verdad). Para cada
empleado, por su cédula:
  - `core.datos.service.datos_empleado` desde ambas fuentes → compara campo a
    campo (tolerancia de redondeo en los montos).
  - `core.repos.prestamos.saldo_total` desde ambas fuentes.

Categorías por empleado: OK · DIF (difieren campos, presente en ambas) ·
SOLO-SQL / SOLO-SUP (presente en una sola — típico: espejo de Supabase con
registros huérfanos que ya no están en SQL Server) · ERROR.

Sale con código ≠ 0 solo si hay DIF o ERROR reales. No escribe nada.
"""

from __future__ import annotations

import argparse
import sys

from core.datos.service import datos_empleado
from core.repos import prestamos
from core.utils import normalizar_cedula

TOLERANCIA = 0.02  # centavos


def _muestra(n: int, fuente: str) -> list[str]:
    """Cédulas (clave estable) de N empleados ACT — mismo criterio que usa
    `datos_empleado` (que filtra `[ESTADO]='ACT'`, igual que el legado)."""
    from core.repos.empleados import buscar

    out: list[str] = []
    for e in buscar("", fuente, solo_activos=True, limite=n):
        ced = normalizar_cedula(e.get("cedula"))
        if ced and ced != "0000000000":
            out.append(ced)
    return out


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


def _clasificar(periodo: str, ident: str) -> tuple[str, list[str]]:
    """Devuelve (categoria, detalle)."""
    try:
        sq = datos_empleado(periodo, ident, "sqlserver")
        su = datos_empleado(periodo, ident, "supabase")
    except Exception as e:  # noqa: BLE001
        return "ERROR", [f"error consultando: {e}"]

    if sq is None and su is None:
        return "ERROR", ["no está en ninguna de las dos fuentes"]
    if su is None:
        return "SOLO-SQL", [
            f"ACT en SQL Server ({sq.empleado}/{sq.cedula}) — falta en el espejo de Supabase"  # type: ignore[union-attr]
        ]
    if sq is None:
        return "SOLO-SUP", [
            f"en Supabase ({su.empleado}/{su.cedula}) — no es un empleado ACT en SQL Server"
        ]

    if normalizar_cedula(sq.cedula) != normalizar_cedula(su.cedula):
        return "ERROR", [
            f"el script casó personas distintas: SQL {sq.empleado}/{sq.cedula} "
            f"vs SUP {su.empleado}/{su.cedula}"
        ]

    detalle = _difs_dict(sq.to_dict(), su.to_dict())
    try:
        s_sq = prestamos.saldo_total(sq.empleado, "sqlserver")
        s_su = prestamos.saldo_total(su.empleado, "supabase")
        if abs(s_sq - s_su) > TOLERANCIA:
            detalle.append(f"saldo préstamos: SQL={s_sq:.2f}  SUP={s_su:.2f}")
    except Exception as e:  # noqa: BLE001
        detalle.append(f"error en saldo de préstamos: {e}")
    return ("DIF", detalle) if detalle else ("OK", [])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("identificadores", nargs="*", help="códigos de empleado o cédulas")
    p.add_argument("--periodo", required=True, help="AAAA-MM")
    p.add_argument("--muestra", type=int, default=0, help="tomar N empleados automáticamente")
    p.add_argument("--muestra-de", default="sqlserver", choices=("sqlserver", "supabase"),
                   help="de qué fuente sacar la muestra (def: sqlserver)")
    args = p.parse_args()

    idents = list(args.identificadores)
    if args.muestra:
        idents += [x for x in _muestra(args.muestra, args.muestra_de) if x not in idents]
    if not idents:
        print("Pasa identificadores o --muestra N.", file=sys.stderr)
        return 2

    print(f"Período {args.periodo} · {len(idents)} empleados · muestra de {args.muestra_de} "
          f"· tolerancia {TOLERANCIA}\n")
    conteo: dict[str, int] = {}
    for ident in idents:
        cat, detalle = _clasificar(args.periodo, ident)
        conteo[cat] = conteo.get(cat, 0) + 1
        marca = {"OK": "OK  ", "DIF": "DIF ", "SOLO-SQL": "S-SQL", "SOLO-SUP": "S-SUP", "ERROR": "ERR "}[cat]
        print(f"[{marca}] {ident}" + ("".join(f"\n       - {d}" for d in detalle) if detalle else ""))

    print("\nResumen: " + " · ".join(f"{k}={v}" for k, v in sorted(conteo.items())))
    return 1 if (conteo.get("DIF") or conteo.get("ERROR")) else 0


if __name__ == "__main__":
    sys.exit(main())
