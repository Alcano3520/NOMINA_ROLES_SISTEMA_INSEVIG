"""Generación de liquidaciones (finiquitos) — módulo 9.

Porta **completo** `LIQUIDACIONES_SISTEMA_INSEVIG/Liquidaciones_generador_CON_VACACIONES.pyw`
(la versión con vacaciones/décimos/desahucio) adaptado a `core`. Cálculos legales
de Ecuador: vacaciones, décima tercera, décima cuarta (por región), desahucio,
indemnización por despido intempestivo, IESS, fondo de reserva, split de anticipos.

Entrada: (cédula, fecha_salida, motivo_salida). Salida: dict por empleado + Excel 62 col.
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass, field

from core.config import get_settings
from core.db import sqlserver, supabase_client
from core.db.health import FUENTE_SUPABASE
from core.utils import a_float, a_int, normalizar_cedula

# ── Constantes del legado ────────────────────────────────────────────────────

MAPEO_CONCEPTOS = {
    100: "SUELDO", 102: "BONIFICACION", 104: "FONDO_RESERVA", 107: "DECIMO_TERCERA",
    108: "DECIMO_CUARTA", 110: "MANIOBRAS", 111: "REEMBOLSOS", 113: "SOBRETIEMPO_25",
    114: "SOBRETIEMPO_50", 115: "SOBRETIEMPO_100", 120: "MOVILIZACION", 200: "APORT_IESS",
    201: "ANTICIPOS_OTROS", 202: "ANTICIPO_SUELDO", 203: "MULTAS", 204: "PRESTAMOS_QUIROGRAFARIOS",
    205: "PRESTAMOS_COMPANIA", 206: "PENSION_ALIMENTICIA", 207: "PRESTAMO_HIPOTECARIO",
    217: "ANTICIPOS_OTROS", 218: "APORT_IESS_CONYUGE", 219: "IMPUESTO_RENTA", 250: "ANTICIPOS_SURTIDOS",
}
CODIGOS_IGNORAR = {105, 126, 199}
DESCUENTOS_MULTI_MES = {
    "PRESTAMOS_COMPANIA", "ANTICIPOS_OTROS", "ANTICIPO_SUELDO", "MULTAS",
    "PRESTAMOS_QUIROGRAFARIOS", "APORT_IESS_CONYUGE", "PENSION_ALIMENTICIA",
    "PRESTAMO_HIPOTECARIO", "ANTICIPOS_SURTIDOS",
}
CONCEPTOS_BASE = [100, 102, 110, 113, 114, 115]  # SUELDO+BONIF+MANIOBRAS+SOBRETIEMPOS
CONCEPTOS_BASE_SIN_SOBT = [100, 102, 110]
IESS_PCT = 0.0945
FONDO_RESERVA_PCT = 0.0833

SBU_DEFECTO = {
    "2020": 400.0, "2021": 400.0, "2022": 425.0, "2023": 450.0,
    "2024": 460.0, "2025": 470.0, "2026": 482.0, "2027": 482.0,
}


@dataclass
class ConfigLiquidacion:
    region: str = "COSTA"  # COSTA | SIERRA
    iess_personal_pct: float = IESS_PCT
    sbu_por_anio: dict[str, float] = field(default_factory=lambda: dict(SBU_DEFECTO))

    def sbu(self, anio: int) -> float:
        d = self.sbu_por_anio
        s = str(anio)
        if s in d:
            return float(d[s])
        anios = sorted(int(a) for a in d)
        if not anios:
            return 482.0
        if anio < anios[0]:
            return float(d[str(anios[0])])
        if anio > anios[-1]:
            return float(d[str(anios[-1])])
        for i in range(len(anios) - 1):
            if anios[i] <= anio < anios[i + 1]:
                return float(d[str(anios[i])])
        return float(d[str(anios[-1])])


# ── Fechas / días comerciales ───────────────────────────────────────────────


def dias360(inicio: dt.date, fin: dt.date) -> int:
    """Equivalente a la función DIAS360 de Excel (12 meses × 30 días)."""
    d_ini, d_fin = min(inicio.day, 30), min(fin.day, 30)
    anios = fin.year - inicio.year
    meses = fin.month - inicio.month
    dias = d_fin - d_ini
    if dias < 0:
        meses -= 1
        dias += 30
    if meses < 0:
        anios -= 1
        meses += 12
    return anios * 360 + meses * 30 + dias


def _ultimo_dia(anio: int, mes: int) -> int:
    return calendar.monthrange(anio, mes)[1]


def periodos_vacaciones(fecha_ing: dt.date, fecha_sal: dt.date) -> list[tuple[dt.date, dt.date]]:
    """Últimos 2 periodos anuales según el mes de ingreso (01/mes_ing → fin mes anterior)."""
    mes_inicio = fecha_ing.month
    if fecha_sal.month > mes_inicio or (fecha_sal.month == mes_inicio and fecha_sal.day >= 1):
        anio_ultimo = fecha_sal.year
    else:
        anio_ultimo = fecha_sal.year - 1
    out = []
    for i in range(1, -1, -1):
        ap = anio_ultimo - i
        inicio = dt.date(ap, mes_inicio, 1)
        if mes_inicio == 1:
            fin = dt.date(ap, 12, 31)
        else:
            fin = dt.date(ap + 1, mes_inicio - 1, _ultimo_dia(ap + 1, mes_inicio - 1))
        if fin >= fecha_ing and inicio <= fecha_sal:
            out.append((inicio, fin))
    return out


def periodos_decima_tercera(fecha_ing: dt.date, fecha_sal: dt.date) -> list[tuple[dt.date, dt.date, bool]]:
    """01/12 año-1 → 30/11 año. `pagado` = la fecha de pago (24/12) ya pasó antes de salir."""
    out = []
    for i in range(1, -1, -1):
        af = fecha_sal.year - i
        inicio, fin = dt.date(af - 1, 12, 1), dt.date(af, 11, 30)
        if fin >= fecha_ing and inicio <= fecha_sal:
            out.append((inicio, fin, dt.date(af, 12, 24) < fecha_sal))
    return out


def periodos_decima_cuarta(
    fecha_ing: dt.date, fecha_sal: dt.date, region: str = "COSTA"
) -> list[tuple[dt.date, dt.date, bool]]:
    """COSTA: 01/03 → 28-29/02 (pago 15/03). SIERRA: 01/08 → 31/07 (pago 15/08)."""
    mes_inicio, mes_fin, dia_pago_mes = (3, 2, 3) if region == "COSTA" else (8, 7, 8)
    out = []
    for anio_base in range(fecha_ing.year - 1, fecha_sal.year + 2):
        inicio = dt.date(anio_base, mes_inicio, 1)
        fin = dt.date(anio_base + 1, mes_fin, _ultimo_dia(anio_base + 1, mes_fin))
        if fin >= fecha_ing and inicio <= fecha_sal:
            pagado = dt.date(fin.year, dia_pago_mes, 15) < fecha_sal
            out.append((inicio, fin, pagado))
    return out


def desahucio(fecha_ing: dt.date, fecha_sal: dt.date, ultimo_sueldo: float,
              tipo_contrato: str = "INDEFINIDO") -> float:
    """(sueldo / 4) × años completos, si trabajó > 360 días y contrato indefinido."""
    if tipo_contrato != "INDEFINIDO":
        return 0.0
    dias = (fecha_sal - fecha_ing).days
    if dias <= 360:
        return 0.0
    from dateutil.relativedelta import relativedelta

    diff = relativedelta(fecha_sal, fecha_ing)
    frac = diff.years + diff.months / 12.0 + diff.days / 365.25 + 0.00278
    return round((ultimo_sueldo / 4) * int(frac), 2)


def indemnizacion_despido(fecha_ing: dt.date, fecha_sal: dt.date, sueldo: float, motivo: str) -> float:
    m = (motivo or "").upper()
    if "DESPIDO" not in m and "INTEMPESTIVO" not in m:
        return 0.0
    anios = int((fecha_sal - fecha_ing).days / 365.25)
    return round(sueldo * (min(anios, 25) if anios >= 3 else 3), 2)


# ── Movimientos por mes ─────────────────────────────────────────────────────


def _rango_mes(anio: int, mes: int) -> tuple[str, str]:
    ini = f"{anio}-{mes:02d}-01"
    fin = f"{anio + 1}-01-01" if mes == 12 else f"{anio}-{mes + 1:02d}-01"
    return ini, fin


def movimientos_mes(empleado: str, anio: int, mes: int, fuente: str) -> tuple[list[dict], str]:
    """Devuelve (movs, origen). Busca primero el período abierto, luego el cerrado."""
    ini, fin = _rango_mes(anio, mes)
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()

        def q_sb(tabla: str) -> list[dict]:
            r = (
                sb.table(tabla)
                .select("clase,valor,dias,codigo")
                .eq("codemp", "10")
                .eq("empleado", str(empleado))
                .gte("fecha_ven", ini)
                .lt("fecha_ven", fin)
                .execute()
            )
            return r.data or []

        m = q_sb("rpingdesres")
        if m:
            return [_norm(x) for x in m], "RPINGDES"
        return [_norm(x) for x in q_sb("rphistor_temp")], "RPHISTOR"

    flt = get_settings().sqlserver_filter

    def q_sql(tabla: str) -> list[dict]:
        return sqlserver.filas(
            f"""SELECT [CLASE],[VALOR],[DIAS],[CODIGO] FROM [insevig].[dbo].[{tabla}]
                WHERE {flt} AND [EMPLEADO] = ? AND [FECHA_VEN] IS NOT NULL
                  AND CAST([FECHA_VEN] AS DATE) >= CAST(? AS DATE)
                  AND CAST([FECHA_VEN] AS DATE) <  CAST(? AS DATE)""",
            (str(empleado), ini, fin),
        )

    m = q_sql("RPINGDES")
    if m:
        return [_norm(x) for x in m], "RPINGDES"
    return [_norm(x) for x in q_sql("RPHISTOR")], "RPHISTOR"


def _norm(r: dict) -> dict:
    return {
        "clase": a_int(r.get("CLASE", r.get("clase"))),
        "valor": a_float(r.get("VALOR", r.get("valor"))),
        "dias": r.get("DIAS", r.get("dias")),
        "codigo": str(r.get("CODIGO", r.get("codigo")) or "").strip(),
    }


def _suma_base(empleado: str, inicio: dt.date, fin: dt.date, fuente: str) -> float:
    """Suma SUELDO+BONIF+MANIOBRAS+SOBRETIEMPOS mes a mes del periodo (base de vacaciones/décimos)."""
    total = 0.0
    y, mth = inicio.year, inicio.month
    while dt.date(y, mth, 1) <= fin:
        movs, _ = movimientos_mes(empleado, y, mth, fuente)
        for mv in movs:
            if mv["clase"] in CONCEPTOS_BASE:
                total += mv["valor"]
        mth, y = (1, y + 1) if mth == 12 else (mth + 1, y)
    return round(total, 2)


# ── Empleado ────────────────────────────────────────────────────────────────


def _empleado(cedula: str, fuente: str) -> dict | None:
    ced = normalizar_cedula(cedula)
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        for filtro in (("cedula", int(ced)), ("cedula", float(ced))):
            try:
                r = sb.table("rpemplea").select("*").eq("codemp", "10").eq(*filtro).limit(1).execute()
                if r.data:
                    return {k.upper(): v for k, v in r.data[0].items()}
            except Exception:  # noqa: BLE001, PERF203
                continue
        return None
    flt = get_settings().sqlserver_filter
    filas = sqlserver.filas(
        f"""SELECT [EMPLEADO],[APELLIDOS],[NOMBRES],[CEDULA],[SUELDO],[CARGO],[DEPTO],
                   [SECCION],[FECHA_ING],[FECHA_SAL],[ESTADO],[HOR25],[HOR50],[HOR100]
            FROM [insevig].[dbo].[RPEMPLEA] WHERE {flt} AND CAST([CEDULA] AS BIGINT) = ?""",
        (int(ced),),
    )
    return filas[0] if filas else None


def _f(v) -> dt.date | None:
    if not v:
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(str(v)[:19], fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class Liquidacion:
    empleado: str
    nombre: str
    cedula: str
    cargo: str
    depto: str
    seccion: str
    sueldo_base: float
    fecha_ingreso: str
    fecha_salida: str
    motivo_salida: str
    dias_trabajados: int
    campos: dict[str, float] = field(default_factory=dict)
    error: str = ""


def _parse_linea(linea: str) -> tuple[str, str, str, str] | None:
    """cédula, dd/mm/aaaa (salida), motivo[, dd/mm/aaaa (ingreso, opcional)]."""
    partes = [p.strip() for p in linea.split(",")]
    if len(partes) < 2:
        return None
    ced, fecha = partes[0], partes[1]
    motivo = partes[2] if len(partes) > 2 else ""
    fecha_ing = partes[3] if len(partes) > 3 else ""
    return ced, fecha, motivo, fecha_ing


def procesar_empleado(
    cedula: str, fecha_salida: str, motivo: str, fuente: str, cfg: ConfigLiquidacion,
    fecha_ingreso: str = "",
) -> Liquidacion:
    emp = _empleado(cedula, fuente)
    ced = normalizar_cedula(cedula)
    if emp is None:
        return Liquidacion(
            "", "", ced, "", "", "", 0.0, "", fecha_salida, motivo, 0, error="empleado no encontrado"
        )
    cod = str(emp["EMPLEADO"]).strip()
    fsal = _f(fecha_salida) or _f(emp.get("FECHA_SAL")) or dt.date.today()
    fing = _f(fecha_ingreso) or _f(emp.get("FECHA_ING")) or fsal
    if fing > fsal:
        return Liquidacion(
            cod, "", ced, "", "", "", 0.0, "", str(fsal), motivo, 0,
            error="fecha de ingreso posterior a la de salida — añade la fecha de ingreso "
                  "correcta como 4º dato de la línea (cédula, salida, motivo, ingreso)",
        )
    sueldo = a_float(emp.get("SUELDO"))
    nombre = f"{(emp.get('APELLIDOS') or '').strip()} {(emp.get('NOMBRES') or '').strip()}".strip()
    dias_trab = (fsal - fing).days

    # 1. Movimientos del mes de salida (+ fallback mes anterior)
    movs, _origen = movimientos_mes(cod, fsal.year, fsal.month, fuente)
    if not movs:
        m_ant = 12 if fsal.month == 1 else fsal.month - 1
        y_ant = fsal.year - 1 if fsal.month == 1 else fsal.year
        movs, _origen = movimientos_mes(cod, y_ant, m_ant, fuente)

    val: dict[str, float] = {c: 0.0 for c in set(MAPEO_CONCEPTOS.values())}
    val["ANTICIPOS_OTROS_L"] = val["ANTICIPO_L_DESAHUCIO"] = val["INDEM_DESPIDO"] = 0.0
    dias_mov = 0.0
    for mv in movs:
        c = mv["clase"]
        if c in CODIGOS_IGNORAR:
            continue
        concepto = MAPEO_CONCEPTOS.get(c)
        if concepto is None:
            if mv["codigo"] == "EGR":
                val["ANTICIPOS_SURTIDOS"] += round(mv["valor"], 2)
            continue
        val[concepto] += round(mv["valor"], 2)
        if concepto == "SUELDO" and mv["dias"] is not None:
            dias_mov = a_float(mv["dias"])

    # 2. Descuentos multi-mes (hasta 36 meses o 3 seguidos sin datos)
    mp, yp, sin_datos = fsal.month, fsal.year, 0
    for _ in range(36):
        mp, yp = (1, yp + 1) if mp == 12 else (mp + 1, yp)
        futuros, _ = movimientos_mes(cod, yp, mp, fuente)
        if not futuros:
            sin_datos += 1
            if sin_datos >= 3:
                break
            continue
        sin_datos = 0
        for mv in futuros:
            concepto = MAPEO_CONCEPTOS.get(mv["clase"])
            if concepto in DESCUENTOS_MULTI_MES:
                val[concepto] += round(mv["valor"], 2)

    # 3. Sobretiempos desde RPEMPLEA si no vinieron en movimientos
    h25, h50, h100 = a_int(emp.get("HOR25")), a_int(emp.get("HOR50")), a_int(emp.get("HOR100"))
    if sueldo > 0 and val["SOBRETIEMPO_25"] == 0:
        if h25:
            val["SOBRETIEMPO_25"] = round((sueldo / 240) * 0.25 * h25, 2)
        if h50:
            val["SOBRETIEMPO_50"] = round((sueldo / 240) * 1.5 * h50, 2)
        if h100:
            val["SOBRETIEMPO_100"] = round((sueldo / 240) * 2.0 * h100, 2)

    # 4. Vacaciones (últimos 2 periodos; calc = último / 24)
    pv = periodos_vacaciones(fing, fsal)
    sumatorias = [_suma_base(cod, i, f, fuente) for i, f in pv]
    vac_ant = sumatorias[0] if len(sumatorias) >= 2 else 0.0
    vac_ult = sumatorias[-1] if sumatorias else 0.0
    vac_calc = round(vac_ult / 24, 2) if vac_ult > 0 else 0.0

    # 5. Décima tercera (total periodo / 12)
    d13_ant = d13_act = 0.0
    p13 = periodos_decima_tercera(fing, fsal)
    for idx, (i, f, _pag) in enumerate(p13):
        dec = round(_suma_base(cod, i, f, fuente) / 12, 2)
        if idx == 0 and len(p13) > 1:
            d13_ant = dec
        else:
            d13_act = dec

    # 6. Décima cuarta (DIAS360 × SBU / 360; pagadas → ANTERIOR, pendiente → ACTUAL)
    d14_ant = d14_act = 0.0
    for i, f, pagado in periodos_decima_cuarta(fing, fsal, cfg.region):
        sbu = cfg.sbu(f.year)
        base_ini = fing if fing > i else i
        d360 = dias360(base_ini, fsal)
        dias_base = d360 + 1
        ajuste_feb = 0
        if fsal.month == 2 and (fsal + dt.timedelta(days=1)).month == 3:
            ajuste_feb = 30 - fsal.day
        dec = round((dias_base + ajuste_feb) * (sbu / 360), 2)
        if pagado:
            d14_ant += dec
        else:
            d14_act += dec

    # 7. Desahucio
    des = desahucio(fing, fsal, sueldo)

    # 8. Fondo de reserva = 8.33% de la base del mes de salida
    fondo_reserva = round((val["SUELDO"] + val["SOBRETIEMPO_25"] + val["SOBRETIEMPO_50"]
                           + val["SOBRETIEMPO_100"] + val["BONIFICACION"] + val["MANIOBRAS"])
                          * FONDO_RESERVA_PCT, 2)
    if val["FONDO_RESERVA"] > 0:
        fondo_reserva = val["FONDO_RESERVA"]

    # 9. IESS
    base_iess = val["SUELDO"] + val["SOBRETIEMPO_25"] + val["SOBRETIEMPO_50"] + val["SOBRETIEMPO_100"]
    iess = round(base_iess * cfg.iess_personal_pct, 2)

    # 10. Indemnización por despido
    indem = indemnizacion_despido(fing, fsal, sueldo, motivo)

    # 11. Split de anticipos si días < 90
    total_liq = vac_calc + d13_act + d14_act + des
    ant_otros_l = ant_l_des = 0.0
    if dias_trab < 90:
        if total_liq > 0:
            ant_otros_l = float(int(total_liq / 3.75))
        if des > 0:
            ant_l_des = float(int(des / 3.75))

    # 12. Totales
    total_ingresos = round(
        val["SUELDO"] + val["BONIFICACION"] + val["MANIOBRAS"] + val["MOVILIZACION"]
        + val["REEMBOLSOS"] + val["SOBRETIEMPO_25"] + val["SOBRETIEMPO_50"] + val["SOBRETIEMPO_100"]
        + fondo_reserva + vac_calc + d13_act + d14_act + des + indem, 2,
    )
    total_descuentos = round(
        val["ANTICIPOS_SURTIDOS"] + val["PRESTAMOS_COMPANIA"] + val["ANTICIPOS_OTROS"]
        + val["ANTICIPO_SUELDO"] + val["MULTAS"] + ant_otros_l + ant_l_des
        + val["PRESTAMOS_QUIROGRAFARIOS"] + val["APORT_IESS_CONYUGE"] + val["PENSION_ALIMENTICIA"]
        + val["PRESTAMO_HIPOTECARIO"] + iess + val["IMPUESTO_RENTA"], 2,
    )

    campos = {
        "SUELDO": val["SUELDO"], "DIAS": dias_mov,
        "HORAS_25": h25, "HORAS_50": h50, "HORAS_100": h100,
        "VAL_SOBT_25": val["SOBRETIEMPO_25"], "VAL_SOBT_50": val["SOBRETIEMPO_50"],
        "VAL_SOBT_100": val["SOBRETIEMPO_100"], "MANIOBRAS": val["MANIOBRAS"],
        "BONIFICACION": val["BONIFICACION"], "MOVILIZACION": val["MOVILIZACION"],
        "REEMBOLSOS": val["REEMBOLSOS"], "FONDO_RESERVA": fondo_reserva,
        "VACACIONES_ANTERIOR": vac_ant, "VACACIONES_ULTIMO": vac_ult, "VACACIONES_CALCULADAS": vac_calc,
        "DECIMA_TERCERA_ANTERIOR": d13_ant, "DECIMA_TERCERA_ACTUAL": d13_act,
        "DECIMA_CUARTA_ANTERIOR": d14_ant, "DECIMA_CUARTA_ACTUAL": d14_act,
        "DESAHUCIO": des, "INDEM_DESPIDO": indem,
        "ANTICIPOS_SURTIDOS": val["ANTICIPOS_SURTIDOS"], "PRESTAMOS_COMPANIA": val["PRESTAMOS_COMPANIA"],
        "ANTICIPOS_OTROS": val["ANTICIPOS_OTROS"], "ANTICIPO_SUELDO": val["ANTICIPO_SUELDO"],
        "MULTAS": val["MULTAS"], "ANTICIPOS_OTROS_L": ant_otros_l, "ANTICIPO_L_DESAHUCIO": ant_l_des,
        "PRESTAMOS_QUIROGRAFARIOS": val["PRESTAMOS_QUIROGRAFARIOS"],
        "APORT_IESS_CONYUGE": val["APORT_IESS_CONYUGE"], "PENSION_ALIMENTICIA": val["PENSION_ALIMENTICIA"],
        "PRESTAMO_HIPOTECARIO": val["PRESTAMO_HIPOTECARIO"], "APORT_IESS": iess,
        "IMPUESTO_RENTA": val["IMPUESTO_RENTA"],
        "TOTAL_INGRESOS": total_ingresos, "TOTAL_DESCUENTOS": total_descuentos,
        "TOTAL_A_RECIBIR": round(total_ingresos - total_descuentos, 2),
    }
    return Liquidacion(
        empleado=cod, nombre=nombre, cedula=ced,
        cargo=str(emp.get("CARGO") or ""), depto=str(emp.get("DEPTO") or ""),
        seccion=str(emp.get("SECCION") or ""), sueldo_base=sueldo,
        fecha_ingreso=str(fing), fecha_salida=str(fsal), motivo_salida=motivo,
        dias_trabajados=dias_trab, campos=campos,
    )


def procesar_lote(texto: str, fuente: str, cfg: ConfigLiquidacion) -> list[Liquidacion]:
    out = []
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        parsed = _parse_linea(linea)
        if parsed is None:
            out.append(Liquidacion("", "", "", "", "", "", 0.0, "", "", "", 0,
                                   error=f"línea inválida: {linea!r}"))
            continue
        ced, fecha, motivo, fecha_ing = parsed
        out.append(procesar_empleado(ced, fecha, motivo, fuente, cfg, fecha_ingreso=fecha_ing))
    return out
