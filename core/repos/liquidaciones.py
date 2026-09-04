"""Generación de liquidaciones (finiquitos) — módulo 9.

Cálculos legales de Ecuador: vacaciones, décima tercera, décima cuarta (por
región), desahucio, indemnización por despido intempestivo, IESS, fondo de
reserva, split de anticipos.

Entrada: (cédula, fecha_salida, motivo_salida). Salida: dict por empleado + Excel.

Origen: esta versión reemplaza la extracción inicial (basada en
`Liquidaciones_generador_CON_VACACIONES.pyw`, la versión vieja/deprecada) por
la lógica de `LIQUIDACIONES_SISTEMA_INSEVIG/nucleo_modular/` — la extracción
fiel y ya probada (18 tests) del `.pyw` que la empresa usa hoy en producción
(`Generador_Liquidaciones_INSEVIG.pyw`), con meses de correcciones reales ya
validadas. Ver `docs/modulos/liquidaciones.md`, sección "Correcciones
incorporadas al reemplazar la extracción inicial", para el detalle de qué
cambió respecto de la versión anterior de este archivo y por qué (ningún
cambio es una "mejora" inventada aquí -- todos ya estaban confirmados contra
casos reales en el `.pyw` de producción).
"""

from __future__ import annotations

import calendar
import contextlib
import datetime as dt
from dataclasses import dataclass, field

from core.concepts import CLASE_A_CONCEPTO, CLASES_IGNORADAS
from core.config import get_settings
from core.db import sqlserver, supabase_client
from core.db.health import FUENTE_SUPABASE
from core.utils import a_float, a_int, normalizar_cedula

# ── Constantes ────────────────────────────────────────────────────────────
# El mapeo CLASE→concepto y los códigos ignorados son los de `core.concepts`
# (fuente única, compartida con roles/reportes) -- ya NO se duplican aquí.

DESCUENTOS_MULTI_MES = {
    "PRESTAMOS_COMPANIA", "ANTICIPOS_OTROS", "ANTICIPO_SUELDO", "MULTAS",
    "PRESTAMOS_QUIROGRAFARIOS", "APORT_IESS_CONYUGE", "PENSION_ALIMENTICIA",
    "PRESTAMO_HIPOTECARIO", "ANTICIPOS_SURTIDOS",
}
CONCEPTOS_BASE = [100, 102, 110, 113, 114, 115]  # SUELDO+BONIF+MANIOBRAS+SOBRETIEMPOS
IESS_PCT = 0.0945
FONDO_RESERVA_PCT = 0.0833
# Umbral (días) y divisor del split de anticipos (ANTICIPOS_OTROS_L / ANTICIPO_L_DESAHUCIO).
ANTICIPO_DIAS_UMBRAL = 90
ANTICIPO_DIVISOR = 3.75
# Días base de vacaciones (Art. 69 Código del Trabajo) usados para prorratear
# un goce PARCIAL ya registrado en vac_registros (ver `_prorratear_por_goce`).
VACACIONES_DIAS_BASE = 15

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


def _dia_ajustado(anio: int, mes: int, dia: int) -> int:
    """Ajusta el día si el mes de ese año no lo tiene (ej. 29 de febrero en
    año no bisiesto)."""
    return min(dia, _ultimo_dia(anio, mes))


def periodos_vacaciones(fecha_ing: dt.date, fecha_sal: dt.date) -> list[tuple[dt.date, dt.date]]:
    """TODOS los periodos de vacaciones vencidos/vigentes desde el ingreso
    hasta la salida -- las vacaciones NO caducan en Ecuador, se acumulan y
    deben liquidarse TODAS (no solo los últimos 2; ver `total_vacaciones_a_pagar`
    más abajo, que sí suma todos los períodos con saldo).

    CORREGIDO (respecto de la extracción inicial de este archivo, que ancla
    en el DÍA 1 del mes de ingreso): el periodo ahora ancla en el DÍA EXACTO
    de ingreso (aniversario real). Alguien que ingresó el 15/03/2020 tiene su
    periodo real 15/03/2024 → 14/03/2025, no 01/03/2024 → 28/02/2025 -- una
    diferencia de ~2 semanas que corre qué meses de sueldo entran en cada
    periodo, y que puede no coincidir con la etiqueta real ya registrada en
    `vac_registros` (ver `vacaciones_pagadas`/`vacaciones_gozadas`).

    Retorna [(inicio1, fin1), ...] del más antiguo al más reciente. Cada
    tupla ya viene recortada a [fecha_ing, fecha_sal] (reingreso: si esta
    persona reingresó a mitad de un periodo anual, el inicio real a
    considerar es su fecha de ingreso ACTUAL, no el aniversario calendario).
    """
    mes_inicio, dia_inicio = fecha_ing.month, fecha_ing.day

    dia_aniv_este_anio = _dia_ajustado(fecha_sal.year, mes_inicio, dia_inicio)
    aniv_este_anio = dt.date(fecha_sal.year, mes_inicio, dia_aniv_este_anio)
    anio_ultimo = fecha_sal.year if fecha_sal >= aniv_este_anio else fecha_sal.year - 1

    out: list[tuple[dt.date, dt.date]] = []
    for i in range(59, -1, -1):  # hasta 60 periodos atrás (60 años); el filtro
        anio_periodo = anio_ultimo - i  # de abajo descarta los que no aplican
        dia_ini = _dia_ajustado(anio_periodo, mes_inicio, dia_inicio)
        inicio = dt.date(anio_periodo, mes_inicio, dia_ini)
        dia_fin = _dia_ajustado(anio_periodo + 1, mes_inicio, dia_inicio)
        fin = dt.date(anio_periodo + 1, mes_inicio, dia_fin) - dt.timedelta(days=1)
        if fin >= fecha_ing and inicio <= fecha_sal:
            out.append((max(inicio, fecha_ing), min(fin, fecha_sal)))
    return out


