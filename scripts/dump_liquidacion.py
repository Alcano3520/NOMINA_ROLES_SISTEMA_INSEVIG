"""Vuelca el resultado de `core.repos.liquidaciones.procesar_empleado` a JSON.

    python -m scripts.dump_liquidacion --cedula 0912345678 --fecha 30/06/2026 --motivo "RENUNCIA VOLUNTARIA"
    python -m scripts.dump_liquidacion --cedula 0912345678 --fecha 30/06/2026 --region SIERRA --json-only

Para la verificación de cálculo (item C): correr esto y comparar campo a campo
contra `nucleo_modular/scripts/dump_liquidacion.py` (LIQUIDACIONES_SISTEMA_INSEVIG)
para las mismas cédulas/fechas. NO escribe nada, no persiste.

Notas para comparar:
- Usar cédulas COSTA (el `procesamiento.py` de `nucleo_modular` tiene la región
  fija en 'COSTA'; una cédula SIERRA daría una falsa diferencia en Décima 14ta).
- NO usar motivos de despido: ninguno de los dos lados calcula `INDEM_DESPIDO`
  automáticamente (correcto), así que no valida nada ahí.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import sys

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cedula", required=True)
    p.add_argument("--fecha", required=True, help="fecha de salida dd/mm/aaaa")
    p.add_argument("--motivo", default="RENUNCIA VOLUNTARIA")
    p.add_argument("--fecha-ingreso", default="", help="override opcional")
    p.add_argument("--region", default="COSTA", choices=("COSTA", "SIERRA"))
    p.add_argument("--fuente", default="sqlserver", choices=("sqlserver", "supabase"))
    p.add_argument("--dec13-ant", action="store_true", help="incluir décimo 13 anterior")
    p.add_argument("--dec14-ant", action="store_true", help="incluir décimo 14 anterior")
    p.add_argument("--sin-sueldo", action="store_true", help="excluir el sueldo del mes de salida")
    p.add_argument("--json-only", action="store_true", help="solo el JSON de campos, sin metadata")
    args = p.parse_args()

    from core.parametros import config_liquidacion
    from core.repos.liquidaciones import procesar_empleado

    cfg = config_liquidacion(args.region)
    liq = procesar_empleado(
        args.cedula, args.fecha, args.motivo, args.fuente, cfg, args.fecha_ingreso,
        incluir_dec13_anterior=args.dec13_ant, incluir_dec14_anterior=args.dec14_ant,
        incluir_sueldo=not args.sin_sueldo,
    )

    campos = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in sorted(liq.campos.items())}
    if args.json_only:
        print(json.dumps(campos, ensure_ascii=False, indent=2))
        return 1 if liq.error else 0

    salida = {
        "entrada": {
            "cedula": args.cedula, "fecha_salida": args.fecha, "motivo": args.motivo,
            "region": args.region, "fuente": args.fuente,
            "dec13_ant": args.dec13_ant, "dec14_ant": args.dec14_ant,
            "incluir_sueldo": not args.sin_sueldo,
        },
        "empleado": {
            "codigo": liq.empleado, "nombre": liq.nombre, "cedula": liq.cedula,
            "cargo": liq.cargo, "seccion": liq.seccion,
            "fecha_ingreso": liq.fecha_ingreso, "fecha_salida": liq.fecha_salida,
            "dias_trabajados": liq.dias_trabajados,
        },
        "error": liq.error or None,
        "alertas": list(liq.alertas),
        "campos": campos,
        "detalle_vacaciones": [dataclasses.asdict(d) for d in liq.detalle_vacaciones],
        "detalle_decimo_tercera": [dataclasses.asdict(d) for d in liq.detalle_decimo_tercera],
    }
    print(json.dumps(salida, ensure_ascii=False, indent=2))
    return 1 if liq.error else 0


if __name__ == "__main__":
    sys.exit(main())
