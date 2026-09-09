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
    """Fórmula legal de indemnización por despido intempestivo (Código de
    Trabajo Ecuador): <3 años de servicio = 3×sueldo; ≥3 años = años×sueldo
    (tope 25).

    ADVERTENCIA -- NO se llama automáticamente desde `procesar_empleado`
    (ver el campo `INDEM_DESPIDO` ahí, siempre en 0.0). Verificado contra
    `Generador_Liquidaciones_INSEVIG.pyw` (el `.pyw` que la empresa usa hoy
    en producción, no el `Liquidaciones_generador_SUPABASE.py` de donde
    salió por error esta fórmula en una versión anterior de este archivo):
    ahí "Indemnización por Despido" es un campo EDITABLE MANUAL en la vista
    previa (`_fila_editable`, default $0), nunca un cálculo automático
    disparado por el texto del motivo -- ni siquiera existe una función
    equivalente en `nucleo_modular` (se verificó su ausencia deliberada).
    Con auto-cálculo, cualquier liquidación con motivo "DESPIDO"/
    "INTEMPESTIVO" sumaba de más sin revisión humana -- bug real, corregido
    (ver docs/modulos/liquidaciones.md). Esta función se deja disponible
    por si en el futuro se quiere ofrecer como un botón "sugerir monto" en
    un campo editable equivalente -- no debe volver a invocarse dentro de
    `procesar_empleado` sin ese contexto.
    """
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


def _horas_seccion(seccion_codigo: str | None, fuente: str) -> tuple[float, float, float]:
    """Horas mensuales de sobretiempo (25%/50%/100%) configuradas para una
    sección en DBTABLAS (TIPO='SEC'): FACTOR/T_C/T_P. Solo se usa para el
    "mes en curso" (ver `calcular_desde_dbtablas` en `procesar_empleado`) --
    RPINGDES todavía no tiene $ real posteado para ese mes. Porta
    `obtener_horas_seccion` de `nucleo_modular/acceso_sqlserver.py`.
    `(0.0, 0.0, 0.0)` si no se encuentra o falta `seccion_codigo`.
    """
    codigo = str(seccion_codigo or "").strip()
    if not codigo:
        return (0.0, 0.0, 0.0)
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        for con_codemp in (True, False):
            q = sb.table("dbtablas").select("factor,t_c,t_p").eq("tipo", "SEC").eq("codigo", codigo)
            if con_codemp:
                q = q.eq("codemp", "10")
            try:
                r = q.limit(1).execute()
            except Exception:  # noqa: BLE001 - degradar sin bloquear la liquidación
                return (0.0, 0.0, 0.0)
            if r.data:
                f = r.data[0]
                return (a_float(f.get("factor")), a_float(f.get("t_c")), a_float(f.get("t_p")))
        return (0.0, 0.0, 0.0)
    for query in (
        "SELECT FACTOR, T_C, T_P FROM dbo.DBTABLAS WHERE TIPO='SEC' AND "
        "LTRIM(RTRIM(CODIGO))=? AND CODEMP='10'",
        "SELECT FACTOR, T_C, T_P FROM dbo.DBTABLAS WHERE TIPO='SEC' AND LTRIM(RTRIM(CODIGO))=?",
    ):
        filas = sqlserver.filas(query, (codigo,))
        if filas:
            f = filas[0]
            return (a_float(f.get("FACTOR")), a_float(f.get("T_C")), a_float(f.get("T_P")))
    return (0.0, 0.0, 0.0)


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


MESES_NOMBRE = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def _suma_base_mensual(
    empleado: str, inicio: dt.date, fin: dt.date, fuente: str,
) -> tuple[float, list[DetalleMesDecimo]]:
    """Igual que `_suma_base`, pero además devuelve el desglose mes a mes.

    Porta `obtener_total_periodo_decimos` de
    `LIQUIDACIONES_SISTEMA_INSEVIG/nucleo_modular/calculos_decimos.py`
    (sin la rama de prorrateo del mes en curso -- este repo no la
    implementaba antes de este cambio y no es parte de lo pedido; si se
    necesita, es un cálculo aparte). Etiqueta EXACTA que ya consume el bot
    RPA MRL: ``f"{nombre_mes} -{año}"`` (espacio antes del guion, ninguno
    después) -- no cambiar el formato sin avisar al lado que lo lee.
    """
    total = 0.0
    detalle: list[DetalleMesDecimo] = []
    y, mth = inicio.year, inicio.month
    while dt.date(y, mth, 1) <= fin:
        mes_total = 0.0
        movs, _ = movimientos_mes(empleado, y, mth, fuente)
        for mv in movs:
            if mv["clase"] in CONCEPTOS_BASE:
                mes_total += mv["valor"]
        total += mes_total
        detalle.append(DetalleMesDecimo(label=f"{MESES_NOMBRE[mth]} -{y}", valor=round(mes_total, 2)))
        mth, y = (1, y + 1) if mth == 12 else (mth + 1, y)
    return round(total, 2), detalle


@dataclass
class DetalleMesDecimo:
    label: str
    valor: float


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


def descuentos_pendientes_de(cedula: str) -> list[dict] | None:
    """Descuentos conocidos de antemano por cédula (préstamo no descontado
    en nómina, dotación no devuelta, etc. -- tabla `descuentos_pendientes`,
    pantalla "Descuentos Pendientes" del `.pyw`) que todavía no se aplicaron
    a ninguna liquidación. `None` si no se pudo consultar (se degrada sin
    bloquear la liquidación, igual que `vacaciones_pagadas`/`_gozadas`).
    Cada item: `{"id", "monto", "motivo"}`.
    """
    ced = normalizar_cedula(cedula)
    try:
        sb = supabase_client.get_client()
        r = (
            sb.table("descuentos_pendientes")
            .select("id,monto,motivo")
            .eq("empleado_cedula", ced)
            .eq("estado", "pendiente")
            .execute()
        )
    except Exception:  # noqa: BLE001 - degradar sin bloquear la liquidación
        return None
    return [
        {"id": f["id"], "monto": a_float(f.get("monto")), "motivo": f.get("motivo") or ""}
        for f in (r.data or [])
    ]


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


