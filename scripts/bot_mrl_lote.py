"""Genera el Excel en formato BOT MRL para un lote de liquidaciones.

Resuelve los IDs de `liquidaciones` a partir de las cédulas + fechas de salida
de un archivo de lote (`cedula, dd/mm/aaaa, motivo`) y llama a
`core.excel.liquidaciones_bot_mrl.bot_mrl_xlsx`.

    python -m scripts.bot_mrl_lote \
        --lote /ruta/lote_pegar_en_programa.txt \
        --salida /ruta/BOT_MRL_lote.xlsx \
        [--excel-basico /ruta/Liquidaciones_por_subir.xlsx]

`--excel-basico` (opcional): si `_sueldo_basico_rpemplea` no puede llegar a SQL
Server (p. ej. desde un sandbox sin ODBC), toma el sueldo básico de la columna
"Sueldo" (índice 3) de ese Excel — la fuente que ya se usó para la carga verbatim.
"""

from __future__ import annotations

import argparse
import contextlib
import sys

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--lote", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--excel-basico", default="")
    p.add_argument("--estado", default="", help="filtrar por estado (por defecto: cualquiera != borrador)")
    args = p.parse_args()

    from core.db import supabase_client
    from core.excel import liquidaciones_bot_mrl as bot
    from core.utils import normalizar_cedula

    # --- sueldo básico desde el Excel de origen (fallback sin SQL Server) ---
    if args.excel_basico:
        import openpyxl

        wb = openpyxl.load_workbook(args.excel_basico, read_only=True, data_only=True)
        ws = wb.active
        filas = list(ws.iter_rows(values_only=True))
        basico: dict[str, float] = {}
        for fila in filas[2:]:
            if len(fila) < 6 or fila[5] in (None, ""):
                continue
            ced = normalizar_cedula(str(fila[5]))
            raw = str(fila[3] or "").strip().replace(".", "").replace(",", ".")
            with contextlib.suppress(ValueError):
                basico[ced] = float(raw)
        orig = bot._sueldo_basico_rpemplea
        bot._sueldo_basico_rpemplea = lambda ced: basico.get(normalizar_cedula(ced)) or orig(ced)  # type: ignore[assignment]
        print(f"Sueldo básico desde Excel: {len(basico)} cédulas")

    sb = supabase_client.get_client()
    ids: list[str] = []
    sin_id: list[str] = []
    with open(args.lote, encoding="utf-8") as fh:
        lineas = fh.readlines()
    for ln in lineas:
        ln = ln.strip()
        if not ln:
            continue
        partes = [x.strip() for x in ln.split(",")]
        ced = normalizar_cedula(partes[0])
        d, m, y = partes[1].split("/")
        fsal = f"{y}-{int(m):02d}-{int(d):02d}"
        q = sb.table("liquidaciones").select("id,estado").eq("empleado_cedula", ced).eq("fecha_salida", fsal)
        q = q.eq("estado", args.estado) if args.estado else q.neq("estado", "borrador")
        rows = q.execute().data or []
        if rows:
            ids.append(rows[0]["id"])
        else:
            sin_id.append(f"{ced} {fsal}")

    print(f"Liquidaciones resueltas: {len(ids)} · sin registro: {len(sin_id)}")
    for s in sin_id:
        print(f"  sin registro: {s}")

    datos, advertencias, error = bot.bot_mrl_xlsx(ids)
    for a in advertencias:
        print(f"  aviso: {a}")
    if error:
        print(f"ERROR: {error}")
        return 1
    assert datos is not None
    with open(args.salida, "wb") as fh:
        fh.write(datos)
    print(f"\nOK -> {args.salida}  ({len(datos):,} bytes, {len(ids)} filas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
