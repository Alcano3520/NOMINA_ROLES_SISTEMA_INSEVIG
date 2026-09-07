"""Prueba de humo de las lecturas de `core/repos/*` contra datos reales.

    python -m scripts.humo_repos --empleado 1012 --periodo 2026-06
    python -m scripts.humo_repos --empleado 1012 --periodo 2026-06 --fuente supabase

Llama las funciones de lectura principales de cada repo con un empleado y un
período reales y reporta cuáles fallan (útil para cazar columnas inventadas que
sólo revientan contra el SQL Server real, como pasó con `creado_por` en
empleados). NO escribe nada.

Sale con código ≠ 0 si alguna lectura falla.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import sys
import traceback

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def _run(nombre: str, fn) -> bool:
    try:
        r = fn()
        n = len(r) if hasattr(r, "__len__") else ("None" if r is None else "ok")
        print(f"  OK    {nombre}  ({n})")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  FALLA {nombre}: {type(e).__name__}: {str(e).splitlines()[0][:160]}")
        if "--traceback" in sys.argv:
            traceback.print_exc()
        return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--empleado", required=True, help="código de empleado")
    p.add_argument("--periodo", required=True, help="AAAA-MM")
    p.add_argument("--fuente", default="sqlserver", choices=("sqlserver", "supabase"))
    p.add_argument("--traceback", action="store_true")
    args = p.parse_args()
    emp, per, fte = args.empleado, args.periodo, args.fuente
    anio, mes = (int(x) for x in per.split("-"))

    from core.datos.service import datos_empleado
    from core.repos import empleados, liquidaciones, nomina, observaciones, prestamos, registrador

    ok = True
    print(f"empleado {emp} · período {per} · fuente {fte}\n")

    print("datos / nómina:")
    ok &= _run("datos_empleado", lambda: datos_empleado(per, emp, fte))
    ok &= _run("nomina.empleados_del_periodo", lambda: nomina.empleados_del_periodo(per, fuente=fte))

    print("empleados:")
    ok &= _run("empleados.buscar('')", lambda: empleados.buscar("", fte, limite=5))
    ok &= _run("empleados.obtener", lambda: empleados.obtener(emp, fte))
    ok &= _run("empleados.catalogos", lambda: empleados.catalogos(fte))
    ok &= _run("empleados.buscar_avanzado", lambda: empleados.buscar_avanzado(fte, apellidos="A", limite=5))

    print("observaciones:")
    ok &= _run("observaciones.observaciones", lambda: observaciones.observaciones(emp, fte))
    ok &= _run("observaciones.multas", lambda: observaciones.multas(emp, fte))
    ok &= _run("observaciones.faltas", lambda: observaciones.faltas(emp, fte))
    ok &= _run("observaciones.historial_observaciones", lambda: observaciones.historial_observaciones(emp, fte))
    ok &= _run("observaciones.datos_basicos_empleado", lambda: observaciones.datos_basicos_empleado(emp, fte))

    print("préstamos:")
    ok &= _run("prestamos.historial_empleado", lambda: prestamos.historial_empleado(emp, fte))
    ok &= _run("prestamos.saldo_total", lambda: prestamos.saldo_total(emp, fte))

    print("registrador:")
    ok &= _run(
        "registrador.historial_movimientos",
        lambda: registrador.historial_movimientos(fte, empleado=emp),
    )
    ok &= _run(
        "registrador.consultar_filas",
        lambda: registrador.consultar_filas(fte, empleado=emp),
    )
    ok &= _run(
        "registrador.proyeccion_pagos_futuros",
        lambda: registrador.proyeccion_pagos_futuros(emp, fte),
    )

    print("liquidaciones:")
    ok &= _run(
        "liquidaciones.movimientos_mes",
        lambda: liquidaciones.movimientos_mes(emp, anio, mes, fte),
    )
    ok &= _run(
        "liquidaciones.buscar_empleado_preview",
        lambda: liquidaciones.buscar_empleado_preview(emp, "codigo", fte),
    )

    print(f"\n{'TODO OK' if ok else 'HAY FALLOS'}  ({dt.date.today()})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
