"""Carga masiva de liquidaciones desde un lote, verificando contra los totales
del Excel de referencia antes de guardar.

Correr en el NAS (necesita SQL Server + Supabase):

    # 1) Solo verificar (NO toca Supabase):
    python -m scripts.cargar_lote_liquidaciones \
        --lote /ruta/lote_pegar_en_programa.txt \
        --referencia /ruta/referencia_totales_excel.tsv

    # 2) Verificar y guardar las que cuadran y no existan ya:
    python -m scripts.cargar_lote_liquidaciones --lote ... --referencia ... --guardar

`--lote`: líneas `cedula, dd/mm/aaaa, MOTIVO` (formato de `procesar_lote`).
`--referencia`: TSV con cabecera `cedula<TAB>nombre<TAB>fecha_salida<TAB>total_excel`
(el total en formato Ecuador: `1.234,56`).

Para cada cédula: `procesar_empleado` (motivo del lote, `--region`, `--fuente`) y
se compara `TOTAL_A_RECIBIR` con `total_excel`.
  - |dif| <= --tolerancia  -> cuadra. Con --guardar: se guarda (estado 'generada',
    mismo flujo que el modo Lote web) salvo que ya exista (cedula+fecha_salida).
  - |dif|  > --tolerancia  -> NO se guarda nunca; se reporta.
  - error de cálculo        -> NO se guarda; se reporta.

Imprime un resumen y escribe un CSV con el detalle fila por fila.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import sys

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def _num_ec(txt: str) -> float | None:
    """'1.234,56' / '900,00' / '900' -> float. None si no parsea."""
    s = (txt or "").strip().replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _aplicar_defaults(liq, mult: float, ant: float) -> list[str]:
    """Aplica los 'Valores por Defecto' del .pyw a `liq.campos` (MULTAS /
    ANTICIPOS_OTROS cuando el movimiento real da 0) y recalcula los totales.
    Ambos son descuentos planos, así que no afectan a IESS ni a otros conceptos."""
    c = liq.campos
    cambios: list[str] = []
    delta = 0.0
    if mult and float(c.get("MULTAS") or 0) == 0:
        c["MULTAS"] = mult
        delta += mult
        cambios.append(f"MULTAS={mult:g}")
    if ant and float(c.get("ANTICIPOS_OTROS") or 0) == 0:
        c["ANTICIPOS_OTROS"] = ant
        delta += ant
        cambios.append(f"ANTICIPOS_OTROS={ant:g}")
    if delta:
        c["TOTAL_DESCUENTOS"] = round(float(c.get("TOTAL_DESCUENTOS") or 0) + delta, 2)
        c["TOTAL_A_RECIBIR"] = round(
            float(c.get("TOTAL_INGRESOS") or 0) - float(c["TOTAL_DESCUENTOS"]), 2
        )
    return cambios


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--lote", required=True)
    p.add_argument("--referencia", required=True)
    p.add_argument("--fuente", default="sqlserver", choices=("sqlserver", "supabase"))
    p.add_argument("--region", default="COSTA", choices=("COSTA", "SIERRA"))
    p.add_argument("--tolerancia", type=float, default=0.50,
                   help="diferencia máxima en $ para considerar que cuadra (default 0.50)")
    p.add_argument("--default-multas", type=float, default=0.0,
                   help="valor fijo a MULTAS cuando el movimiento real da 0 "
                        "(campo 'Valores por Defecto' del .pyw, no portado; para esta reconciliación)")
    p.add_argument("--default-anticipos-otros", type=float, default=0.0,
                   help="ídem para ANTICIPOS_OTROS")
    p.add_argument("--usuario", default="carga_lote")
    p.add_argument("--guardar", action="store_true",
                   help="sin este flag es dry-run: solo verifica, no toca Supabase")
    p.add_argument("--reporte", default="reporte_carga_lote_liquidaciones.csv")
    args = p.parse_args()

    from core.parametros import config_liquidacion
    from core.repos import liquidaciones as repo
    from core.utils import normalizar_cedula

    cfg = config_liquidacion(args.region)

    # --- referencia: cédula normalizada -> (nombre, total_excel) ---
    ref: dict[str, tuple[str, float | None]] = {}
    with open(args.referencia, encoding="utf-8") as fh:
        rd = csv.reader(fh, delimiter="\t")
        next(rd, None)  # cabecera
        for row in rd:
            if len(row) < 4:
                continue
            ced, nombre, _fsal, total = row[0], row[1], row[2], row[3]
            ref[normalizar_cedula(ced)] = (nombre.strip(), _num_ec(total))

    # --- lote ---
    with open(args.lote, encoding="utf-8") as fh:
        texto = fh.read()
    lineas = [ln for ln in texto.splitlines() if ln.strip()]

    print(f"Lote: {len(lineas)} líneas · referencia: {len(ref)} cédulas · "
          f"fuente={args.fuente} región={args.region} tol=${args.tolerancia:.2f} · "
          f"{'GUARDAR' if args.guardar else 'DRY-RUN (no guarda)'}\n")

    liqs = repo.procesar_lote(texto, args.fuente, cfg)

    filas_rep: list[dict] = []
    n_ok = n_guardadas = n_existian = n_dif = n_error = n_sin_ref = 0

    for ln, liq in zip(lineas, liqs, strict=False):
        ced_in = normalizar_cedula(ln.split(",")[0])
        nombre_ref, total_esp = ref.get(ced_in, ("", None))
        base = {
            "cedula": ced_in, "nombre": nombre_ref or liq.nombre,
            "fecha_salida": liq.fecha_salida, "total_excel": total_esp,
            "total_calculado": "", "diferencia": "", "resultado": "",
            "defaults_aplicados": "", "detalle": "",
        }

        if liq.error:
            n_error += 1
            base["resultado"] = "ERROR_CALCULO"
            base["detalle"] = liq.error
            filas_rep.append(base)
            print(f"  ERROR   {ced_in} {nombre_ref[:28]:<28} {liq.error}")
            continue

        cambios = _aplicar_defaults(liq, args.default_multas, args.default_anticipos_otros)
        base["defaults_aplicados"] = " ".join(cambios)

        total_calc = round(float(liq.campos.get("TOTAL_A_RECIBIR") or 0), 2)
        base["total_calculado"] = total_calc

        if total_esp is None:
            n_sin_ref += 1
            base["resultado"] = "SIN_REFERENCIA"
            filas_rep.append(base)
            print(f"  SIN-REF {ced_in} {nombre_ref[:28]:<28} calc={total_calc:,.2f}")
            continue

        dif = round(total_calc - total_esp, 2)
        base["diferencia"] = dif

        if abs(dif) > args.tolerancia:
            n_dif += 1
            base["resultado"] = "DIFERENCIA"
            filas_rep.append(base)
            print(f"  DIFF    {ced_in} {nombre_ref[:28]:<28} "
                  f"excel={total_esp:,.2f} calc={total_calc:,.2f} dif={dif:+,.2f}")
            continue

        n_ok += 1
        if not args.guardar:
            base["resultado"] = "CUADRA"
            filas_rep.append(base)
            print(f"  OK      {ced_in} {nombre_ref[:28]:<28} {total_calc:,.2f} (dif {dif:+.2f})")
            continue

        existente = repo.buscar_liquidacion_existente(ced_in, liq.fecha_salida, "generada")
        if existente:
            n_existian += 1
            base["resultado"] = "YA_EXISTIA"
            base["detalle"] = existente
            filas_rep.append(base)
            print(f"  SKIP    {ced_in} {nombre_ref[:28]:<28} ya existe ({existente})")
            continue

        ok, res = repo.guardar_liquidacion(
            liq, "generada", cfg, usuario=args.usuario, roles={args.usuario},
        )
        if ok:
            n_guardadas += 1
            base["resultado"] = "GUARDADA"
            base["detalle"] = res
            print(f"  SAVE    {ced_in} {nombre_ref[:28]:<28} {total_calc:,.2f} -> {res}")
        else:
            n_error += 1
            base["resultado"] = "ERROR_GUARDAR"
            base["detalle"] = res
            print(f"  ERRSAV  {ced_in} {nombre_ref[:28]:<28} {res}")
        filas_rep.append(base)

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(filas_rep[0].keys()) if filas_rep else [])
    w.writeheader()
    w.writerows(filas_rep)
    with open(args.reporte, "w", encoding="utf-8") as fh:
        fh.write(buf.getvalue())

    print(
        "\n─── Resumen ───\n"
        f"  cuadran (|dif| <= tol) : {n_ok}\n"
        + (f"    guardadas ahora      : {n_guardadas}\n"
           f"    ya existían (skip)   : {n_existian}\n" if args.guardar else "")
        + f"  diferencia de monto    : {n_dif}\n"
        f"  error de cálculo       : {n_error}\n"
        f"  sin total de referencia: {n_sin_ref}\n"
        f"  total procesadas       : {len(filas_rep)}\n"
        f"\n  reporte -> {args.reporte}"
    )
    return 1 if (n_dif or n_error) else 0


if __name__ == "__main__":
    sys.exit(main())
