"""Importa liquidaciones YA CALCULADAS desde el Excel LIQUIDACIONES_REG
(62+ columnas del `.pyw`), respetando los montos del Excel — sin recalcular.

Correr con acceso a Supabase.

    # dry-run (no toca nada), muestra qué haría:
    python -m scripts.importar_liquidaciones_excel --excel /ruta/Liquidaciones_por_subir.xlsx

    # aplicar de verdad:
    python -m scripts.importar_liquidaciones_excel --excel ... --guardar

Por cada fila del Excel busca en `liquidaciones` (estado != borrador) un
registro con la misma cédula + fecha de salida:
  - no existe            -> FALTA   : INSERT (estado 'generada')
  - existe y coincide     -> OK      : nada (|total_liquido - Excel| <= tol)
  - existe y NO coincide   -> CORRIGE : UPDATE de montos + conceptos + desglose
                             mensual, CONSERVANDO el estado actual del registro.

`--solo faltantes` o `--solo correcciones` limita a un caso. Escribe un CSV
con el detalle.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import sys

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--excel", required=True)
    p.add_argument("--region", default="COSTA", choices=("COSTA", "SIERRA"))
    p.add_argument("--tolerancia", type=float, default=0.50)
    p.add_argument("--usuario", default="carga_historica_excel")
    p.add_argument("--solo", choices=("faltantes", "correcciones"), default="")
    p.add_argument("--guardar", action="store_true",
                   help="sin este flag es dry-run: no toca Supabase")
    p.add_argument("--reporte", default="reporte_import_liquidaciones_excel.csv")
    args = p.parse_args()

    from core.db import supabase_client
    from core.excel.liquidaciones_import import parse_excel_liquidaciones
    from core.parametros import config_liquidacion
    from core.repos import liquidaciones as repo

    cfg = config_liquidacion(args.region)
    with open(args.excel, "rb") as fh:
        liqs, errores_parse = parse_excel_liquidaciones(fh.read())

    print(f"Excel: {len(liqs)} liquidaciones parseadas · {len(errores_parse)} filas con error de parseo · "
          f"{'GUARDAR' if args.guardar else 'DRY-RUN'}\n")
    for e in errores_parse:
        print(f"  parseo: {e}")

    sb = supabase_client.get_client()
    filas_rep: list[dict] = []
    n_falta = n_ok = n_corrige = n_err = 0

    for liq in liqs:
        ced, fsal = liq.cedula, liq.fecha_salida
        excel_total = round(float(liq.campos.get("TOTAL_A_RECIBIR") or 0), 2)
        base = {
            "cedula": ced, "nombre": liq.nombre, "fecha_salida": fsal,
            "total_excel": excel_total, "total_supabase": "", "estado": "",
            "situacion": "", "accion": "", "detalle": "",
        }

        existentes = (
            sb.table(repo.TABLA_LIQ).select("id,estado,total_liquido")
            .eq("empleado_cedula", ced).eq("fecha_salida", fsal)
            .neq("estado", "borrador").execute().data or []
        )

        # ── caso 1: no existe -> INSERT ────────────────────────────────
        if not existentes:
            n_falta += 1
            base["situacion"] = "FALTA"
            if args.solo == "correcciones" or not args.guardar:
                base["accion"] = (
                    "insertaría (estado 'generada')" if not args.guardar
                    else "omitida (--solo correcciones)"
                )
                filas_rep.append(base)
                print(f"  FALTA   {ced} {liq.nombre[:30]:<30} excel={excel_total:,.2f}  {base['accion']}")
                continue
            ok, res = repo.guardar_liquidacion(
                liq, "generada", cfg, usuario=args.usuario, roles={args.usuario},
            )
            base["accion"] = "INSERT ok" if ok else "INSERT ERROR"
            base["detalle"] = res
            n_err += 0 if ok else 1
            filas_rep.append(base)
            print(f"  {'INSERT ' if ok else 'ERROR  '}{ced} {liq.nombre[:30]:<30} excel={excel_total:,.2f}  {res}")
            continue

        reg = existentes[0]
        tl = round(float(reg.get("total_liquido") or 0), 2)
        estado_actual = reg.get("estado") or ""
        base["total_supabase"] = tl
        base["estado"] = estado_actual

        # ── caso 2: existe y coincide -> nada ─────────────────────────
        if abs(tl - excel_total) <= args.tolerancia:
            n_ok += 1
            base["situacion"] = "OK"
            base["accion"] = "sin cambios"
            filas_rep.append(base)
            continue

        # ── caso 3: existe y NO coincide -> UPDATE conservando estado ──
        n_corrige += 1
        base["situacion"] = "NO_COINCIDE"
        base["detalle"] = f"dif {round(excel_total - tl, 2):+.2f}"
        if args.solo == "faltantes" or not args.guardar:
            base["accion"] = (
                f"corregiría {tl:,.2f} -> {excel_total:,.2f} (estado {estado_actual})"
                if not args.guardar else "omitida (--solo faltantes)"
            )
            filas_rep.append(base)
            print(f"  CORRIGE {ced} {liq.nombre[:30]:<30} {tl:,.2f} -> {excel_total:,.2f}  [{estado_actual}]")
            continue

        if estado_actual not in repo.ESTADOS_LIQUIDACION:
            base["accion"] = "ERROR"
            base["detalle"] = f"estado '{estado_actual}' no está en ESTADOS_LIQUIDACION — no se corrige"
            n_err += 1
            filas_rep.append(base)
            print(f"  ERROR   {ced} {liq.nombre[:30]:<30} estado '{estado_actual}' inválido para guardar")
            continue

        ok, res = repo.guardar_liquidacion(
            liq, estado_actual, cfg, usuario=args.usuario, roles={args.usuario},
            liquidacion_id_existente=reg["id"],
        )
        base["accion"] = "UPDATE ok" if ok else "UPDATE ERROR"
        base["detalle"] = res
        n_err += 0 if ok else 1
        filas_rep.append(base)
        print(f"  {'UPDATE ' if ok else 'ERROR  '}{ced} {liq.nombre[:30]:<30} {tl:,.2f} -> {excel_total:,.2f}  {res}")

    buf = io.StringIO()
    if filas_rep:
        w = csv.DictWriter(buf, fieldnames=list(filas_rep[0].keys()))
        w.writeheader()
        w.writerows(filas_rep)
    with open(args.reporte, "w", encoding="utf-8") as fh:
        fh.write(buf.getvalue())

    print(
        "\n─── Resumen ───\n"
        f"  faltan / a insertar : {n_falta}\n"
        f"  ya OK (coinciden)   : {n_ok}\n"
        f"  a corregir          : {n_corrige}\n"
        f"  errores             : {n_err}\n"
        f"  parseo con error    : {len(errores_parse)}\n"
        f"\n  reporte -> {args.reporte}"
    )
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