def periodos_decima_tercera(fecha_ing: dt.date, fecha_sal: dt.date) -> list[tuple[dt.date, dt.date, bool]]:
    """01/12 año-1 → 30/11 año (últimos 2 periodos). `pagado` = la fecha de
    pago (24/12) ya pasó antes de salir.

    CORREGIDO: cada tupla se recorta a [fecha_ing, fecha_sal] -- antes, un
    reingreso a mitad del periodo calendario (01/12 → 30/11) sumaba
    movimientos desde el 01/12 aunque esa persona hubiera reingresado
    después, inflando la Décima Tercera con sueldo de un ingreso anterior ya
    liquidado por separado.
    """
    out = []
    for i in range(1, -1, -1):
        af = fecha_sal.year - i
        inicio, fin = dt.date(af - 1, 12, 1), dt.date(af, 11, 30)
        if fin >= fecha_ing and inicio <= fecha_sal:
            pagado = dt.date(af, 12, 24) < fecha_sal
            out.append((max(inicio, fecha_ing), min(fin, fecha_sal), pagado))
    return out


def periodos_decima_cuarta(
    fecha_ing: dt.date, fecha_sal: dt.date, region: str = "COSTA"
) -> list[tuple[dt.date, dt.date, bool]]:
    """Los últimos 2 periodos (anterior + actual), igual que décima tercera.
    COSTA: 01/03 → 28/29-02. SIERRA: 01/08 → 31/07.

    CORREGIDO (bug real de la extracción inicial de este archivo, que
    recorría TODOS los años desde el ingreso -- para alguien con varios años
    de antigüedad esto inflaba el valor absurdamente sumando periodos ya
    pagados año a año en su momento): ahora solo se consideran los últimos 2
    periodos, anclados en la fecha de salida.

    CORREGIDO también el criterio de "pagado": antes comparaba contra la
    fecha LEGAL de pago (15/03 o 15/08); un periodo se considera "pagado" si
    simplemente ya terminó antes de la fecha de salida -- confirmado contra
    actas de finiquito reales, la empresa liquida el periodo anterior en
    nómina regular ANTES de esa fecha legal, no en ella.
    """
    mes_inicio, mes_fin = (3, 2) if region == "COSTA" else (8, 7)

    anio_base_actual = fecha_sal.year if fecha_sal.month >= mes_inicio else fecha_sal.year - 1

    out = []
    for i in range(1, -1, -1):  # i=1 (anterior), i=0 (actual)
        anio_base = anio_base_actual - i
        inicio = dt.date(anio_base, mes_inicio, 1)
        fin = dt.date(anio_base + 1, mes_fin, _ultimo_dia(anio_base + 1, mes_fin))
        if fin >= fecha_ing and inicio <= fecha_sal:
            pagado = fin < fecha_sal
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


# ── Vacaciones ya pagadas/gozadas (Supabase `vac_registros`) ────────────────
# Antes de contar un periodo de vacaciones como "pendiente", se verifica si ya
# existe un registro en `vac_registros` (proyecto VACACIONES_SISTEMA_INSEVIG,
# misma base Supabase) que indique que ya se pagó o que el empleado ya salió
# de descanso esos días -- si no se revisa esto, la liquidación puede volver a
# pagar en efectivo un periodo ya cubierto (doble pago real, caso confirmado
# en producción). Si Supabase no responde, se degrada de forma segura: se
# devuelve `None` (no un dict vacío) para que el llamador NO descarte ningún
# periodo por falta de verificación, no porque conste que no está pagado.


def _etiqueta_periodo(inicio: dt.date) -> str:
    """Etiqueta 'YYYY-YYYY' de un periodo a partir de su fecha de INICIO
    real -- nunca del año de "fin" (que puede venir recortado a la fecha de
    salida, corrompiendo el año en un periodo que cruza fin de año)."""
    return f"{inicio.year}-{inicio.year + 1}"


def vacaciones_pagadas(cedula: str) -> dict[str, bool] | None:
    """{periodo: True/False} -- True si ese periodo ya se pagó de verdad
    (estado_doc='completado', o estado_doc nulo con valor_vacaciones>0,
    caso de importaciones históricas). `None` si no se pudo verificar."""
    ced = normalizar_cedula(cedula)
    try:
        sb = supabase_client.get_client()
        r = (
            sb.table("vac_registros")
            .select("periodo,estado_doc,valor_vacaciones")
            .eq("cedula", ced)
            .eq("tipo", "pagada")
            .execute()
        )
    except Exception:  # noqa: BLE001 - degradar sin bloquear la liquidación
        return None
    registros: dict[str, bool] = {}
    for fila in r.data or []:
        periodo = fila.get("periodo")
        if not periodo:
            continue
        estado = fila.get("estado_doc")
        valor = a_float(fila.get("valor_vacaciones"))
        ya_pagado = (estado == "completado") or (not estado and valor > 0)
        registros[periodo] = registros.get(periodo, False) or ya_pagado
    return registros


def vacaciones_gozadas(cedula: str) -> dict[str, float] | None:
    """{periodo: dias_tomados_total} (tipo='gozada', estado_doc='completado').
    `None` si no se pudo verificar."""
    ced = normalizar_cedula(cedula)
    try:
        sb = supabase_client.get_client()
        r = (
            sb.table("vac_registros")
            .select("periodo,dias_tomados")
            .eq("cedula", ced)
            .eq("tipo", "gozada")
            .eq("estado_doc", "completado")
            .execute()
        )
    except Exception:  # noqa: BLE001
        return None
    dias_por_periodo: dict[str, float] = {}
    for fila in r.data or []:
        periodo = fila.get("periodo")
        if periodo:
            dias_por_periodo[periodo] = dias_por_periodo.get(periodo, 0) + a_float(fila.get("dias_tomados"))
    return dias_por_periodo


