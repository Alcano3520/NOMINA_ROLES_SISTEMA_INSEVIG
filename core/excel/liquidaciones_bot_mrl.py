"""Excel en el formato EXACTO que espera el bot RPA de liquidaciones para
llenar el formulario del SUT (MRL).

Portado 1:1 de `LIQUIDACIONES_SISTEMA_INSEVIG/nucleo_modular/generacion_bot_mrl.py`
(que a su vez porta `_generar_formato_bot_mrl` del `.pyw`, líneas ~7692-8048),
adaptado a este repo: lee de Supabase (`liquidaciones`, `liquidaciones_detalle`,
`liquidaciones_periodos_calculo`), SQL Server es opcional, devuelve bytes.

LIMITACIÓN HEREDADA: `_MESES_DECIMO_VIGENTE` está fijo al periodo Dic2025-Nov2026.
Desde diciembre 2026 hay que actualizarlo a mano.

LIMITACIÓN DE ESTA CAPA: si `liquidaciones_periodos_calculo` no tiene el desglose
mensual del décimo tercero (hoy `guardar_liquidacion` no lo persiste — falta que
el motor de cálculo exponga `detalle_decimo_tercera`), las 24 columnas mensuales
del décimo salen en 0; los totales generales sí funcionan.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import io

from core.db import supabase_client
from core.utils import normalizar_cedula

_MESES_NOMBRE = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}
_MESES_ABREV = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
}
_NOMBRE_A_NUM = {v: k for k, v in _MESES_NOMBRE.items()}

_MESES_DECIMO_VIGENTE = {
    (2025, 12): "DICIEMBRE_25", (2026, 1): "ENERO_26", (2026, 2): "FEBRERO_26",
    (2026, 3): "MARZO_26", (2026, 4): "ABRIL_26", (2026, 5): "MAYO_26",
    (2026, 6): "JUNIO_26", (2026, 7): "JULIO_26", (2026, 8): "AGOSTO_26",
    (2026, 9): "SEPTIEMBRE_26", (2026, 10): "OCTUBRE_26", (2026, 11): "NOVIEMBRE_26",
}
_COL_DECIMO_TODAS = [
    "DICIEMBRE", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO",
    "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE",
    "DICIEMBRE_25", "ENERO_26", "FEBRERO_26", "MARZO_26", "ABRIL_26", "MAYO_26",
    "JUNIO_26", "JULIO_26", "AGOSTO_26", "SEPTIEMBRE_26", "OCTUBRE_26", "NOVIEMBRE_26",
]
_COL_DECIMO_VESTIGIAL = [
    "DICIEMBRE_24", "ENERO_25", "FEBRERO_25", "MARZO_25", "ABRIL_25", "MAYO_25",
    "JUNIO_25", "JULIO_25", "AGOSTO_25", "SEPTIEMBRE_25", "OCTUBRE_25", "NOVIEMBRE_25",
]
_DESCUENTOS = [
    ("ANTICIPOS_1", "ANTICIPOS_SURTIDOS"), ("ANTICIPOS_MOVILIZACION_1", None),
    ("PRESTAMOS", "PREST_COMPANIA"), ("ANTICIPOS_OTROS", "ANTICIPOS_OTROS"),
    ("QUINCENA", "ANTICIPO_SUELDO"), ("MULTAS", "MULTAS"),
    ("PREST_QUIROGRA", "PREST_QUIROGRAFARIO"), ("CONYUGUE", "IESS_CONYUGE"),
    ("PENSION_ALIMENTICIA", "PENSION_ALIMENTICIA"), ("PREST_HIPOTECARIO", "PREST_HIPOTECARIO"),
    ("ANTICIPOS_L", "ANTICIPOS_OTROS_L"), ("ANTICIPO_L_DES", "ANTICIPO_L_DESAHUCIO"),
]

_ENCABEZADOS = [
    "Cod", "Nombres", "cedula", "SUELDO_MENSUAL", "Nomdep", "Seccion", "REMUNERACION",
    "Fecha Ingreso", "Fecha Salida", "SALIDA_DIA", "SALIDA_MES", "SALIDA_AÑO", "DIAS",
    "SALARIO_PENDIENTE_DIAS", 25, 50, 100, "RECARGO DEL 25% NOCHE", "RECARGO DEL 50%",
    "NOCHE RECARGO DEL 100%", "MANIOBRAS", "BONIFICACION",
    "MOVILIZACION-BONO DE TRANSP - ALIMENT", "DEVOLUCION Y/O ACREDIT", "FONDO_RESERVA",
    "TOTAL INGRESO SUELDO", "13anterior", "13era Remuneracion", "14anterior",
    "14ta Remuneracion", "VACACIONES_penultimas", "VACACIONES_ultimas",
    "VacacionesAnteriores", "VACACIONES_TOTAL", "VALOR_VAVACIONES",
    "DESAHUCIO 25%Y OTROS", "OTROS INGRESOS", "TOTAL_INGRESOS", "TOTAL LIQUIDACION",
    "INGRESOS", "IESS 9.45%", "ANTICIPOS_1", "ANTICIPOS_MOVILIZACION_1", "ANTICIPOS_2",
    "ANTICIPOS_MOVILIZACION_2", "PRESTAMOS", "ANTICIPOS_OTROS", "QUINCENA", "MULTAS",
    "PREST_QUIROGRA", "CONYUGUE", "PENSION_ALIMENTICIA", "PREST_HIPOTECARIO",
    "ANTICIPOS_L", "ANTICIPO_L_DES", "TOTAL_DESCUENTOS", "EGRESOS", "TOTAL_FINIQUITO",
    "CUADRE", "cuadre_2", "DECIMO_PENDIENTE", "DECIMO4TO_PENDIENTE",
] + _COL_DECIMO_TODAS[:12] + ["MES_COM"] + _COL_DECIMO_VESTIGIAL + _COL_DECIMO_TODAS[12:]


def _sueldo_basico_rpemplea(cedula: str) -> float | None:
    try:
        from core.db import sqlserver

        with sqlserver.conexion() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT SUELDO FROM RPEMPLEA WHERE CODEMP='10' AND CODSUC='10' AND CEDULA=?",
                int(cedula),
            )
            fila = cur.fetchone()
        return float(fila[0]) if fila and fila[0] is not None else None
    except Exception:  # noqa: BLE001 - SQL Server opcional
        return None


def bot_mrl_xlsx(liquidacion_ids: list[str]) -> tuple[bytes | None, list[str], str | None]:
    """`(bytes | None, advertencias, error | None)` — Excel del bot RPA MRL para
    las liquidaciones indicadas."""
    if not liquidacion_ids:
        return None, [], "Selecciona una o más liquidaciones."
    sb = supabase_client.get_client()
    advertencias: list[str] = []
    if dt.datetime.now() >= dt.datetime(2026, 12, 1):
        advertencias.append(
            "El mapeo de meses del décimo tercero es del periodo Dic2025-Nov2026 y "
            "ya pasó diciembre 2026: revisa _MESES_DECIMO_VIGENTE antes de confiar en "
            "esas columnas."
        )
    filas_bot: list[dict] = []

    for reg_id in liquidacion_ids:
        r = sb.table("liquidaciones").select("*").eq("id", reg_id).limit(1).execute().data or []
        if not r:
            advertencias.append(f"{reg_id}: no se encontró la liquidación.")
            continue
        registro = r[0]
        cedula = normalizar_cedula(registro.get("empleado_cedula", ""))
        if cedula == "0000000000":
            cedula = ""
        nombres = (
            f"{registro.get('empleado_apellidos', '') or ''} "
            f"{registro.get('empleado_nombres', '') or ''}"
        ).strip()

        conceptos = (
            sb.table("liquidaciones_detalle").select("concepto_codigo,valor_total")
            .eq("liquidacion_id", reg_id).execute().data or []
        )
        val = {c.get("concepto_codigo"): float(c.get("valor_total", 0) or 0) for c in conceptos}

        valor_por_mes_real: dict[tuple[int, int], float] = {}
        try:
            periodos = (
                sb.table("liquidaciones_periodos_calculo").select("tipo,meses")
                .eq("liquidacion_id", reg_id).eq("tipo", "DEC_TERCERA").execute().data or []
            )
        except Exception:  # noqa: BLE001 - tabla opcional
            periodos = []
        for m in (periodos[0].get("meses") or []) if periodos else []:
            label = (m.get("label") or "").strip()
            if " -" not in label:
                continue
            nombre_mes, anio_str = label.rsplit(" -", 1)
            mes_num = _NOMBRE_A_NUM.get(nombre_mes.strip().lower())
            try:
                anio_num = int(anio_str.strip())
            except ValueError:
                continue
            if mes_num is not None:
                valor_por_mes_real[(anio_num, mes_num)] = round(float(m.get("valor", 0) or 0), 2)
        if not valor_por_mes_real and (val.get("DEC_TERCERA_ACT") or 0) > 0:
            advertencias.append(
                f"{cedula} {nombres}: sin desglose mensual del décimo tercero "
                "(liquidaciones_periodos_calculo vacío) — las 24 columnas mensuales van en 0."
            )

        fecha_sal_str = registro.get("fecha_salida") or ""
        fecha_sal_dt = None
        if fecha_sal_str:
            with contextlib.suppress(ValueError):
                fecha_sal_dt = dt.datetime.strptime(fecha_sal_str[:10], "%Y-%m-%d")

        remuneracion = round(
            val.get("SUELDO", 0.0) + val.get("SOBT_25", 0.0)
            + val.get("SOBT_50", 0.0) + val.get("SOBT_100", 0.0), 2
        )
        sueldo_basico = _sueldo_basico_rpemplea(cedula) if cedula else None
        if sueldo_basico is None:
            sueldo_basico = val.get("SUELDO", 0.0)
            advertencias.append(
                f"{cedula} {nombres}: no se pudo confirmar el sueldo básico en RPEMPLEA "
                "— se usó el proporcional del mes en 'SUELDO_MENSUAL', revisar."
            )
        valor_hora_base = (sueldo_basico / 240) if sueldo_basico else 0.0

        def _horas(clave_cant: str, clave_dolar: str, mult: float, reg=registro, vh=valor_hora_base, v=val) -> int:
            cant = reg.get(clave_cant)
            if cant:
                return int(round(float(cant)))
            dol = v.get(clave_dolar, 0.0)
            return int(round(dol / (vh * mult))) if vh > 0 and dol > 0 else 0

        h25 = _horas("horas_25_cantidad", "SOBT_25", 0.25)
        h50 = _horas("horas_50_cantidad", "SOBT_50", 1.5)
        h100 = _horas("horas_100_cantidad", "SOBT_100", 2.0)

        mes_num_sal = fecha_sal_dt.month if fecha_sal_dt else None
        vacaciones_pagado = round(float(registro.get("vacaciones_pendientes", 0) or 0), 2)
        vacaciones_total = round(vacaciones_pagado * 24, 2)
        desahucio = round(
            val.get("DESAHUCIO", float(registro.get("bonificacion_desahucio", 0) or 0)), 2
        )

        fila = {
            "Cod": registro.get("empleado_codigo", "") or "",
            "Nombres": nombres, "cedula": cedula,
            "SUELDO_MENSUAL": round(sueldo_basico, 2),
            "Nomdep": registro.get("puesto_servicio", "") or "",
            "Seccion": registro.get("seccion", "") or "",
            "REMUNERACION": remuneracion,
            "Fecha Ingreso": registro.get("fecha_ingreso") or "", "Fecha Salida": fecha_sal_str,
            "SALIDA_DIA": fecha_sal_dt.day if fecha_sal_dt else 0,
            "SALIDA_MES": _MESES_ABREV.get(mes_num_sal or 0, "").capitalize(),
            "SALIDA_AÑO": (fecha_sal_dt.year if fecha_sal_dt else 0),
            "DIAS": registro.get("dias_trabajados", 0) or 0,
            "SALARIO_PENDIENTE_DIAS": round(val.get("SUELDO", 0.0), 2),
            25: h25, 50: h50, 100: h100,
            "RECARGO DEL 25% NOCHE": round(val.get("SOBT_25", 0.0), 2),
            "RECARGO DEL 50%": round(val.get("SOBT_50", 0.0), 2),
            "NOCHE RECARGO DEL 100%": round(val.get("SOBT_100", 0.0), 2),
            "MANIOBRAS": round(val.get("MANIOBRAS", 0.0), 2),
            "BONIFICACION": round(val.get("BONIFICACION", 0.0), 2),
            "MOVILIZACION-BONO DE TRANSP - ALIMENT": round(val.get("MOVILIZACION", 0.0), 2),
            "DEVOLUCION Y/O ACREDIT": 0.0,
            "FONDO_RESERVA": round(
                val.get("FONDO_RESERVA", float(registro.get("fondo_reserva", 0) or 0)), 2
            ),
            "TOTAL INGRESO SUELDO": 0.0,
            "13anterior": 0.0,   # regla de negocio: el anterior no pagado nunca se reporta
            "13era Remuneracion": round(val.get("DEC_TERCERA_ACT", 0.0), 2),
            "14anterior": 0.0,
            "14ta Remuneracion": round(val.get("DEC_CUARTA_ACT", 0.0), 2),
            "VACACIONES_penultimas": 0.0, "VACACIONES_ultimas": vacaciones_total,
            "VacacionesAnteriores": 0.0, "VACACIONES_TOTAL": vacaciones_total,
            "VALOR_VAVACIONES": vacaciones_pagado,
            "DESAHUCIO 25%Y OTROS": desahucio,
            "OTROS INGRESOS": round(val.get("INDEM_DESPIDO", 0.0) + val.get("AJUSTE_CUADRE", 0.0), 2),
            "TOTAL_INGRESOS": round(
                val.get("BONIFICACION", 0.0) + val.get("MOVILIZACION", 0.0)
                + val.get("INDEM_DESPIDO", 0.0) + val.get("AJUSTE_CUADRE", 0.0), 2
            ),
            "TOTAL LIQUIDACION": round(
                val.get("DEC_TERCERA_ACT", 0.0) + val.get("DEC_CUARTA_ACT", 0.0)
                + vacaciones_pagado + desahucio, 2
            ),
            "INGRESOS": 0.0,
            "IESS 9.45%": round(val.get("IESS", 0.0), 2),
            "DECIMO_PENDIENTE": 0.0, "DECIMO4TO_PENDIENTE": 0.0,
            "MES_COM": _MESES_NOMBRE.get(mes_num_sal or 0, "").capitalize(),
            "CUADRE": 0.0, "cuadre_2": 0.0,
        }
        for col_bot, cod_local in _DESCUENTOS:
            fila[col_bot] = round(val.get(cod_local, 0.0), 2) if cod_local else 0.0
        fila["TOTAL_DESCUENTOS"] = round(float(registro.get("total_descuentos", 0) or 0), 2)
        fila["EGRESOS"] = 0.0
        fila["TOTAL_FINIQUITO"] = round(float(registro.get("total_liquido", 0) or 0), 2)
        for col in _COL_DECIMO_TODAS + _COL_DECIMO_VESTIGIAL:
            fila[col] = 0.0
        for (anio_m, mes_m), col_vig in _MESES_DECIMO_VIGENTE.items():
            if (anio_m, mes_m) in valor_por_mes_real:
                fila[col_vig] = valor_por_mes_real[(anio_m, mes_m)]
        filas_bot.append(fila)

    if not filas_bot:
        return None, advertencias, "No se generó ninguna fila."

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Hoja1"
    ws.append(_ENCABEZADOS)
    for fila in filas_bot:
        ws.append([fila.get(h, 0) for h in _ENCABEZADOS])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), advertencias, None