def buscar_empleado_preview(identificador: str, modo: str, fuente: str) -> dict | None:
    """Busca UN empleado por cédula/código/nombre para el modo "Individual" de
    la pantalla principal (combo "Buscar por:" del `.pyw`). Devuelve un dict
    liviano para el panel de solo-lectura (Nombre/Cargo/Sección/Fecha de
    Ingreso/Sueldo) y la cédula normalizada para pasar a `procesar_empleado`.
    """
    identificador = (identificador or "").strip()
    if not identificador:
        return None
    emp: dict | None = None
    if modo == "codigo":
        cod = identificador
        if fuente == FUENTE_SUPABASE:
            sb = supabase_client.get_client()
            r = sb.table("rpemplea").select("*").eq("codemp", "10").eq("empleado", cod).limit(1).execute()
            if r.data:
                emp = {k.upper(): v for k, v in r.data[0].items()}
        else:
            flt = get_settings().sqlserver_filter
            filas = sqlserver.filas(
                f"""SELECT [EMPLEADO],[APELLIDOS],[NOMBRES],[CEDULA],[SUELDO],[CARGO],[DEPTO],
                           [SECCION],[FECHA_ING],[FECHA_SAL],[ESTADO],[HOR25],[HOR50],[HOR100]
                    FROM [insevig].[dbo].[RPEMPLEA] WHERE {flt} AND [EMPLEADO] = ?""",
                (cod,),
            )
            emp = filas[0] if filas else None
    elif modo == "nombre":
        # Búsqueda por apellidos/nombres inline (no se importa
        # core.repos.empleados: los repos no se cruzan entre sí, ver
        # tests/test_arquitectura.py::test_repos_no_se_importan_entre_si).
        texto = identificador
        if fuente == FUENTE_SUPABASE:
            sb = supabase_client.get_client()
            r = (
                sb.table("rpemplea").select("*").eq("codemp", "10")
                .or_(f"apellidos.ilike.%{texto}%,nombres.ilike.%{texto}%")
                .order("apellidos").limit(1).execute()
            )
            if r.data:
                emp = {k.upper(): v for k, v in r.data[0].items()}
        else:
            flt = get_settings().sqlserver_filter
            filas = sqlserver.filas(
                f"""SELECT TOP 1 [EMPLEADO],[APELLIDOS],[NOMBRES],[CEDULA],[SUELDO],[CARGO],[DEPTO],
                           [SECCION],[FECHA_ING],[FECHA_SAL],[ESTADO],[HOR25],[HOR50],[HOR100]
                    FROM [insevig].[dbo].[RPEMPLEA]
                    WHERE {flt} AND ([APELLIDOS] LIKE ? OR [NOMBRES] LIKE ?) ORDER BY [APELLIDOS]""",
                (f"%{texto}%", f"%{texto}%"),
            )
            emp = filas[0] if filas else None
    else:  # "cedula" (por defecto)
        emp = _empleado(identificador, fuente)
    if emp is None:
        return None
    return {
        "cedula": normalizar_cedula(emp.get("CEDULA")),
        "empleado": str(emp.get("EMPLEADO") or "").strip(),
        "nombre": f"{(emp.get('APELLIDOS') or '').strip()} {(emp.get('NOMBRES') or '').strip()}".strip(),
        "cargo": str(emp.get("CARGO") or ""),
        "seccion": str(emp.get("SECCION") or ""),
        "fecha_ingreso": str(emp.get("FECHA_ING") or ""),
        "sueldo": a_float(emp.get("SUELDO")),
    }


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
    # Desglose mes a mes de la Décima Tercera ACTUAL (para el bot RPA MRL,
    # tabla `liquidaciones_periodos_calculo`). La ANTERIOR nunca se detalla
    # aquí -- ver el docstring de `_suma_base_mensual` y la memoria de este
    # proyecto (decimo_anterior_no_pagado_no_debe_aparecer): el .pyw
    # original tampoco persiste ese detalle, ni siquiera como referencia.
    detalle_decimo_tercera: list[DetalleMesDecimo] = field(default_factory=list)
    # Ids de `descuentos_pendientes` (estado='pendiente') consumidos en el
    # cálculo de esta liquidación -- ver `descuentos_pendientes_de`. Quien
    # persista (guardar_liquidacion) debe marcarlos 'aplicado' recién
    # cuando la liquidación se guarda de verdad, nunca en una simulación.
    descuentos_aplicados: list[str] = field(default_factory=list)


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
    incluir_dec13_anterior: bool = False,
    incluir_dec14_anterior: bool = False,
    incluir_sueldo: bool = True,
    usar_ingresos_reales_desahucio: bool = False,
    indemnizacion_manual: float = 0.0,
    periodo_calc_anio: int | None = None,
    periodo_calc_mes: int | None = None,
    usar_valores_reales_mes_actual: bool = False,
    default_multas: float = 0.0,
    default_antic_otros: float = 0.0,
) -> Liquidacion:
    """Procesa un empleado y arma su liquidación.

    `incluir_sueldo` (default `True`): si `False`, excluye TODO el rol
    regular del mes de salida -- sueldo, sobretiempos y los descuentos de
    ese mismo mes -- por si ya se pagó/descontó por otra vía y no debe
    liquidarse de nuevo aquí. No afecta `sueldo_base` (el básico registrado
    de RPEMPLEA, que se sigue mostrando igual). Porta la casilla "Incluir el
    Sueldo del mes de salida..." del modo individual y el 4º campo
    SIPAGO/NOPAGO de una línea en modo lote del `.pyw` (no portado aún del
    lado de `procesar_lote`/`_parse_linea` -- ver docs/modulos/liquidaciones.md).

    `default_multas`/`default_antic_otros` (default `0.0`, agregados
    2026-09): "4. Valores por Defecto" del `.pyw` -- si el rubro real de
    MULTAS/ANTICIPOS_OTROS del mes de salida da $0, se reemplaza por este
    valor (nunca se SUMA, se reemplaza -- mismo criterio que
    `if fila['MULTAS'] == 0 and self._default_multas > 0`). No se aplica
    si `incluir_sueldo=False` (el `.pyw` no deja que un default se cuele
    justo en el mes que se pidió dejar en $0 a propósito). Usado por
    `recalcular_liquidacion` para reproducir "🔄 Recalcular Liquidación"
    del Editor con los mismos valores por defecto que tenía la
    liquidación original -- si se omiten acá, el recálculo puede dar un
    MULTAS/ANTICIPOS_OTROS distinto (0) al que se guardó originalmente.

    `indemnizacion_manual` (default `0.0`): monto de indemnización por
    despido intempestivo que la persona ingresó a mano -- pasa tal cual a
    `campos["INDEM_DESPIDO"]` y se suma al total en el mismo lugar donde
    antes iba el auto-cálculo (ver corrección de más arriba: nunca se
    calcula solo, es puramente lo que el llamador decida pasar).

    `periodo_calc_anio`/`periodo_calc_mes` (default `None`, ambos): "3.
    Periodo para Calcular Horas" del `.pyw` -- cuando coinciden con el año/
    mes de `fecha_salida`, ese mes se trata como "en curso" (todavía
    abierto, sin $ real posteado): las horas de sobretiempo se estiman
    desde el cupo mensual de la sección (DBTABLAS SEC) en vez del $ real de
    los movimientos, y Sueldo/Bonificación se prorratean por días
    trabajados. Si se omiten (default), el comportamiento es idéntico al de
    antes de agregar este parámetro -- SIEMPRE se trata el mes como
    "cerrado" (horas derivadas del $ real). `usar_valores_reales_mes_actual`
    NO tiene efecto si no se configura este periodo (ver ese parámetro).

    `usar_valores_reales_mes_actual` (default `False`): solo importa cuando
    `periodo_calc_anio`/`periodo_calc_mes` coinciden con el mes de salida
    (mes "en curso"). Si `True`, en vez de la fórmula del cupo de sección
    usa lo que YA esté cargado en RPINGDES para ese mes (igual que un mes
    cerrado) -- útil cuando se sabe que ya hay valores reales aunque el mes
    no esté formalmente cerrado. No afecta el prorrateo de Sueldo/
    Bonificación, que depende solo de `periodo_calc_anio`/`periodo_calc_mes`.

    `usar_ingresos_reales_desahucio` (default `False`): si `True`, la base
    mensual del desahucio deja de ser el sueldo básico de RPEMPLEA y pasa a
    ser el promedio real del último periodo de vacaciones (incluye
    sobretiempos), dividido por los meses que ese periodo realmente abarca.
    Porta la casilla equivalente del modo individual.

    `incluir_dec13_anterior`/`incluir_dec14_anterior` (default `False`):
    controla si el décimo tercero/cuarto del periodo ANTERIOR (ya pagado en
    su momento) se suma a `total_ingresos` (y por lo tanto al total a
    recibir) además de mostrarse como referencia en
    `campos["DECIMA_TERCERA_ANTERIOR"]`/`["DECIMA_CUARTA_ANTERIOR"]`.

    CORRECCIÓN (ver docs/modulos/liquidaciones.md): una versión anterior de
    este archivo tenía el default en `True`. Se verificó contra
    `Generador_Liquidaciones_INSEVIG.pyw` (`_procesar_empleado`,
    `_parsear_entrada_cedulas`) que el comportamiento REAL en las dos
    pantallas que existen hoy es excluir el anterior por defecto: en modo
    LOTE el campo está *hardcodeado en False* sin forma de activarlo
    ("pedido explícito del usuario: incluir el décimo anterior es una
    decisión puntual, caso por caso... nunca en un proceso masivo"), y en
    modo individual la casilla equivalente nace *desmarcada*. El default
    `True` de la propia función `_procesar_empleado` en el `.pyw` nunca se
    ejercita en la práctica porque ambos llamadores siempre pasan el valor
    explícito. `procesar_lote()` de este archivo, en cambio, SÍ dependía del
    default (no pasaba el argumento) -- con `True` estaba incluyendo de más
    el décimo anterior en cada liquidación de lote generada por el sistema
    web, cosa que el `.pyw` nunca permite. Corregido aquí para que
    `procesar_lote` sin overrides coincida con el comportamiento real.
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

    # 3. Horas de sobretiempo.
    #
    # calcular_desde_dbtablas: True solo si periodo_calc_anio/periodo_calc_mes
    # (parámetros opcionales, "3. Periodo para Calcular Horas" del .pyw)
    # coinciden con el mes de salida -- normalmente ese mes está todavía
    # abierto, sin $ real posteado. Si no se pasan (default), esto nunca es
    # True y el comportamiento es idéntico al de antes de este cambio.
    calcular_desde_dbtablas = (
        periodo_calc_anio is not None and periodo_calc_mes is not None
        and fsal.year == periodo_calc_anio and fsal.month == periodo_calc_mes
    )
    inicio_mes = dt.date(fsal.year, fsal.month, 1)
    if fing.year == fsal.year and fing.month == fsal.month and fing > inicio_mes:
        inicio_mes = fing
    dias_laborados = max(0, (fsal - inicio_mes).days + 1)

    h25 = h50 = h100 = 0
    if calcular_desde_dbtablas and not usar_valores_reales_mes_actual:
        # Mes en curso: horas desde el cupo mensual de la sección (DBTABLAS),
        # prorrateado por días trabajados -- todavía no hay $ real posteado.
        hrs_sec = _horas_seccion(emp.get("SECCION"), fuente)
        if hrs_sec[0] > 0:
            h25 = int(round((hrs_sec[0] / 30) * dias_laborados))
        if hrs_sec[1] > 0:
            h50 = int(round((hrs_sec[1] / 30) * dias_laborados))
        if hrs_sec[2] > 0:
            h100 = int(round((hrs_sec[2] / 30) * dias_laborados))
        if sueldo > 0:
            val["SOBRETIEMPO_25"] = round((sueldo / 240) * 0.25 * h25, 2)
            val["SOBRETIEMPO_50"] = round((sueldo / 240) * 1.5 * h50, 2)
            val["SOBRETIEMPO_100"] = round((sueldo / 240) * 2.0 * h100, 2)
    else:
        # Mes cerrado (o usar_valores_reales_mes_actual=True): si YA vino un
        # valor $ real en los movimientos, las horas se derivan de ESE $
        # (redondeando) y el $ final se RECALCULA desde esas horas enteras
        # -- no se deja el $ real con su propio redondeo de nómina, que
        # puede no cuadrar con la fórmula del MRL (corregido; antes las
        # "horas" mostradas venían siempre de RPEMPLEA, sin relación con el
        # $ real ya sumado -- podían no coincidir entre sí). Si NO vino un
        # $ real, se usa el cupo asignado en RPEMPLEA (HOR25/50/100) como
        # estimación -- mismo comportamiento que antes.
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

    # 3c. Prorratear Sueldo/Bonificación al mes en curso -- ligado SOLO a
    # calcular_desde_dbtablas (no a usar_valores_reales_mes_actual, igual
    # que el .pyw real): RPINGDES trae el Sueldo/Bonificación proyectados al
    # mes completo (DIAS=30 en el movimiento) porque a esa fecha el sistema
    # de nómina no sabe todavía que el empleado va a salir antes de que
    # termine el mes.
    if calcular_desde_dbtablas:
        dias_base_mov = dias_mov if dias_mov else 30
        if dias_base_mov and dias_laborados < dias_base_mov:
            factor_prorateo = dias_laborados / dias_base_mov
            val["SUELDO"] = round(val["SUELDO"] * factor_prorateo, 2)
            val["BONIFICACION"] = round(val["BONIFICACION"] * factor_prorateo, 2)
            dias_mov = dias_laborados

    # 3b. incluir_sueldo=False: excluye TODO el rol regular del mes de salida
    # (no solo Sueldo) -- si ese rol ya se pagó/descontó por otra vía, las
    # horas extras y los descuentos de ese mismo mes tampoco deben
    # liquidarse de nuevo aquí. `sueldo` (básico registrado, columna
    # "Sueldo"/REMUNERACION) NO se ve afectado -- viene de RPEMPLEA, no de
    # `val`. Lista exacta verificada contra Generador_Liquidaciones_INSEVIG.pyw
    # (`_procesar_empleado`, constante `CAMPOS_ROL_MES`).
    if not incluir_sueldo:
        for _campo in (
            "SUELDO", "SOBRETIEMPO_25", "SOBRETIEMPO_50", "SOBRETIEMPO_100",
            "ANTICIPOS_SURTIDOS", "PRESTAMOS_COMPANIA", "ANTICIPOS_OTROS",
            "ANTICIPO_SUELDO", "MULTAS", "PRESTAMOS_QUIROGRAFARIOS",
            "APORT_IESS_CONYUGE", "PENSION_ALIMENTICIA", "PRESTAMO_HIPOTECARIO",
            "IMPUESTO_RENTA",
        ):
            val[_campo] = 0.0
    else:
        # "4. Valores por Defecto" del .pyw: reemplaza (no suma) MULTAS/
        # ANTICIPOS_OTROS si el rubro real del mes de salida da $0 --
        # nunca se aplica si incluir_sueldo=False (ver arriba), para no
        # colar un default justo en el mes que se dejó en $0 a propósito.
        if val["MULTAS"] == 0 and default_multas > 0:
            val["MULTAS"] = round(default_multas, 2)
        if val["ANTICIPOS_OTROS"] == 0 and default_antic_otros > 0:
            val["ANTICIPOS_OTROS"] = round(default_antic_otros, 2)

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
    detalle_dec13: list[DetalleMesDecimo] = []
    p13 = periodos_decima_tercera(fing, fsal)
    for idx, (i, f, _pag) in enumerate(p13):
        es_actual = idx > 0 or len(p13) == 1
        if es_actual:
            total_periodo, detalle_dec13 = _suma_base_mensual(cod, i, f, fuente)
        else:
            total_periodo = _suma_base(cod, i, f, fuente)
        dec = round(total_periodo / 12, 2)
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

    # 7. Desahucio. Por defecto usa el sueldo básico de RPEMPLEA (mensual
    # completo). Con usar_ingresos_reales_desahucio=True se usa en cambio el
    # promedio mensual real del último periodo de vacaciones (incluye
    # sobretiempos) -- divisor: la cantidad de MESES que ese último periodo
    # realmente abarca (no siempre 12: el periodo "actual" puede llevar
    # acumulados solo unos pocos meses). Verificado contra
    # Generador_Liquidaciones_INSEVIG.pyw (comentario "CÁLCULO DE DESAHUCIO"):
    # dividir siempre entre 12 fijo daba un promedio muy por debajo del real
    # para alguien a mitad de su periodo de vacaciones.
    base_desahucio = sueldo
    if usar_ingresos_reales_desahucio and vac_ult > 0:
        i_ult, f_ult = pv[-1]
        meses_ultimo_periodo = (f_ult.year - i_ult.year) * 12 + (f_ult.month - i_ult.month) + 1
        if meses_ultimo_periodo <= 0:
            meses_ultimo_periodo = 12
        base_desahucio = round(vac_ult / meses_ultimo_periodo, 2)
    des = desahucio(fing, fsal, base_desahucio)

    # 8. Fondo de reserva = 8.33% de la base del mes de salida
    fondo_reserva = round((val["SUELDO"] + val["SOBRETIEMPO_25"] + val["SOBRETIEMPO_50"]
                           + val["SOBRETIEMPO_100"] + val["BONIFICACION"] + val["MANIOBRAS"])
                          * FONDO_RESERVA_PCT, 2)
    if val["FONDO_RESERVA"] > 0:
        fondo_reserva = val["FONDO_RESERVA"]

    # 9. IESS
    base_iess = val["SUELDO"] + val["SOBRETIEMPO_25"] + val["SOBRETIEMPO_50"] + val["SOBRETIEMPO_100"]
    iess = round(base_iess * cfg.iess_personal_pct, 2)

    # 10. Indemnización por despido intempestivo: campo MANUAL, no
    # auto-calculado. Verificado contra Generador_Liquidaciones_INSEVIG.pyw
    # (el `.pyw` real de producción): "Indemnización por Despido" es un
    # campo editable con default $0 en la vista previa, nunca disparado
    # automáticamente por el texto del motivo -- ver docstring de
    # `indemnizacion_despido` para el detalle de esta corrección (bug real:
    # una versión anterior de este archivo lo calculaba solo, sumando de
    # más sin revisión humana en cualquier liquidación con motivo
    # DESPIDO/INTEMPESTIVO). `indemnizacion_manual` deja que el llamador
    # (UI del modo Individual) pase el valor que la persona ingresó a mano,
    # igual que el campo editable del `.pyw`.
    indem = round(indemnizacion_manual, 2)

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

    # 12. Totales. El décimo ANTERIOR (13ro y 14to) NO se incluye por
    # defecto en el total -- coincide con el comportamiento real del .pyw en
    # sus dos pantallas actuales (lote: hardcodeado en False sin poder
    # activarlo; individual: casilla desmarcada por defecto). Se puede
    # incluir explícitamente con incluir_dec13_anterior/incluir_dec14_anterior
    # =True, opción que en el .pyw solo existe en modo individual (ver
    # docstring de esta función para el historial de esta corrección).
    dec13_ant_incluido = d13_ant if incluir_dec13_anterior else 0.0
    dec14_ant_incluido = d14_ant if incluir_dec14_anterior else 0.0
    total_ingresos = round(
        val["SUELDO"] + val["BONIFICACION"] + val["MANIOBRAS"] + val["MOVILIZACION"]
        + val["REEMBOLSOS"] + val["SOBRETIEMPO_25"] + val["SOBRETIEMPO_50"] + val["SOBRETIEMPO_100"]
        + fondo_reserva + vac_calc + dec13_ant_incluido + d13_act
        + dec14_ant_incluido + d14_act + des + indem, 2,
    )
    # 13. Descuentos pendientes registrados de antemano (pantalla "Descuentos
    # Pendientes" del .pyw): se suman aquí como un descuento más. Solo pasan
    # a 'aplicado' cuando la liquidación se GUARDA de verdad (responsabilidad
    # de guardar_liquidacion/quien persista, con los ids de
    # descuentos_aplicados) -- generar/previsualizar nunca los consume, se
    # puede repetir la simulación las veces que haga falta.
    pendientes = descuentos_pendientes_de(ced) or []
    monto_descuentos_pendientes = round(sum(p["monto"] for p in pendientes), 2)
    descuentos_aplicados = [p["id"] for p in pendientes]

    total_descuentos = round(
        val["ANTICIPOS_SURTIDOS"] + val["PRESTAMOS_COMPANIA"] + val["ANTICIPOS_OTROS"]
        + val["ANTICIPO_SUELDO"] + val["MULTAS"] + ant_otros_l + ant_l_des
        + val["PRESTAMOS_QUIROGRAFARIOS"] + val["APORT_IESS_CONYUGE"] + val["PENSION_ALIMENTICIA"]
        + val["PRESTAMO_HIPOTECARIO"] + iess + val["IMPUESTO_RENTA"] + monto_descuentos_pendientes, 2,
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
        "DESCUENTOS_REGISTRADOS": monto_descuentos_pendientes,
        "TOTAL_A_RECIBIR": round(total_ingresos - total_descuentos, 2),
    }
    return Liquidacion(
        empleado=cod, nombre=nombre, cedula=ced,
        cargo=str(emp.get("CARGO") or ""), depto=str(emp.get("DEPTO") or ""),
        seccion=str(emp.get("SECCION") or ""), sueldo_base=sueldo,
        fecha_ingreso=str(fing), fecha_salida=str(fsal), motivo_salida=motivo,
        dias_trabajados=dias_trab, campos=campos, alertas=alertas_vac,
        apellidos=apellidos_emp, nombres=nombres_emp, detalle_vacaciones=detalle_vac,
        detalle_decimo_tercera=detalle_dec13,
        descuentos_aplicados=descuentos_aplicados,
    )


def procesar_lote(
    texto: str, fuente: str, cfg: ConfigLiquidacion, *,
    default_multas: float = 0.0, default_antic_otros: float = 0.0,
) -> list[Liquidacion]:
    """`default_multas`/`default_antic_otros`: "4. Valores por Defecto" del
    `.pyw` -- un único valor para todo el lote (mismo control que el modo
    Individual, ver `procesar_empleado`), no por línea."""
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
        out.append(procesar_empleado(
            ced, fecha, motivo, fuente, cfg, fecha_ingreso=fecha_ing,
            default_multas=default_multas, default_antic_otros=default_antic_otros,
        ))
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
TABLA_LIQ_AJUSTES = "liquidaciones_ajustes_concepto"  # confirmada existente en producción
TABLA_LIQ_PERIODOS = "liquidaciones_periodos_calculo"

# CORREGIDO (2026-09): "pagada" no coincidía con el valor real que usa
# producción -- Generador_Liquidaciones_INSEVIG.pyw (la app que escribió
# las 4100+ liquidaciones existentes) guarda 'pagado' (masculino, no
# 'pagada'). Con el valor viejo, guardar_liquidacion(estado='pagado')
# rebotaba con "Estado inválido" y -- más grave -- los guardas
# `if registro.get("estado") == "pagada"` de editar_valores_liquidacion/
# eliminar_liquidacion NUNCA coincidían con un registro real: la
# protección contra editar/eliminar una liquidación ya pagada estaba
# rota en silencio para el 100% de los datos reales.
#
# FLUJO COMPLETO (2026-09-08, paridad total pedida por el usuario) --
# verificado línea por línea contra "Gestión de Liquidaciones" del `.pyw`
# (ACCION_POR_ESTADO/_abrir_dialogo_*, líneas ~13600-14045):
#   generada -> aprobado -> registrado_mrl -> cheque_listo ->
#       {pagado | consignada} -> legalizada_mrl
#   (+ 'cancelado', 'borrador', 'impreso', 'archivado')
#
# IMPORTANTE -- chequeado contra los datos reales de producción (2026-09-08,
# 4101 filas): SOLO existen 'generada' (198) y 'pagado' (3903). Cero filas
# en 'aprobado'/'registrado_mrl'/'cheque_listo'/'consignada'/
# 'legalizada_mrl'/'impreso'/'archivado'/'cancelado'/'borrador' -- el flujo
# de aprobación intermedio existe en el código del `.pyw` pero nadie lo usa
# en la práctica hoy. Se implementa de todos modos por pedido explícito del
# usuario (paridad completa con la interfaz, no con el uso real).
#
# 'impreso'/'archivado': aparecen en `ESTADOS_AVANZADOS` del `.pyw` (línea
# ~8366) pero NO tienen ninguna entrada en `ACCION_POR_ESTADO` de Gestión de
# Liquidaciones -- no se encontró el disparador real de estas dos
# transiciones en el código leído; se dejan declaradas (sin fila en
# TRANSICIONES que lleve a ellas) hasta encontrar de dónde salen.
# 'cancelado': mismo caso, sin botón confirmado en Gestión de
# Liquidaciones -- se asume alcanzable desde 'generada'/'aprobado' (chips
# de filtro CHIPS_FILA_2/línea ~9647 lo sugieren) pero no está confirmado
# con un botón real.
ESTADOS_LIQUIDACION = (
    "borrador", "generada", "aprobado", "registrado_mrl", "cheque_listo",
    "consignada", "pagado", "legalizada_mrl", "impreso", "archivado", "cancelado",
)

# Transiciones válidas desde cada estado (para que la UI sepa qué botones
# mostrar). Ver el comentario de ESTADOS_LIQUIDACION para la evidencia de
# cada tramo -- 'impreso'/'archivado' quedan sin fila de origen (no
# confirmado); 'cancelado' es un supuesto razonable, no confirmado.
TRANSICIONES: dict[str, tuple[str, ...]] = {
    "borrador": ("generada",),
    "generada": ("aprobado", "cancelado"),
    "aprobado": ("registrado_mrl", "cancelado"),
    "registrado_mrl": ("cheque_listo",),
    "cheque_listo": ("pagado", "consignada"),
    "pagado": ("legalizada_mrl",),
    "consignada": ("legalizada_mrl",),
    "legalizada_mrl": (),
    "impreso": (),
    "archivado": (),
    "cancelado": (),
}

# Campos de "seguimiento de firma y cobro" (panel de detalle, botón
# "Guardar todo" del .pyw) -- independientes del estado, se pueden guardar
# en cualquier momento. Ver guardar_seguimiento().
_CAMPOS_SEGUIMIENTO = (
    "color_etiqueta", "lugar_firma", "numero_acta", "fecha_firma_acuerdo",
    "fecha_lista_cobro", "fecha_citado_cobro", "fecha_consignacion", "observaciones",
)


def _insertar_historial(sb, liquidacion_id: str, estado: str, usuario: str, observacion: str = "") -> None:
    with contextlib.suppress(Exception):
        sb.table(TABLA_LIQ_HISTORIAL).insert({
            "liquidacion_id": liquidacion_id, "estado": estado,
            "usuario": usuario, "observacion": observacion or None,
        }).execute()


def historial_estados(liquidacion_id: str) -> list[dict]:
    """Timeline de cambios de estado de una liquidación (más reciente
    primero) -- para la sección "HISTORIAL DE ESTADOS" del panel de
    detalle (paridad con Gestión de Liquidaciones)."""
    sb = supabase_client.get_client()
    return (
        sb.table(TABLA_LIQ_HISTORIAL).select("*")
        .eq("liquidacion_id", liquidacion_id).order("created_at", desc=True)
        .execute().data or []
    )


def guardar_seguimiento(
    liquidacion_id: str, campos: dict, *, usuario: str, roles: set[str],
) -> tuple[bool, str]:
    """Guarda color/seguimiento de firma-cobro/observaciones -- paridad con
    el botón "💾 Guardar todo (color, seguimiento y observaciones)" del
    panel de detalle. Independiente del estado -- se puede guardar en
    cualquier momento, incluso sobre una liquidación ya pagada. Ignora
    cualquier clave de `campos` que no esté en `_CAMPOS_SEGUIMIENTO`."""
    datos = {k: v for k, v in campos.items() if k in _CAMPOS_SEGUIMIENTO}
    if not datos:
        return False, "No hay campos válidos para guardar."
    registro, _c = obtener_liquidacion(liquidacion_id)
    if registro is None:
        return False, "No existe esa liquidación."
    from core.audit.writer import audit_scope

    with audit_scope(
        "liquidaciones", "guardar_seguimiento", usuario=usuario, roles=roles,
        target_table=TABLA_LIQ, target_key=liquidacion_id, after=datos,
    ):
        sb = supabase_client.get_client()
        sb.table(TABLA_LIQ).update({**datos, "updated_by": usuario}).eq("id", liquidacion_id).execute()
    return True, ""


def autorizar(liquidacion_id: str, *, autorizado_por: str, usuario: str, roles: set[str]) -> tuple[bool, str]:
    """generada -> aprobado. Paridad con el diálogo "Confirmar autorización"
    de Gestión de Liquidaciones."""
    autorizado_por = (autorizado_por or "").strip()
    if not autorizado_por:
        return False, "Ingrese el nombre de quien autoriza."
    registro, _c = obtener_liquidacion(liquidacion_id)
    if registro is None:
        return False, "No existe esa liquidación."
    estado_actual = registro.get("estado", "")
    if "aprobado" not in TRANSICIONES.get(estado_actual, ()):
        return False, f"No se puede autorizar una liquidación en estado '{estado_actual}'."
    from core.audit.writer import audit_scope

    with audit_scope(
        "liquidaciones", "autorizar", usuario=usuario, roles=roles,
        target_table=TABLA_LIQ, target_key=liquidacion_id,
        antes={"estado": estado_actual}, after={"estado": "aprobado"},
    ):
        sb = supabase_client.get_client()
        sb.table(TABLA_LIQ).update({
            "estado": "aprobado",
            "aprobado_por_rrhh": autorizado_por,
            "fecha_aprobacion_rrhh": dt.datetime.now().isoformat(),
            "updated_by": usuario,
        }).eq("id", liquidacion_id).execute()
        _insertar_historial(sb, liquidacion_id, "aprobado", usuario, f"Autorizado por {autorizado_por}")
    return True, ""


def marcar_cheque_listo(
    liquidacion_id: str, *, forma_pago: str, comprobante_pago: str = "", usuario: str, roles: set[str],
) -> tuple[bool, str]:
    """registrado_mrl -> cheque_listo. Paridad con el diálogo "Marcar Cheque
    Listo". `comprobante_pago` es opcional -- en el `.pyw`, cuando se marca
    un LOTE de varias liquidaciones a la vez, el número de cheque se deja
    en blanco (cada una tiene el suyo) y se completa después, una por una.
    Este archivo no tiene todavía una forma de actualizar solo
    `comprobante_pago` sin volver a pasar por esta función (que exige venir
    de 'registrado_mrl') -- si hace falta completarlo después de que la
    liquidación ya avanzó de estado, agregar una función aparte cuando se
    necesite (no inventada acá para no adelantarse sin caso de uso real)."""
    forma_pago = (forma_pago or "").strip()
    if not forma_pago:
        return False, "Seleccione la forma de pago."
    registro, _c = obtener_liquidacion(liquidacion_id)
    if registro is None:
        return False, "No existe esa liquidación."
    estado_actual = registro.get("estado", "")
    if "cheque_listo" not in TRANSICIONES.get(estado_actual, ()):
        return False, f"No se puede marcar 'Cheque Listo' desde el estado '{estado_actual}'."
    datos = {"estado": "cheque_listo", "forma_pago": forma_pago, "updated_by": usuario}
    comprobante_pago = (comprobante_pago or "").strip()
    if comprobante_pago:
        datos["comprobante_pago"] = comprobante_pago
    from core.audit.writer import audit_scope

    with audit_scope(
        "liquidaciones", "marcar_cheque_listo", usuario=usuario, roles=roles,
        target_table=TABLA_LIQ, target_key=liquidacion_id,
        antes={"estado": estado_actual}, after=datos,
    ):
        sb = supabase_client.get_client()
        sb.table(TABLA_LIQ).update(datos).eq("id", liquidacion_id).execute()
        _insertar_historial(sb, liquidacion_id, "cheque_listo", usuario,
                             f"{forma_pago} · {comprobante_pago or 'pendiente'}")
    return True, ""


def _marcar_fecha_pago(
    liquidacion_id: str, estado_final: str, *, fecha: str, usuario: str, roles: set[str],
) -> tuple[bool, str]:
    registro, _c = obtener_liquidacion(liquidacion_id)
    if registro is None:
        return False, "No existe esa liquidación."
    estado_actual = registro.get("estado", "")
    if estado_final not in TRANSICIONES.get(estado_actual, ()):
        return False, f"No se puede marcar '{estado_final}' desde el estado '{estado_actual}'."
    from core.audit.writer import audit_scope

    with audit_scope(
        "liquidaciones", f"marcar_{estado_final}", usuario=usuario, roles=roles,
        target_table=TABLA_LIQ, target_key=liquidacion_id,
        antes={"estado": estado_actual}, after={"estado": estado_final, "fecha_pago": fecha},
    ):
        sb = supabase_client.get_client()
        sb.table(TABLA_LIQ).update({
            "estado": estado_final, "fecha_pago": fecha, "updated_by": usuario,
        }).eq("id", liquidacion_id).execute()
        _insertar_historial(sb, liquidacion_id, estado_final, usuario)
    return True, ""


def marcar_pagada(liquidacion_id: str, *, fecha: str, usuario: str, roles: set[str]) -> tuple[bool, str]:
    """cheque_listo -> pagado. Paridad con el botón "Pagada" del diálogo
    "Marcar como Pagada o Consignada" (misma columna `fecha_pago` que
    `marcar_consignada`)."""
    return _marcar_fecha_pago(liquidacion_id, "pagado", fecha=fecha, usuario=usuario, roles=roles)


def marcar_consignada(liquidacion_id: str, *, fecha: str, usuario: str, roles: set[str]) -> tuple[bool, str]:
    """cheque_listo -> consignada. Paridad con el botón "Consignada" del
    mismo diálogo que `marcar_pagada`."""
    return _marcar_fecha_pago(liquidacion_id, "consignada", fecha=fecha, usuario=usuario, roles=roles)


def avanzar_estado(
    liquidacion_id: str, nuevo_estado: str, *, responsable: str, usuario: str, roles: set[str],
) -> tuple[bool, str]:
    """Transición genérica que solo pide "quién hizo la acción" -- paridad
    con `_abrir_dialogo_avance` del `.pyw` (usada hoy para
    aprobado->registrado_mrl "Registrar en MRL" y
    pagado/consignada->legalizada_mrl "Legalizar en MRL"). El responsable
    se ANEXA a `observaciones` (nunca la pisa), igual que el original."""
    responsable = (responsable or "").strip()
    if not responsable:
        return False, "Ingrese el nombre del responsable."
    registro, _c = obtener_liquidacion(liquidacion_id)
    if registro is None:
        return False, "No existe esa liquidación."
    estado_actual = registro.get("estado", "")
    if nuevo_estado not in TRANSICIONES.get(estado_actual, ()):
        return False, f"No se puede pasar de '{estado_actual}' a '{nuevo_estado}'."
    nota = f"{nuevo_estado} por {responsable} el {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}."
    obs_previa = (registro.get("observaciones") or "").strip()
    obs_nueva = f"{obs_previa}\n{nota}".strip() if obs_previa else nota
    from core.audit.writer import audit_scope

    with audit_scope(
        "liquidaciones", "avanzar_estado", usuario=usuario, roles=roles,
        target_table=TABLA_LIQ, target_key=liquidacion_id,
        antes={"estado": estado_actual}, after={"estado": nuevo_estado},
    ):
        sb = supabase_client.get_client()
        sb.table(TABLA_LIQ).update({
            "estado": nuevo_estado, "observaciones": obs_nueva, "updated_by": usuario,
        }).eq("id", liquidacion_id).execute()
        _insertar_historial(sb, liquidacion_id, nuevo_estado, usuario, f"Por {responsable}")
    return True, ""


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
    # Agregados 2026-09 para Editar en cuadrícula / Cuadre masivo (ver
    # docs/modulos/liquidaciones_cuadricula_UI.md) -- ninguno lo calcula
    # procesar_empleado hoy, son campos manuales del Editor/cuadrícula.
    # "DESCUENTOS_REGISTRADOS" (plural) es la misma clave que ya usa
    # procesar_empleado para descuentos_pendientes (ver
    # descuentos_pendientes_de) -- no una clave nueva.
    ("DESCUENTO_REGISTRADO", "Descuentos registrados (pendientes)", "descuento", "DESCUENTOS_REGISTRADOS"),
    # Ajuste de cuadre contra el MRL -- admite negativo a propósito, se
    # muestra del lado de "ingreso" (puede restar) igual que el .pyw
    # (generacion_bot_mrl.py: OTROS_INGRESOS = INDEM_DESPIDO + AJUSTE_CUADRE).
    ("AJUSTE_CUADRE", "Ajuste de Cuadre (MRL)", "ingreso", "AJUSTE_CUADRE"),
    ("OTRAS_INDEM", "Otras indemnizaciones", "ingreso", "OTRAS_INDEM"),
    ("VALOR_NO_CONSIDERADO", "Por cualquier valor no considerado", "ingreso", "VALOR_NO_CONSIDERADO"),
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


def previsualizar_conceptos(liq: Liquidacion) -> list[dict]:
    """Desglose concepto/tipo/valor de una `Liquidacion` calculada, para el
    panel "VISTA PREVIA" del modo Individual (sin guardar nada)."""
    return _construir_conceptos(liq)


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
                with contextlib.suppress(Exception):
                    sb.table(TABLA_LIQ_PERIODOS).delete().eq(
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
            # Desglose mensual de la Décima Tercera ACTUAL -> el bot MRL lo lee.
            if liq.detalle_decimo_tercera:
                with contextlib.suppress(Exception):
                    sb.table(TABLA_LIQ_PERIODOS).insert({
                        "liquidacion_id": liquidacion_id,
                        "tipo": "DEC_TERCERA",
                        "meses": [
                            {"label": d.label, "valor": d.valor}
                            for d in liq.detalle_decimo_tercera
                        ],
                    }).execute()
            with contextlib.suppress(Exception):
                sb.table(TABLA_LIQ_HISTORIAL).insert({
                    "liquidacion_id": liquidacion_id, "estado": estado,
                    "usuario": usuario, "observacion": None,
                }).execute()
            return True, liquidacion_id
        except Exception as e:  # noqa: BLE001
            return False, str(e)


def resumen_liquidaciones() -> dict[str, int]:
    """Cuenta de liquidaciones guardadas por estado, para el panel "Resumen de
    liquidaciones guardadas" de la pantalla principal (paridad con
    `_actualizar_resumen_liquidaciones` del `.pyw`)."""
    sb = supabase_client.get_client()
    filas = sb.table(TABLA_LIQ).select("estado").execute().data or []
    conteo = dict.fromkeys(ESTADOS_LIQUIDACION, 0)
    for f in filas:
        e = f.get("estado")
        if e in conteo:
            conteo[e] += 1
    return conteo


def listar_liquidaciones(
    *, texto: str = "", estado: str = "", tipo: str = "", lote: str = "",
    desde: str = "", hasta: str = "", orden: str = "-created_at", limite: int = 200,
) -> list[dict]:
    """Lista de `liquidaciones` para el Editor/Gestión — más recientes
    primero por defecto.

    `lote`: filtra por `codigo_lote` exacto (selector "Lote:" de Gestión de
    Liquidaciones). `desde`/`hasta`: rango de `fecha_salida` (ISO
    aaaa-mm-dd), paridad con el filtro de fechas "Desde"/"Hasta". `orden`:
    columna a ordenar, con prefijo "-" para descendente (default
    "-created_at", más recientes primero); columnas típicas:
    "fecha_salida", "total_liquido", "empleado_apellidos"."""
    sb = supabase_client.get_client()
    q = sb.table(TABLA_LIQ).select(
        "id,empleado_codigo,empleado_cedula,empleado_nombres,empleado_apellidos,"
        "cargo,fecha_salida,tipo_liquidacion,estado,total_liquido,created_at,"
        "codigo_lote,forma_pago,comprobante_pago,fecha_pago,aprobado_por_rrhh,"
        "color_etiqueta"
    )
    if estado:
        q = q.eq("estado", estado)
    if tipo:
        q = q.eq("tipo_liquidacion", tipo)
    if lote:
        q = q.eq("codigo_lote", lote)
    if desde:
        q = q.gte("fecha_salida", desde)
    if hasta:
        q = q.lte("fecha_salida", hasta)
    if texto.strip():
        t = texto.strip()
        if t.isdigit() or normalizar_cedula(t) == t.zfill(10):
            q = q.or_(f"empleado_cedula.eq.{normalizar_cedula(t)},empleado_codigo.eq.{t},codigo_lote.eq.{t}")
        else:
            q = q.or_(f"empleado_apellidos.ilike.%{t}%,empleado_nombres.ilike.%{t}%")
    campo_orden = orden.lstrip("-")
    filas = q.order(campo_orden, desc=orden.startswith("-")).limit(limite).execute().data or []
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
        _insertar_historial(sb, liquidacion_id, estado, usuario, observacion)


_TIPO_POR_CODIGO: dict[str, str] = {cod: tipo for cod, _n, tipo, _c in _CONCEPTOS_DETALLE}
_NOMBRE_POR_CODIGO: dict[str, str] = {cod: nom for cod, nom, _t, _c in _CONCEPTOS_DETALLE}


def _totales_desde_valores(valores: dict[str, float]) -> dict[str, float]:
    """Recalcula los totales y columnas derivadas de `liquidaciones` a partir de
    `{concepto_codigo: valor}`. Mismas fórmulas que `_mapear_registro`."""
    def _s(*cods: str) -> float:
        return round(sum(valores.get(x, 0.0) for x in cods), 2)

    total_ing = round(sum(v for k, v in valores.items() if _TIPO_POR_CODIGO.get(k) == "ingreso"), 2)
    total_dsc = round(sum(v for k, v in valores.items() if _TIPO_POR_CODIGO.get(k) == "descuento"), 2)
    return {
        "total_ingresos": total_ing,
        "total_descuentos": total_dsc,
        "total_liquido": round(total_ing - total_dsc, 2),
        "decimo_tercero": _s("DEC_TERCERA_ANT", "DEC_TERCERA_ACT"),
        "decimo_cuarto": _s("DEC_CUARTA_ANT", "DEC_CUARTA_ACT"),
        "horas_extras": _s("SOBT_25", "SOBT_50", "SOBT_100"),
        "vacaciones_pendientes": _s("VACACIONES"),
        "fondo_reserva": _s("FONDO_RESERVA"),
        "bonificacion_desahucio": _s("DESAHUCIO"),
        "otros_ingresos": _s("REEMBOLSOS", "MANIOBRAS", "BONIFICACION", "MOVILIZACION"),
        "anticipos": _s("ANTICIPO_SUELDO", "ANTICIPOS_OTROS", "ANTICIPO_L_DESAHUCIO"),
        "prestamos": _s("PREST_QUIROGRAFARIO", "PREST_COMPANIA", "PREST_HIPOTECARIO"),
        "multas": _s("MULTAS"),
        "otros_descuentos": _s("PENSION_ALIMENTICIA", "IESS_CONYUGE", "IMPUESTO_RENTA", "IESS"),
    }


def editar_valores_liquidacion(
    liquidacion_id: str, cambios: dict[str, float], *, usuario: str, roles: set[str],
) -> tuple[bool, str]:
    """Corrige a mano los valores de conceptos de una liquidación guardada
    (el Editor del `.pyw`). `cambios`: `concepto_codigo -> nuevo valor_total`
    (0 quita el concepto). Recalcula los totales y las columnas derivadas de
    `liquidaciones`. No toca una liquidación en estado 'pagado'."""
    from core.audit.writer import audit_scope

    registro, conceptos = obtener_liquidacion(liquidacion_id)
    if registro is None:
        return False, "No existe esa liquidación."
    if registro.get("estado") == "pagado":
        return False, "No se puede editar una liquidación ya marcada como pagada."

    cambios_norm = {
        str(k): round(float(v), 2) for k, v in cambios.items() if str(k) in _TIPO_POR_CODIGO
    }
    if not cambios_norm:
        return False, "No hay cambios válidos."

    valores: dict[str, float] = {str(c["concepto_codigo"]): float(c.get("valor_total") or 0) for c in conceptos}
    valores.update(cambios_norm)
    derivados = _totales_desde_valores(valores)

    with audit_scope(
        "liquidaciones", "editar_valores", usuario=usuario, roles=roles,
        target_table=TABLA_LIQ, target_key=liquidacion_id,
        antes={"total_liquido": registro.get("total_liquido")},
        after={"total_liquido": derivados["total_liquido"], "cambios": cambios_norm},
    ):
        sb = supabase_client.get_client()
        for cod, val in cambios_norm.items():
            if val == 0:
                sb.table(TABLA_LIQ_DETALLE).delete().eq("liquidacion_id", liquidacion_id).eq(
                    "concepto_codigo", cod).execute()
                continue
            upd = sb.table(TABLA_LIQ_DETALLE).update({"valor_total": val}).eq(
                "liquidacion_id", liquidacion_id).eq("concepto_codigo", cod).execute()
            if not (upd.data or []):
                sb.table(TABLA_LIQ_DETALLE).insert({
                    "liquidacion_id": liquidacion_id, "concepto_codigo": cod,
                    "concepto_nombre": _NOMBRE_POR_CODIGO.get(cod, cod),
                    "concepto_tipo": _TIPO_POR_CODIGO[cod], "valor_total": val,
                    "orden": len(conceptos),
                }).execute()
        sb.table(TABLA_LIQ).update({**derivados, "updated_by": usuario}).eq("id", liquidacion_id).execute()
        with contextlib.suppress(Exception):
            sb.table(TABLA_LIQ_HISTORIAL).insert({
                "liquidacion_id": liquidacion_id, "estado": registro.get("estado"),
                "usuario": usuario,
                "observacion": "Edición manual de valores: " + ", ".join(sorted(cambios_norm)),
            }).execute()
    return True, ""


def eliminar_liquidacion(
    liquidacion_id: str, motivo: str, *, usuario: str, roles: set[str],
) -> tuple[bool, str]:
    """Elimina una liquidación guardando antes un snapshot completo en
    `liquidaciones_eliminadas_historial` (mismo criterio que
    `eliminar_liquidacion_con_historial` del legado: no elimina si el estado
    ya es 'pagado'). `liquidaciones_detalle` cae solo por ON DELETE CASCADE."""
    from core.audit.writer import audit_scope

    sb = supabase_client.get_client()
    registro, conceptos = obtener_liquidacion(liquidacion_id)
    if registro is None:
        return False, "No existe esa liquidación."
    if registro.get("estado") == "pagado":
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


def _aplicar_delta_a_detalle(
    sb, liquidacion_id: str, concepto_codigo: str, delta: float,
    conceptos: list[dict], usuario: str,
) -> float:
    """SUMA `delta` al `valor_total` de un concepto en `liquidaciones_detalle`
    (crea la fila si no existía, la borra si el resultado da 0) y
    recalcula/guarda los totales derivados en `liquidaciones`. Devuelve el
    valor nuevo del concepto. Compartido por `ajustar_concepto` (inserta un
    ajuste nuevo) y `editar_ajuste`/`eliminar_ajuste` (aplican un delta
    compensatorio sobre un ajuste YA existente) -- la parte de escritura en
    `liquidaciones_detalle`/`liquidaciones` es idéntica en los tres casos,
    solo cambia qué pasa con la fila de `liquidaciones_ajustes_concepto`."""
    valores: dict[str, float] = {str(c["concepto_codigo"]): float(c.get("valor_total") or 0) for c in conceptos}
    valor_anterior = valores.get(concepto_codigo, 0.0)
    valor_nuevo = round(valor_anterior + delta, 2)
    valores[concepto_codigo] = valor_nuevo
    derivados = _totales_desde_valores(valores)

    if valor_nuevo == 0:
        sb.table(TABLA_LIQ_DETALLE).delete().eq("liquidacion_id", liquidacion_id).eq(
            "concepto_codigo", concepto_codigo).execute()
    else:
        upd = sb.table(TABLA_LIQ_DETALLE).update({"valor_total": valor_nuevo}).eq(
            "liquidacion_id", liquidacion_id).eq("concepto_codigo", concepto_codigo).execute()
        if not (upd.data or []):
            sb.table(TABLA_LIQ_DETALLE).insert({
                "liquidacion_id": liquidacion_id, "concepto_codigo": concepto_codigo,
                "concepto_nombre": _NOMBRE_POR_CODIGO.get(concepto_codigo, concepto_codigo),
                "concepto_tipo": _TIPO_POR_CODIGO[concepto_codigo], "valor_total": valor_nuevo,
                "orden": len(conceptos),
            }).execute()
    sb.table(TABLA_LIQ).update({**derivados, "updated_by": usuario}).eq("id", liquidacion_id).execute()
    return valor_nuevo


def ajustar_concepto(
    liquidacion_id: str, concepto_codigo: str, delta: float, *,
    motivo: str = "", usuario: str, roles: set[str],
) -> tuple[bool, str]:
    """SUMA `delta` (admite negativo) al valor actual de un concepto de una
    liquidación ya guardada -- a diferencia de `editar_valores_liquidacion`
    (que REEMPLAZA el valor), esto es incremental: paridad con el "+" del
    Editor de Liquidaciones (`_abrir_dialogo_ajuste_concepto`) y con Editar
    en cuadrícula/Cuadre masivo (ver docs/modulos/liquidaciones_cuadricula_UI.md).

    `motivo` es OPCIONAL -- verificado contra el `.pyw`: el diálogo "+"
    individual del Editor lo pide como "Motivo (opcional)" (a diferencia
    de Editar en cuadrícula/Cuadre masivo, donde SÍ es obligatorio a nivel
    de esas pantallas -- eso lo exige la UI que llama, no esta función).

    CORREGIDO (2026-09): el orden de escritura importa. El `.pyw` inserta
    PRIMERO el registro en `liquidaciones_ajustes_concepto` y verifica
    `resp.data` (memoria de este proyecto:
    "un insert puede no lanzar excepción y aun así no guardar nada por
    RLS") -- si eso falla, NO toca el valor mostrado ni el total. La
    primera versión de esta función hacía lo opuesto (actualizaba el valor
    primero, insertaba el ajuste con las excepciones suprimidas después) --
    si el insert del ajuste fallaba en silencio, el monto quedaba sumado
    igual pero sin ningún rastro de motivo/quién/cuándo. Se invirtió el
    orden."""
    concepto_codigo = str(concepto_codigo)
    if concepto_codigo not in _TIPO_POR_CODIGO:
        return False, f"Concepto desconocido: {concepto_codigo}"
    try:
        delta = round(float(delta), 2)
    except (TypeError, ValueError):
        return False, "Ingrese un monto numérico."
    if delta == 0:
        return False, "El monto a agregar no puede ser 0."
    motivo = (motivo or "").strip()
    registro, conceptos = obtener_liquidacion(liquidacion_id)
    if registro is None:
        return False, "No existe esa liquidación."
    if registro.get("estado") == "pagado":
        return False, "No se puede ajustar una liquidación ya marcada como pagada."

    valor_anterior = next(
        (float(c.get("valor_total") or 0) for c in conceptos if str(c["concepto_codigo"]) == concepto_codigo), 0.0)

    from core.audit.writer import audit_scope

    with audit_scope(
        "liquidaciones", "ajustar_concepto", usuario=usuario, roles=roles,
        target_table=TABLA_LIQ, target_key=liquidacion_id,
        antes={concepto_codigo: valor_anterior},
        after={concepto_codigo: round(valor_anterior + delta, 2), "delta": delta, "motivo": motivo},
    ):
        sb = supabase_client.get_client()
        try:
            resp = sb.table(TABLA_LIQ_AJUSTES).insert({
                "liquidacion_id": liquidacion_id, "concepto_codigo": concepto_codigo,
                "concepto_nombre": _NOMBRE_POR_CODIGO.get(concepto_codigo, concepto_codigo),
                "monto": delta, "motivo": motivo or None, "usuario": usuario,
            }).execute()
        except Exception as e:  # noqa: BLE001
            return False, f"No se pudo registrar el ajuste: {e}"
        if not (resp.data or []):
            return False, (
                "No se pudo registrar el ajuste: el sistema no confirmó el guardado. "
                "El monto NO se sumó -- intente de nuevo."
            )
        _aplicar_delta_a_detalle(sb, liquidacion_id, concepto_codigo, delta, conceptos, usuario)
    return True, ""


def listar_ajustes_concepto(liquidacion_id: str, concepto_codigo: str | None = None) -> list[dict]:
    """Ajustes "+" ya registrados de una liquidación (todos, o solo los de
    UN concepto si se pasa `concepto_codigo`) -- para el indicador
    clickeable debajo de cada campo con ajustes en el Editor de
    Liquidaciones. Más reciente primero. Columna de fecha real: `fecha`
    (NO `created_at` -- confirmado leyendo filas reales de
    `liquidaciones_ajustes_concepto` en producción)."""
    sb = supabase_client.get_client()
    q = sb.table(TABLA_LIQ_AJUSTES).select("*").eq("liquidacion_id", liquidacion_id)
    if concepto_codigo:
        q = q.eq("concepto_codigo", str(concepto_codigo))
    return q.order("fecha", desc=True).execute().data or []


def _ajuste_por_id(ajuste_id: str) -> dict | None:
    sb = supabase_client.get_client()
    filas = sb.table(TABLA_LIQ_AJUSTES).select("*").eq("id", ajuste_id).limit(1).execute().data or []
    return filas[0] if filas else None


def editar_ajuste(
    ajuste_id: str, *, nuevo_monto: float, motivo: str = "", usuario: str, roles: set[str],
) -> tuple[bool, str]:
    """Corrige el monto de un ajuste "+" YA REGISTRADO -- modelo de DELTA
    COMPENSATORIO: aplica `nuevo_monto - monto_viejo` al concepto en
    `liquidaciones_detalle` (para quedar consistente pase lo que pase con
    el valor del concepto entre medio, ej. si alguien más lo tocó con otro
    ajuste) y actualiza la fila del ajuste con el monto/motivo nuevos.
    Bloquea si la liquidación ya está en estado 'pagado'."""
    try:
        nuevo_monto = round(float(nuevo_monto), 2)
    except (TypeError, ValueError):
        return False, "Ingrese un monto numérico."
    ajuste = _ajuste_por_id(ajuste_id)
    if ajuste is None:
        return False, "No existe ese ajuste."
    liquidacion_id = str(ajuste["liquidacion_id"])
    concepto_codigo = str(ajuste["concepto_codigo"])
    monto_viejo = float(ajuste.get("monto") or 0)
    delta_compensatorio = round(nuevo_monto - monto_viejo, 2)

    registro, conceptos = obtener_liquidacion(liquidacion_id)
    if registro is None:
        return False, "No existe esa liquidación."
    if registro.get("estado") == "pagado":
        return False, "No se puede editar un ajuste de una liquidación ya marcada como pagada."

    motivo = (motivo or "").strip()
    from core.audit.writer import audit_scope

    with audit_scope(
        "liquidaciones", "editar_ajuste", usuario=usuario, roles=roles,
        target_table=TABLA_LIQ_AJUSTES, target_key=ajuste_id,
        antes={"monto": monto_viejo}, after={"monto": nuevo_monto, "motivo": motivo},
    ):
        sb = supabase_client.get_client()
        if delta_compensatorio != 0:
            _aplicar_delta_a_detalle(sb, liquidacion_id, concepto_codigo, delta_compensatorio, conceptos, usuario)
        sb.table(TABLA_LIQ_AJUSTES).update({
            "monto": nuevo_monto, "motivo": motivo or None,
        }).eq("id", ajuste_id).execute()
    return True, ""


def eliminar_ajuste(ajuste_id: str, *, usuario: str, roles: set[str]) -> tuple[bool, str]:
    """Elimina un ajuste "+" YA REGISTRADO -- aplica `delta = -monto` al
    concepto en `liquidaciones_detalle` (mismo modelo de delta
    compensatorio que `editar_ajuste`) y borra la fila del ajuste. Bloquea
    si la liquidación ya está en estado 'pagado'."""
    ajuste = _ajuste_por_id(ajuste_id)
    if ajuste is None:
        return False, "No existe ese ajuste."
    liquidacion_id = str(ajuste["liquidacion_id"])
    concepto_codigo = str(ajuste["concepto_codigo"])
    monto = float(ajuste.get("monto") or 0)

    registro, conceptos = obtener_liquidacion(liquidacion_id)
    if registro is None:
        return False, "No existe esa liquidación."
    if registro.get("estado") == "pagado":
        return False, "No se puede eliminar un ajuste de una liquidación ya marcada como pagada."

    from core.audit.writer import audit_scope

    with audit_scope(
        "liquidaciones", "eliminar_ajuste", usuario=usuario, roles=roles,
        target_table=TABLA_LIQ_AJUSTES, target_key=ajuste_id,
        antes={"monto": monto},
    ):
        sb = supabase_client.get_client()
        if monto != 0:
            _aplicar_delta_a_detalle(sb, liquidacion_id, concepto_codigo, -monto, conceptos, usuario)
        sb.table(TABLA_LIQ_AJUSTES).delete().eq("id", ajuste_id).execute()
    return True, ""


def cuadre_masivo(texto: str, *, usuario: str, roles: set[str]) -> tuple[int, list[str]]:
    """Carga masiva de "Ajuste de Cuadre (MRL)" por texto libre -- paridad
    con `_abrir_carga_masiva_ajuste_cuadre`. Una línea por liquidación:
    `cedula, fecha_salida (dd/mm/aaaa o aaaa-mm-dd), monto`. El monto se
    SUMA al ajuste de cuadre existente (no lo reemplaza), admite negativo
    -- reutiliza `ajustar_concepto` sobre el concepto `AJUSTE_CUADRE` con
    motivo fijo "Cuadre masivo" (el `.pyw` deja elegir un motivo por carga,
    no por línea; acá se simplifica a un motivo fijo -- si hace falta
    elegirlo, agregar un parámetro `motivo` a esta función).

    Retorna `(cantidad_aplicada, errores)` -- una línea con error no
    bloquea el resto del lote."""
    errores: list[str] = []
    aplicadas = 0
    for num_linea, linea in enumerate(texto.splitlines(), start=1):
        linea = linea.strip()
        if not linea:
            continue
        partes = [p.strip() for p in linea.split(",")]
        if len(partes) < 3:
            errores.append(f"Línea {num_linea}: faltan datos (cédula, fecha de salida, monto) -> '{linea}'.")
            continue
        cedula_raw, fecha_raw, monto_raw = partes[0], partes[1], partes[2]
        fecha_sal = _f(fecha_raw)
        if not cedula_raw or fecha_sal is None:
            errores.append(f"Línea {num_linea}: cédula o fecha inválida (use dd/mm/aaaa) -> '{linea}'.")
            continue
        try:
            monto = round(float(monto_raw.replace("$", "").replace(",", ".")), 2)
        except ValueError:
            errores.append(f"Línea {num_linea}: monto inválido -> '{monto_raw}'.")
            continue
        ced = normalizar_cedula(cedula_raw)
        sb = supabase_client.get_client()
        filas = (
            sb.table(TABLA_LIQ).select("id").eq("empleado_cedula", ced)
            .eq("fecha_salida", fecha_sal.isoformat()).limit(1).execute().data or []
        )
        if not filas:
            errores.append(
                f"Línea {num_linea}: no se encontró liquidación para {ced} con salida {fecha_sal.isoformat()}.")
            continue
        ok, err = ajustar_concepto(
            filas[0]["id"], "AJUSTE_CUADRE", monto,
            motivo="Cuadre masivo", usuario=usuario, roles=roles,
        )
        if ok:
            aplicadas += 1
        else:
            errores.append(f"Línea {num_linea} ({ced}): {err}")
    return aplicadas, errores


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


def recalcular_liquidacion(
    liquidacion_id: str, fuente: str, cfg: ConfigLiquidacion, *,
    cedula: str = "", fecha_salida: str = "", motivo: str = "",
) -> Liquidacion:
    """Vuelve a correr TODO el cálculo desde cero contra los datos actuales
    de nómina -- paridad con "🔄 Recalcular Liquidación" del Editor de
    Liquidaciones. A diferencia de `reconstruir_liquidacion` (arma una
    `Liquidacion` aproximada a partir de lo ya guardado, sin tocar
    RPEMPLEA/movimientos), esto es un `procesar_empleado` fresco -- mismo
    caso real que motivó el botón en el `.pyw`: un valor calculado se ve
    mal (ej. vacaciones infladas por un período con goce parcial mal
    sumado) y hace falta recalcular en vez de corregir a mano campo por
    campo.

    NO guarda nada -- devuelve la `Liquidacion` recién calculada para que
    el llamador la muestre y decida si guardarla (`guardar_liquidacion(...,
    liquidacion_id_existente=liquidacion_id)`) después de revisarla.

    `cedula`/`fecha_salida`/`motivo`: si se omiten, se toman del registro
    YA GUARDADO. El `.pyw` real recalcula contra lo que esté escrito en el
    FORMULARIO en ese momento (que puede diferir de lo guardado si el
    usuario editó la fecha de salida antes de recalcular) -- pasar estos
    overrides explícitos para reproducir ese caso.

    Mismos defaults fijos que usa el botón del `.pyw` (no hay control
    propio para esto en el Editor): `incluir_dec13_anterior=False`,
    `incluir_dec14_anterior=False`.
    """
    registro, _c = obtener_liquidacion(liquidacion_id)
    if registro is None:
        return Liquidacion(
            "", "", "", "", "", "", 0.0, "", "", "", 0, error="No existe esa liquidación.")
    ced = cedula or str(registro.get("empleado_cedula") or "")
    fsal = fecha_salida or str(registro.get("fecha_salida") or "")
    mot = motivo or str(registro.get("motivo") or "")
    return procesar_empleado(
        ced, fsal, mot, fuente, cfg,
        incluir_dec13_anterior=False, incluir_dec14_anterior=False,
    )