@dataclass
class DetalleVacacionesPeriodo:
    periodo: str
    estado: str  # PAGADO | GOZADO_COMPLETO | GOZADO_PARCIAL | PENDIENTE | SIN_SALDO | SIN_VERIFICAR
    dias_gozados: float
    monto_bruto: float
    incluido: bool


def total_vacaciones_a_pagar(
    cedula: str, sumatorias_brutas: list[float], periodos: list[tuple[dt.date, dt.date]]
) -> tuple[float, list[str], list[DetalleVacacionesPeriodo]]:
    """Del total bruto de CADA periodo (`sumatorias_brutas`, paralelo a
    `periodos`), descarta los que `vac_registros` marca como ya pagados o ya
    gozados (≥15 días: derecho base, Art. 69 CT), prorratea un goce PARCIAL
    (< 15 días), y suma TODOS los periodos restantes con saldo -- las
    vacaciones no caducan, así que un periodo más antiguo que el "anterior"
    también debe pagarse si nadie lo cubrió.

    Si no se puede verificar contra `vac_registros` (Supabase no responde),
    por seguridad SOLO se calcula automáticamente el periodo más reciente
    (igual que el comportamiento anterior a esta verificación); cualquier
    periodo más antiguo con saldo se dej fuera del total y se alerta para
    revisión manual -- sumarlo a ciegas podría ser un doble pago real.

    Retorna (suma_total_pendiente, alertas, detalle_por_periodo). El monto a
    pagar es `suma_total_pendiente / 24` (lo calcula el llamador).
    """
    pagadas = vacaciones_pagadas(cedula)
    gozadas = vacaciones_gozadas(cedula)
    alertas: list[str] = []
    detalle: list[DetalleVacacionesPeriodo] = []
    sumatorias = list(sumatorias_brutas)

    if pagadas is None or gozadas is None:
        for idx, (inicio, _fin) in enumerate(periodos):
            label = _etiqueta_periodo(inicio)
            es_ultimo = idx == len(periodos) - 1
            bruto = sumatorias_brutas[idx]
            if not es_ultimo and bruto > 0:
                alertas.append(
                    f"Periodo {label} NO se incluyó automáticamente (no se pudo verificar "
                    f"contra vac_registros si ya fue pagado/gozado) -- monto potencial "
                    f"${bruto / 24:.2f}. Revisar manualmente antes de agregarlo."
                )
                sumatorias[idx] = 0.0
                detalle.append(DetalleVacacionesPeriodo(label, "SIN_VERIFICAR", 0.0, bruto, False))
            else:
                detalle.append(DetalleVacacionesPeriodo(
                    label, "PENDIENTE" if bruto > 0 else "SIN_SALDO", 0.0, bruto, bruto > 0))
        return round(sum(sumatorias), 2), alertas, detalle

    for idx, (inicio, _fin) in enumerate(periodos):
        label = _etiqueta_periodo(inicio)
        bruto = sumatorias_brutas[idx]
        ya_pagado = pagadas.get(label, False)
        dias_gozados = gozadas.get(label, 0.0)

        if ya_pagado and bruto > 0:
            sumatorias[idx] = 0.0
            detalle.append(DetalleVacacionesPeriodo(label, "PAGADO", dias_gozados, bruto, False))
        elif dias_gozados >= VACACIONES_DIAS_BASE and bruto > 0:
            sumatorias[idx] = 0.0
            detalle.append(DetalleVacacionesPeriodo(label, "GOZADO_COMPLETO", dias_gozados, bruto, False))
        elif dias_gozados > 0 and bruto > 0:
            # Goce PARCIAL: se paga solo (15 - dias_gozados) de los 15 días base.
            dias_pendientes = max(0, VACACIONES_DIAS_BASE - dias_gozados)
            factor = dias_pendientes / VACACIONES_DIAS_BASE
            monto_reducido = round(bruto * factor, 2)
            sumatorias[idx] = monto_reducido
            alertas.append(
                f"Periodo {label}: {dias_gozados:g} día(s) ya gozados (parcial) -- se "
                f"prorratea a los {dias_pendientes:g} día(s) pendientes: ${monto_reducido:.2f} "
                f"de ${bruto:.2f}."
            )
            detalle.append(DetalleVacacionesPeriodo(label, "GOZADO_PARCIAL", dias_gozados, monto_reducido, True))
        else:
            detalle.append(DetalleVacacionesPeriodo(
                label, "PENDIENTE" if bruto > 0 else "SIN_SALDO", dias_gozados, bruto, bruto > 0))

    return round(sum(sumatorias), 2), alertas, detalle


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
    alertas: list[str] = field(default_factory=list)
    error: str = ""
    apellidos: str = ""
    nombres: str = ""
    detalle_vacaciones: list[DetalleVacacionesPeriodo] = field(default_factory=list)


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
    *,
    incluir_dec13_anterior: bool = True,
    incluir_dec14_anterior: bool = True,
) -> Liquidacion:
    """Procesa un empleado y arma su liquidación.

    `incluir_dec13_anterior`/`incluir_dec14_anterior` (default `True`, mismo
    comportamiento que antes de exponer el parámetro): si el décimo tercero
    o cuarto del periodo ANTERIOR ya se pagó por otra vía (nómina regular) y
    no debe volver a sumarse aquí, se pasa `False` -- entonces ese valor
    queda en `campos["DECIMA_TERCERA_ANTERIOR"]` como referencia informativa
    (se sigue calculando y mostrando la cifra) pero NO se suma a los totales.
    """
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
    apellidos_emp = (emp.get("APELLIDOS") or "").strip()
    nombres_emp = (emp.get("NOMBRES") or "").strip()
    nombre = f"{apellidos_emp} {nombres_emp}".strip()
    dias_trab = (fsal - fing).days

    # 1. Movimientos del mes de salida (+ fallback mes anterior)
    movs, _origen = movimientos_mes(cod, fsal.year, fsal.month, fuente)
    if not movs:
        m_ant = 12 if fsal.month == 1 else fsal.month - 1
        y_ant = fsal.year - 1 if fsal.month == 1 else fsal.year
        movs, _origen = movimientos_mes(cod, y_ant, m_ant, fuente)

    val: dict[str, float] = dict.fromkeys(set(CLASE_A_CONCEPTO.values()), 0.0)
    val["ANTICIPOS_OTROS_L"] = val["ANTICIPO_L_DESAHUCIO"] = val["INDEM_DESPIDO"] = 0.0
    dias_mov = 0.0
    for mv in movs:
        c = mv["clase"]
        if c in CLASES_IGNORADAS:
            continue
        concepto = CLASE_A_CONCEPTO.get(c)
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
            concepto = CLASE_A_CONCEPTO.get(mv["clase"])
            if concepto in DESCUENTOS_MULTI_MES:
                val[concepto] += round(mv["valor"], 2)

    # 3. Horas de sobretiempo: si YA vino un valor $ real en los movimientos,
    # las horas se derivan de ESE $ (redondeando) y el $ final se RECALCULA
    # desde esas horas enteras -- no se deja el $ real con su propio
    # redondeo de nómina, que puede no cuadrar con la fórmula del MRL
    # (corregido; antes las "horas" mostradas venían siempre de RPEMPLEA,
    # sin relación con el $ real ya sumado -- podían no coincidir entre sí).
    # Si NO vino un $ real, se usa el cupo asignado en RPEMPLEA (HOR25/50/100)
    # como estimación -- mismo comportamiento que antes.
    h25 = h50 = h100 = 0
    if sueldo > 0:
        valor_hora = sueldo / 240
        if val["SOBRETIEMPO_25"] > 0:
            h25 = int(round(val["SOBRETIEMPO_25"] / (valor_hora * 0.25)))
            val["SOBRETIEMPO_25"] = round(valor_hora * 0.25 * h25, 2)
        elif a_int(emp.get("HOR25")):
            h25 = a_int(emp.get("HOR25"))
            val["SOBRETIEMPO_25"] = round(valor_hora * 0.25 * h25, 2)
        if val["SOBRETIEMPO_50"] > 0:
            h50 = int(round(val["SOBRETIEMPO_50"] / (valor_hora * 1.5)))
            val["SOBRETIEMPO_50"] = round(valor_hora * 1.5 * h50, 2)
        elif a_int(emp.get("HOR50")):
            h50 = a_int(emp.get("HOR50"))
            val["SOBRETIEMPO_50"] = round(valor_hora * 1.5 * h50, 2)
        if val["SOBRETIEMPO_100"] > 0:
            h100 = int(round(val["SOBRETIEMPO_100"] / (valor_hora * 2.0)))
            val["SOBRETIEMPO_100"] = round(valor_hora * 2.0 * h100, 2)
        elif a_int(emp.get("HOR100")):
            h100 = a_int(emp.get("HOR100"))
            val["SOBRETIEMPO_100"] = round(valor_hora * 2.0 * h100, 2)

    # 4. Vacaciones: TODOS los periodos pendientes (no caducan), descartando
    # los ya pagados/gozados según `vac_registros` (ver total_vacaciones_a_pagar).
    pv = periodos_vacaciones(fing, fsal)
    sumatorias_brutas = [_suma_base(cod, i, f, fuente) for i, f in pv]
    vac_ant = sumatorias_brutas[-2] if len(sumatorias_brutas) >= 2 else 0.0
    vac_ult = sumatorias_brutas[-1] if sumatorias_brutas else 0.0
    suma_pendiente, alertas_vac, detalle_vac = total_vacaciones_a_pagar(ced, sumatorias_brutas, pv)
    vac_calc = round(suma_pendiente / 24, 2) if suma_pendiente > 0 else 0.0

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
        fecha_inicio_efectiva = max(fing, i)
        fecha_fin_efectiva = min(fsal, f)
        dias_periodo = dias360(fecha_inicio_efectiva, fecha_fin_efectiva) + 1
        dec = round((sbu / 360) * dias_periodo, 2)
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

    # 11. Split de anticipos si días < umbral (base: solo lo que SÍ se paga:
    # vacaciones + décimos ACTUALES + desahucio -- el anterior, si se incluye,
    # no entra en esta base, igual que en el .pyw de producción).
    total_liq_base_split = vac_calc + d13_act + d14_act + des
    ant_otros_l = ant_l_des = 0.0
    if dias_trab < ANTICIPO_DIAS_UMBRAL:
        if total_liq_base_split > 0:
            ant_otros_l = float(int(total_liq_base_split / ANTICIPO_DIVISOR))
        if des > 0:
            ant_l_des = float(int(des / ANTICIPO_DIVISOR))

    # 12. Totales. CORREGIDO: el décimo ANTERIOR (13ro y 14to) se incluye por
    # defecto en el total -- la extracción inicial de este archivo lo omitía
    # siempre (subpagaba la liquidación en cualquier caso con décimo anterior
    # pendiente). Se puede excluir explícitamente con
    # incluir_dec13_anterior/incluir_dec14_anterior=False (ver docstring).
    dec13_ant_incluido = d13_ant if incluir_dec13_anterior else 0.0
    dec14_ant_incluido = d14_ant if incluir_dec14_anterior else 0.0
    total_ingresos = round(
        val["SUELDO"] + val["BONIFICACION"] + val["MANIOBRAS"] + val["MOVILIZACION"]
        + val["REEMBOLSOS"] + val["SOBRETIEMPO_25"] + val["SOBRETIEMPO_50"] + val["SOBRETIEMPO_100"]
        + fondo_reserva + vac_calc + dec13_ant_incluido + d13_act
        + dec14_ant_incluido + d14_act + des + indem, 2,
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
        dias_trabajados=dias_trab, campos=campos, alertas=alertas_vac,
        apellidos=apellidos_emp, nombres=nombres_emp, detalle_vacaciones=detalle_vac,
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


# ── Persistencia en Supabase (Editor / Gestión de liquidaciones) ────────────
# Porta `_mapear_fila_a_liquidacion`/`_construir_conceptos_liquidacion`/
# `guardar_liquidacion`/`eliminar_liquidacion_con_historial` de
# `Generador_Liquidaciones_INSEVIG.pyw` vía `LIQUIDACIONES_SISTEMA_INSEVIG/
# nucleo_modular/{mapeo_liquidacion,acceso_supabase}.py`, adaptado para leer
# directamente de `Liquidacion` (nuestro dataclass) en vez del dict `fila`
# del legado. Tablas: `liquidaciones`, `liquidaciones_detalle`,
# `liquidaciones_periodos_calculo`, `liquidaciones_historial_estados`,
# `liquidaciones_eliminadas_historial`.

TABLA_LIQ = "liquidaciones"
TABLA_LIQ_DETALLE = "liquidaciones_detalle"
TABLA_LIQ_HISTORIAL = "liquidaciones_historial_estados"
TABLA_LIQ_ELIMINADAS = "liquidaciones_eliminadas_historial"

ESTADOS_LIQUIDACION = ("borrador", "generada", "pagada", "anulada")


def clasificar_tipo_liquidacion(motivo: str | None) -> str:
    """Deriva 'tipo_liquidacion' (para filtrar en el listado) del texto libre
    de MOTIVO_SALIDA. Clasificación por palabras clave, no exhaustiva."""
    m = (motivo or "").upper()
    if "DESPID" in m:
        return "despido"
    if "RENUNCIA" in m:
        return "renuncia"
    if "VISTO BUEN" in m:
        return "visto_bueno"
    if any(p in m for p in ("CONTRATO", "PRUEBA", "TERMINO", "TÉRMINO", "TERMINACION", "TERMINACIÓN")):
        return "termino_contrato"
    if "MUERTE" in m or "FALLEC" in m:
        return "muerte"
    if "JUBILAC" in m:
        return "jubilacion"
    return "otro"


def _mapear_registro(liq: Liquidacion, estado: str, cfg: ConfigLiquidacion, *, usuario: str) -> dict:
    """`Liquidacion` -> columnas de la tabla `liquidaciones`."""
    c = liq.campos
    anios_servicio = None
    try:
        d_ing = dt.date.fromisoformat(liq.fecha_ingreso)
        d_sal = dt.date.fromisoformat(liq.fecha_salida)
        anios_servicio = round((d_sal - d_ing).days / 365.25, 2)
    except ValueError:
        pass

    def g(k: str) -> float:
        return float(c.get(k) or 0)

    decimo_tercero = round(g("DECIMA_TERCERA_ANTERIOR") + g("DECIMA_TERCERA_ACTUAL"), 2)
    decimo_cuarto = round(g("DECIMA_CUARTA_ANTERIOR") + g("DECIMA_CUARTA_ACTUAL"), 2)
    horas_extras = round(g("VAL_SOBT_25") + g("VAL_SOBT_50") + g("VAL_SOBT_100"), 2)

    def _horas_col(cant_key: str, valor_key: str) -> tuple[float, float]:
        cantidad = c.get(cant_key) or 0
        valor_total = g(valor_key)
        return cantidad, (round(valor_total / cantidad, 2) if cantidad else 0.0)

    h25c, h25v = _horas_col("HORAS_25", "VAL_SOBT_25")
    h50c, h50v = _horas_col("HORAS_50", "VAL_SOBT_50")
    h100c, h100v = _horas_col("HORAS_100", "VAL_SOBT_100")

    otros_ingresos = round(g("REEMBOLSOS") + g("MANIOBRAS") + g("BONIFICACION") + g("MOVILIZACION"), 2)
    anticipos = round(g("ANTICIPO_SUELDO") + g("ANTICIPOS_OTROS") + g("ANTICIPO_L_DESAHUCIO"), 2)
    prestamos = round(g("PRESTAMOS_QUIROGRAFARIOS") + g("PRESTAMOS_COMPANIA") + g("PRESTAMO_HIPOTECARIO"), 2)
    otros_descuentos = round(
        g("PENSION_ALIMENTICIA") + g("APORT_IESS_CONYUGE") + g("IMPUESTO_RENTA") + g("APORT_IESS"), 2
    )

    sbu_ref = None
    with contextlib.suppress(ValueError):
        sbu_ref = cfg.sbu(dt.date.fromisoformat(liq.fecha_salida).year)

    usuario = usuario or "Sistema"
    return {
        "empleado_codigo": liq.empleado,
        "empleado_cedula": liq.cedula,
        "empleado_nombres": liq.nombres,
        "empleado_apellidos": liq.apellidos,
        "cargo": liq.cargo or None,
        "puesto_servicio": liq.depto or None,
        "seccion": liq.seccion or None,
        "sueldo_basico_unificado": sbu_ref,
        "tipo_liquidacion": clasificar_tipo_liquidacion(liq.motivo_salida),
        "motivo": liq.motivo_salida or None,
        "fecha_ingreso": liq.fecha_ingreso or None,
        "fecha_salida": liq.fecha_salida or None,
        "dias_trabajados": liq.dias_trabajados,
        "anios_servicio": anios_servicio,
        "decimo_tercero": decimo_tercero,
        "decimo_cuarto": decimo_cuarto,
        "vacaciones_pendientes": round(g("VACACIONES_CALCULADAS"), 2),
        "fondo_reserva": round(g("FONDO_RESERVA"), 2),
        "bonificacion_desahucio": round(g("DESAHUCIO"), 2),
        "horas_extras": horas_extras,
        "horas_25_cantidad": h25c, "horas_25_valor_hora": h25v,
        "horas_50_cantidad": h50c, "horas_50_valor_hora": h50v,
        "horas_100_cantidad": h100c, "horas_100_valor_hora": h100v,
        "otros_ingresos": otros_ingresos,
        "anticipos": anticipos,
        "prestamos": prestamos,
        "multas": round(g("MULTAS"), 2),
        "otros_descuentos": otros_descuentos,
        "total_ingresos": round(g("TOTAL_INGRESOS"), 2),
        "total_descuentos": round(g("TOTAL_DESCUENTOS"), 2),
        "total_liquido": round(g("TOTAL_A_RECIBIR"), 2),
        "estado": estado,
        "observaciones": (
            "Simulación / borrador generado desde PDF individual."
            if estado == "borrador" else
            "Liquidación generada y guardada en el sistema."
        ),
        "created_by": usuario,
        "updated_by": usuario,
    }


# concepto_codigo -> (nombre, tipo, clave en Liquidacion.campos)
_CONCEPTOS_DETALLE: tuple[tuple[str, str, str, str], ...] = (
    ("SUELDO", "Sueldo", "ingreso", "SUELDO"),
    ("BONIFICACION", "Bonificación", "ingreso", "BONIFICACION"),
    ("MANIOBRAS", "Maniobras", "ingreso", "MANIOBRAS"),
    ("MOVILIZACION", "Movilización", "ingreso", "MOVILIZACION"),
    ("REEMBOLSOS", "Reembolsos", "ingreso", "REEMBOLSOS"),
    ("SOBT_25", "Sobretiempo 25%", "ingreso", "VAL_SOBT_25"),
    ("SOBT_50", "Sobretiempo 50%", "ingreso", "VAL_SOBT_50"),
    ("SOBT_100", "Sobretiempo 100%", "ingreso", "VAL_SOBT_100"),
    ("FONDO_RESERVA", "Fondo de Reserva 8,33%", "ingreso", "FONDO_RESERVA"),
    ("VACACIONES", "Vacaciones pendientes", "ingreso", "VACACIONES_CALCULADAS"),
    ("DEC_TERCERA_ANT", "Décima Tercera (anterior)", "ingreso", "DECIMA_TERCERA_ANTERIOR"),
    ("DEC_TERCERA_ACT", "Décima Tercera (actual)", "ingreso", "DECIMA_TERCERA_ACTUAL"),
    ("DEC_CUARTA_ANT", "Décima Cuarta (anterior)", "ingreso", "DECIMA_CUARTA_ANTERIOR"),
    ("DEC_CUARTA_ACT", "Décima Cuarta (actual)", "ingreso", "DECIMA_CUARTA_ACTUAL"),
    ("DESAHUCIO", "Bonificación Desahucio 25%", "ingreso", "DESAHUCIO"),
    ("INDEM_DESPIDO", "Indemnización por despido", "ingreso", "INDEM_DESPIDO"),
    ("IESS", "Aporte IESS personal", "descuento", "APORT_IESS"),
    ("IESS_CONYUGE", "Aporte IESS cónyuge", "descuento", "APORT_IESS_CONYUGE"),
    ("PREST_QUIROGRAFARIO", "Préstamo quirografario", "descuento", "PRESTAMOS_QUIROGRAFARIOS"),
    ("PREST_COMPANIA", "Préstamo compañía", "descuento", "PRESTAMOS_COMPANIA"),
    ("PREST_HIPOTECARIO", "Préstamo hipotecario", "descuento", "PRESTAMO_HIPOTECARIO"),
    ("ANTICIPO_SUELDO", "Anticipo de sueldo", "descuento", "ANTICIPO_SUELDO"),
    ("ANTICIPOS_OTROS", "Anticipos otros", "descuento", "ANTICIPOS_OTROS"),
    ("ANTICIPOS_SURTIDOS", "Anticipos surtidos", "descuento", "ANTICIPOS_SURTIDOS"),
    ("ANTICIPOS_OTROS_L", "Anticipo otros (liquidado)", "descuento", "ANTICIPOS_OTROS_L"),
    ("ANTICIPO_L_DESAHUCIO", "Anticipo liquidado (desahucio)", "descuento", "ANTICIPO_L_DESAHUCIO"),
    ("MULTAS", "Multas", "descuento", "MULTAS"),
    ("PENSION_ALIMENTICIA", "Pensión alimenticia", "descuento", "PENSION_ALIMENTICIA"),
    ("IMPUESTO_RENTA", "Impuesto a la renta", "descuento", "IMPUESTO_RENTA"),
)


def _construir_conceptos(liq: Liquidacion) -> list[dict]:
    """Arma `liquidaciones_detalle` a partir de `Liquidacion.campos`."""
    conceptos = []
    for codigo, nombre, tipo, clave in _CONCEPTOS_DETALLE:
        valor = float(liq.campos.get(clave) or 0)
        if valor == 0:
            continue
        conceptos.append({
            "concepto_codigo": codigo, "concepto_nombre": nombre,
            "concepto_tipo": tipo, "valor_total": round(valor, 2),
        })
    for idx, concepto in enumerate(conceptos):
        concepto["orden"] = idx
    return conceptos


def buscar_liquidacion_existente(cedula: str, fecha_salida_iso: str, estado: str,
                                  fecha_ingreso_iso: str = "") -> str | None:
    """Busca en `liquidaciones` un registro previo del mismo empleado + fecha
    de salida (+ ingreso si se da), para avisar antes de guardar por si ya
    existe. 'borrador' se busca aparte de todo estado real."""
    if not fecha_salida_iso:
        return None
    ced = normalizar_cedula(cedula)
    sb = supabase_client.get_client()
    q = sb.table(TABLA_LIQ).select("id").eq("empleado_cedula", ced).eq("fecha_salida", fecha_salida_iso)
    q = q.eq("estado", "borrador") if estado == "borrador" else q.neq("estado", "borrador")
    if fecha_ingreso_iso:
        q = q.eq("fecha_ingreso", fecha_ingreso_iso)
    filas = q.execute().data or []
    return filas[0]["id"] if filas else None


def guardar_liquidacion(
    liq: Liquidacion, estado: str, cfg: ConfigLiquidacion, *,
    usuario: str, roles: set[str], liquidacion_id_existente: str = "",
) -> tuple[bool, str]:
    """Inserta (o actualiza) una liquidación en `liquidaciones` + sus
    conceptos en `liquidaciones_detalle` (reemplazando los anteriores al
    actualizar). Devuelve (True, id) o (False, mensaje de error)."""
    if liq.error:
        return False, liq.error
    if estado not in ESTADOS_LIQUIDACION:
        return False, f"Estado inválido: {estado}"
    registro = _mapear_registro(liq, estado, cfg, usuario=usuario)
    conceptos = _construir_conceptos(liq)
    from core.audit.writer import audit_scope

    with audit_scope(
        "liquidaciones", "guardar_liquidacion", usuario=usuario, roles=roles,
        target_table=TABLA_LIQ, target_key=f"{liq.cedula}/{liq.fecha_salida}",
        after={"estado": estado, "total_liquido": registro["total_liquido"]},
    ):
        try:
            sb = supabase_client.get_client()
            if liquidacion_id_existente:
                sb.table(TABLA_LIQ).update(registro).eq("id", liquidacion_id_existente).execute()
                sb.table(TABLA_LIQ_DETALLE).delete().eq(
                    "liquidacion_id", liquidacion_id_existente
                ).execute()
                liquidacion_id = liquidacion_id_existente
            else:
                resultado = sb.table(TABLA_LIQ).insert(registro).execute()
                liquidacion_id = resultado.data[0]["id"]
            if conceptos:
                for c in conceptos:
                    c["liquidacion_id"] = liquidacion_id
                sb.table(TABLA_LIQ_DETALLE).insert(conceptos).execute()
            with contextlib.suppress(Exception):
                sb.table(TABLA_LIQ_HISTORIAL).insert({
                    "liquidacion_id": liquidacion_id, "estado": estado,
                    "usuario": usuario, "observacion": None,
                }).execute()
            return True, liquidacion_id
        except Exception as e:  # noqa: BLE001
            return False, str(e)


def listar_liquidaciones(
    *, texto: str = "", estado: str = "", tipo: str = "", limite: int = 200,
) -> list[dict]:
    """Lista de `liquidaciones` para el Editor/Gestión — más recientes primero."""
    sb = supabase_client.get_client()
    q = sb.table(TABLA_LIQ).select(
        "id,empleado_codigo,empleado_cedula,empleado_nombres,empleado_apellidos,"
        "cargo,fecha_salida,tipo_liquidacion,estado,total_liquido,created_at"
    )
    if estado:
        q = q.eq("estado", estado)
    if tipo:
        q = q.eq("tipo_liquidacion", tipo)
    if texto.strip():
        t = texto.strip()
        if t.isdigit() or normalizar_cedula(t) == t.zfill(10):
            q = q.or_(f"empleado_cedula.eq.{normalizar_cedula(t)},empleado_codigo.eq.{t}")
        else:
            q = q.or_(f"empleado_apellidos.ilike.%{t}%,empleado_nombres.ilike.%{t}%")
    filas = q.order("created_at", desc=True).limit(limite).execute().data or []
    for f in filas:
        f["nombre"] = f"{f.get('empleado_apellidos', '')} {f.get('empleado_nombres', '')}".strip()
    return filas


def obtener_liquidacion(liquidacion_id: str) -> tuple[dict | None, list[dict]]:
    """(registro, conceptos) de una liquidación guardada, o (None, [])."""
    sb = supabase_client.get_client()
    r = sb.table(TABLA_LIQ).select("*").eq("id", liquidacion_id).limit(1).execute()
    registro = r.data[0] if r.data else None
    if registro is None:
        return None, []
    conceptos = (
        sb.table(TABLA_LIQ_DETALLE).select("*").eq("liquidacion_id", liquidacion_id)
        .order("orden").execute().data or []
    )
    return registro, conceptos


def cambiar_estado_liquidacion(
    liquidacion_id: str, estado: str, *, usuario: str, roles: set[str], observacion: str = "",
) -> None:
    if estado not in ESTADOS_LIQUIDACION:
        raise ValueError(f"Estado inválido: {estado}")
    from core.audit.writer import audit_scope

    with audit_scope(
        "liquidaciones", "cambiar_estado", usuario=usuario, roles=roles,
        target_table=TABLA_LIQ, target_key=liquidacion_id, after={"estado": estado},
    ):
        sb = supabase_client.get_client()
        sb.table(TABLA_LIQ).update(
            {"estado": estado, "updated_by": usuario}
        ).eq("id", liquidacion_id).execute()
        with contextlib.suppress(Exception):
            sb.table(TABLA_LIQ_HISTORIAL).insert({
                "liquidacion_id": liquidacion_id, "estado": estado,
                "usuario": usuario, "observacion": observacion or None,
            }).execute()


def eliminar_liquidacion(
    liquidacion_id: str, motivo: str, *, usuario: str, roles: set[str],
) -> tuple[bool, str]:
    """Elimina una liquidación guardando antes un snapshot completo en
    `liquidaciones_eliminadas_historial` (mismo criterio que
    `eliminar_liquidacion_con_historial` del legado: no elimina si el estado
    ya es 'pagada'). `liquidaciones_detalle` cae solo por ON DELETE CASCADE."""
    from core.audit.writer import audit_scope

    sb = supabase_client.get_client()
    registro, conceptos = obtener_liquidacion(liquidacion_id)
    if registro is None:
        return False, "No existe esa liquidación."
    if registro.get("estado") == "pagada":
        return False, "No se puede eliminar una liquidación ya marcada como pagada."
    with audit_scope(
        "liquidaciones", "eliminar_liquidacion", usuario=usuario, roles=roles,
        target_table=TABLA_LIQ, target_key=liquidacion_id,
        antes={"estado": registro.get("estado"), "total_liquido": registro.get("total_liquido")},
    ):
        try:
            with contextlib.suppress(Exception):
                sb.table(TABLA_LIQ_ELIMINADAS).insert({
                    "liquidacion_id": liquidacion_id, "registro": registro,
                    "conceptos": conceptos, "motivo": motivo or None, "usuario": usuario,
                }).execute()
            sb.table(TABLA_LIQ).delete().eq("id", liquidacion_id).execute()
            return True, ""
        except Exception as e:  # noqa: BLE001
            return False, str(e)


# concepto_codigo -> clave de Liquidacion.campos, para reconstruir (inverso de
# _CONCEPTOS_DETALLE, colapsando los que comparten clave, ej. FONDO_RESERVA).
_CODIGO_A_CLAVE_CAMPO: dict[str, str] = {cod: clave for cod, _n, _t, clave in _CONCEPTOS_DETALLE}


def reconstruir_liquidacion(registro: dict, conceptos: list[dict]) -> Liquidacion:
    """Reconstruye una `Liquidacion` aproximada a partir de lo ya guardado en
    Supabase (`liquidaciones` + `liquidaciones_detalle`), para regenerar el
    PDF/Excel de un registro guardado sin volver a calcular contra SQL
    Server. El desglose mensual (vacaciones/décimos) no se guarda, así que
    no se reconstruye — el total sí sale bien, solo falta el detalle mes a
    mes si se pide "mostrar insumos"."""
    valores: dict[str, float] = {}
    for c in conceptos:
        cod = str(c.get("concepto_codigo") or "")
        clave = _CODIGO_A_CLAVE_CAMPO.get(cod)
        if clave:
            valores[clave] = valores.get(clave, 0.0) + float(c.get("valor_total") or 0)

    campos = dict(valores)
    campos.setdefault("FONDO_RESERVA", float(registro.get("fondo_reserva") or 0))
    campos.setdefault("VACACIONES_CALCULADAS", float(registro.get("vacaciones_pendientes") or 0))
    campos.setdefault("DESAHUCIO", float(registro.get("bonificacion_desahucio") or 0))
    campos["HORAS_25"] = registro.get("horas_25_cantidad") or 0
    campos["HORAS_50"] = registro.get("horas_50_cantidad") or 0
    campos["HORAS_100"] = registro.get("horas_100_cantidad") or 0
    total_ingresos = round(sum(campos.get(k, 0) for k in (
        "SUELDO", "VAL_SOBT_25", "VAL_SOBT_50", "VAL_SOBT_100", "FONDO_RESERVA",
        "MANIOBRAS", "MOVILIZACION", "REEMBOLSOS", "BONIFICACION",
    )), 2)
    campos["TOTAL_INGRESOS"] = total_ingresos
    campos["TOTAL_DESCUENTOS"] = round(float(registro.get("total_descuentos") or 0), 2)
    campos["TOTAL_A_RECIBIR"] = round(float(registro.get("total_liquido") or 0), 2)

    apellidos = str(registro.get("empleado_apellidos") or "")
    nombres = str(registro.get("empleado_nombres") or "")
    return Liquidacion(
        empleado=str(registro.get("empleado_codigo") or ""),
        nombre=f"{apellidos} {nombres}".strip(),
        cedula=str(registro.get("empleado_cedula") or ""),
        cargo=str(registro.get("cargo") or ""), depto=str(registro.get("puesto_servicio") or ""),
        seccion=str(registro.get("seccion") or ""),
        sueldo_base=float(campos.get("SUELDO", 0)),
        fecha_ingreso=str(registro.get("fecha_ingreso") or ""),
        fecha_salida=str(registro.get("fecha_salida") or ""),
        motivo_salida=str(registro.get("motivo") or ""),
        dias_trabajados=int(registro.get("dias_trabajados") or 0),
        campos=campos, apellidos=apellidos, nombres=nombres,
    )
