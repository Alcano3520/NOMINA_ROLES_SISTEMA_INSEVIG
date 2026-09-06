"""Carga única: `historial_prestamos` (SQLite `Saldo_prestamos_driver.db`) ->
tabla `LoanHistoryMigrated` del Postgres de la app.

    python -m core.migrations_legacy.sqlite_to_appdb /ruta/Saldo_prestamos_driver.db

Adapta `shared/migracion_prestamos_sqlite_supabase.py`. Tras el cutover, el SQLite
sobre SMB deja de usarse; `core/repos/prestamos.py` lee de `LoanHistoryMigrated`.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

import sqlmodel

from core.db import appdb
from core.db.models import LoanHistoryMigrated

_COLS = ("empleado", "fecha", "ingreso", "egreso", "concepto", "tipo", "numero_fila")


def _leer_sqlite(ruta: str) -> list[dict]:
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    try:
        # el nombre de columna del empleado varía entre versiones
        cur = con.execute("PRAGMA table_info(historial_prestamos)")
        cols = {r[1].lower() for r in cur.fetchall()}
        emp_col = "codigo_empleado" if "codigo_empleado" in cols else "empleado"
        rows = con.execute(
            f"SELECT {emp_col} AS empleado, fecha, ingreso, egreso, concepto, tipo, "
            f"numero_fila FROM historial_prestamos"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def _clave(empleado: str, fecha: str, numero_fila, ingreso: float, egreso: float) -> tuple:
    return (empleado, fecha, numero_fila, round(ingreso, 2), round(egreso, 2))


def migrar(ruta_sqlite: str, *, reemplazar: bool = False) -> int:
    """Carga `historial_prestamos` en `LoanHistoryMigrated`. Idempotente: una
    segunda corrida no duplica (salta las filas ya presentes). Devuelve cuántas
    filas NUEVAS se insertaron. `reemplazar=True` borra lo migrado antes."""
    filas = _leer_sqlite(ruta_sqlite)
    appdb.crear_tablas()
    insertadas = 0
    with appdb.session() as s:
        if reemplazar:
            s.exec(sqlmodel.delete(LoanHistoryMigrated))  # type: ignore[call-overload]
            s.commit()
            existentes: set[tuple] = set()
        else:
            existentes = {
                _clave(x.empleado, x.fecha, x.numero_fila, x.ingreso, x.egreso)
                for x in s.exec(sqlmodel.select(LoanHistoryMigrated)).all()
            }
        for r in filas:
            emp = str(r["empleado"]).strip()
            fecha = str(r.get("fecha") or "")[:10]
            ingreso = float(r.get("ingreso") or 0)
            egreso = float(r.get("egreso") or 0)
            k = _clave(emp, fecha, r.get("numero_fila"), ingreso, egreso)
            if k in existentes:
                continue
            existentes.add(k)
            s.add(
                LoanHistoryMigrated(
                    empleado=emp,
                    fecha=fecha,
                    ingreso=ingreso,
                    egreso=egreso,
                    concepto=str(r.get("concepto") or ""),
                    tipo=str(r.get("tipo") or ""),
                    numero_fila=r.get("numero_fila"),
                    origen="sqlite",
                )
            )
            insertadas += 1
        s.commit()
    return insertadas


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("ruta_sqlite")
    p.add_argument("--reemplazar", action="store_true", help="borra lo migrado antes de cargar")
    args = p.parse_args()
    n = migrar(args.ruta_sqlite, reemplazar=args.reemplazar)
    print(f"Insertadas {n} filas nuevas en LoanHistoryMigrated.", file=sys.stderr)


if __name__ == "__main__":
    main()
