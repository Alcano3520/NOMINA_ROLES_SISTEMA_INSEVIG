"""Vacaciones — Art. 69/71/76 CT Ecuador (períodos, cálculo, registro GOCE/PAGO).

Porta `VACACIONES_SISTEMA_INSEVIG/calculos.py`, `model.py`, `supabase_client.py`
(funciones `vac_*`/`rpemplea`) y la fórmula real de pago de `app.py`
(`_recalcular_totales`/`_registrar_pagada`). El `.pyw` original NO se modifica —
sigue siendo la fuente de verdad de referencia; este módulo es la migración a
`core/`, no un fork.

Datos en **Supabase** (igual que `core/repos/bitacora.py`): este módulo nunca
escribe a SQL Server — a diferencia de otros módulos de este repo, vacaciones
no tiene equivalente en RPEMPLEA/RPEMPOBSERV/RPINGDES, es 100% propio
(`vac_registros`/`vac_calculo`/`vac_config`/`vac_codigos_nomina`). Ver nota en
`docs/CONTRATOS.md` "Reglas de datos" — pendiente de aclarar ahí que esta regla
de "escrituras siempre SQL Server" no aplica a los módulos que, como bitácora
y vacaciones, no tienen tabla nomina equivalente.

Tablas Supabase usadas (mismo proyecto que el resto de `core/repos/*`):
- `rpemplea`, `rpingdesres`, `rphistor_temp`, `dbtablas` — lectura (nómina/empleados).
- `vac_registros` — registros GOCE y PAGO. **No renombrar/cambiar semántica de
  columnas sin avisar**: `core/repos/liquidaciones.py` ya lee `periodo`,
  `estado_doc`, `valor_vacaciones`, `dias_tomados` de esta tabla para no
  volver a pagar un período ya gozado/pagado.
- `vac_calculo` — desglose mensual (12 meses) que sostiene el cálculo de pago.
- `vac_config` — parámetros globales (empresa, firmante, divisores).
- `vac_codigos_nomina` — códigos CLASE que forman la base de cálculo.
- `vac_auditoria` — historial de cambios (el `.pyw` original NO la usa, audita
  solo en SQLite local; aquí se cablea a `core.audit` como hace bitácora).

Diferencia de comportamiento detectada (reportada, NO corregida en silencio):
`calculos.calcular_vacaciones_pagadas()` del `.pyw` es código MUERTO (solo lo
usa `test_sistema.py`) con una fórmula distinta e incompatible con la que de
verdad usa producción (`app.py::_recalcular_totales`/`_registrar_pagada`):
código muerto → `dias_adicionales` se paga como `(sueldo_mensual/30) *
dias_adicionales` (un valor aparte, sumado); producción → los días
adicionales se pliegan dentro de `dias_a_pagar` (15 + adicionales − gozados) y
se pagan todos al mismo valor/día (`total_periodo/24/15`). Este módulo porta
la fórmula de PRODUCCIÓN (`calcular_pago`), no la del código muerto.
"""

from __future__ import annotations

import calendar
import contextlib
import datetime as dt
import logging
from datetime import date, datetime

from postgrest.types import CountMethod

from core.audit.writer import registrar_evento
from core.db import supabase_client
from core.utils import a_float, a_int, normalizar_cedula

log = logging.getLogger(__name__)

# ─── Constantes ──────────────────────────────────────────────────────────────

# Códigos CLASE que forman la base de cálculo (igual que IESS / Fondo Reserva).
# Porta `calculos.CODIGOS_BASE`. Fallback si `vac_codigos_nomina` no responde.
CODIGOS_BASE_DEFAULT = frozenset({
    100, 102, 104, 105, 107, 108, 110, 111, 113, 114, 115,
    120, 126, 199, 200, 202, 204, 205, 217, 218, 219, 250,
})

ESTADOS_DOC = ("borrador", "pendiente", "completado")
TIPOS = ("gozada", "pagada")

_VAC_COLS = (
    "id,cedula,tipo,periodo,anio_registro,estado_doc,observaciones,source,"
    "cod_acta,created_at,updated_at,"
    "fecha_comprobante,desde,hasta,dias_tomados,referencia,firmado,"
    "lo_cubrio_agente,fecha_firma,"
    "fecha_pago,valor_vacaciones,banco,no_cheque,forma_pago,cta_cte_no,"
    "total_periodo,vacaciones_calc,dias_adicionales,anticipo,total_pagar,fecha_cobro"
)

_PERMITIDOS_UPDATE = {
    "periodo", "estado_doc", "observaciones", "cod_acta",
    "fecha_comprobante", "desde", "hasta", "dias_tomados",
    "referencia", "firmado", "lo_cubrio_agente", "fecha_firma",
    "fecha_pago", "fecha_cobro", "valor_vacaciones", "banco",
    "no_cheque", "forma_pago", "cta_cte_no", "total_periodo",
    "vacaciones_calc", "dias_adicionales", "anticipo", "total_pagar",
}


# ─── Número a letras (comprobante de anticipo) ───────────────────────────────
# Porta app.py::_numero_a_letras. Conversor propio para no depender de
# 'num2words' (no instalado ni empaquetado en el .exe — dependerlo dejaba el
# comprobante de anticipo sin generarse en toda máquina de producción, bug
# real corregido 2026-07-21 en el .pyw).

_UNIDADES = ("", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE")
_ESPECIALES_10_19 = ("DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISEIS",
                     "DIECISIETE", "DIECIOCHO", "DIECINUEVE")
_DECENAS = ("", "", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA",
            "SETENTA", "OCHENTA", "NOVENTA")
_CENTENAS = ("", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS",
             "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS")


def numero_a_letras(n: int) -> str:
    """Entero (0-999999) a letras en español. Porta `app.py::_numero_a_letras`."""
    n = int(n)
    if n == 0:
        return "CERO"
    if n < 0:
        return f"MENOS {numero_a_letras(-n)}"

    def _menor_1000(x: int) -> str:
        if x == 0:
            return ""
        if x == 100:
            return "CIEN"
        partes = []
        if x >= 100:
            partes.append(_CENTENAS[x // 100])
            x %= 100
        if x >= 20:
            partes.append(_DECENAS[x // 10])
            if x % 10:
                partes.append("Y " + _UNIDADES[x % 10])
        elif x >= 10:
            partes.append(_ESPECIALES_10_19[x - 10])
        elif x > 0:
            partes.append(_UNIDADES[x])
        return " ".join(p for p in partes if p)

    if n < 1000:
        return _menor_1000(n)

    miles, resto = divmod(n, 1000)
    txt_miles = "MIL" if miles == 1 else f"{_menor_1000(miles)} MIL"
    return f"{txt_miles} {_menor_1000(resto)}".strip()


def valor_en_letras(valor: float) -> str:
    """'123.45' -> 'CIENTO VEINTITRÉS CON 45/100 DÓLARES'. Porta el bloque
    homónimo de `_generar_pdf_anticipo`/`_dialogo_anticipo`."""
    entero = int(valor)
    centavos = round((valor - entero) * 100)
    return f"{numero_a_letras(entero).upper()} CON {centavos:02d}/100 DÓLARES"


# ─── Períodos (Art. 69/71/76 CT) — porta calculos.py tal cual ───────────────


def _fecha(d) -> date:
    if isinstance(d, str):
        return datetime.strptime(d[:10], "%Y-%m-%d").date()
    if isinstance(d, datetime):
        return d.date()
    return d


def calcular_periodo(fecha_ingreso, anio_base: int | None = None) -> dict:
    """Período de vacaciones para un año base. Porta `calculos.calcular_periodo`.

    Corre desde el aniversario de ingreso hasta el día anterior al siguiente
    aniversario. Ej: ingreso 15/03/2020, anio_base=2024 → '2024-2025'.
    """
    fi = _fecha(fecha_ingreso)
    if anio_base is None:
        anio_base = date.today().year

    dia = min(fi.day, calendar.monthrange(anio_base, fi.month)[1])
    inicio = date(anio_base, fi.month, dia)

    anio_fin = anio_base + 1
    dia_fin = min(fi.day, calendar.monthrange(anio_fin, fi.month)[1])
    fin = date(anio_fin, fi.month, dia_fin) - dt.timedelta(days=1)

    return {"label": f"{anio_base}-{anio_fin}", "inicio": inicio, "fin": fin, "anio_base": anio_base}


def periodos_disponibles(fecha_ingreso, fecha_referencia=None, n: int = 5) -> list[dict]:
    """Últimos n períodos (más reciente primero). Porta `calculos.periodos_disponibles`."""
    fi = _fecha(fecha_ingreso)
    fecha_referencia = _fecha(fecha_referencia) if fecha_referencia else date.today()

    dia_aniv = min(fi.day, calendar.monthrange(fecha_referencia.year, fi.month)[1])
    aniv_este_anio = date(fecha_referencia.year, fi.month, dia_aniv)
    anio_actual = fecha_referencia.year if fecha_referencia >= aniv_este_anio else fecha_referencia.year - 1

    periodos = []
    for i in range(n):
        per = calcular_periodo(fi, anio_actual - i)
        if per["inicio"] < fi:  # cubre reingresos
            break
        periodos.append(per)
    return periodos


def meses_en_periodo(inicio, fin) -> list[tuple[int, int]]:
    """Lista (anio, mes) dentro de [inicio, fin]. Porta `calculos.meses_en_periodo`."""
    inicio, fin = _fecha(inicio), _fecha(fin)
    meses = []
    cur = date(inicio.year, inicio.month, 1)
    while cur <= fin:
        meses.append((cur.year, cur.month))
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
    return meses


def calcular_dias_adicionales(fecha_ingreso, fecha_fin_periodo) -> tuple[int, int]:
    """Art. 69 CT: 1 día adicional por cada año de servicio sobre 5.

    Porta `calculos.calcular_dias_adicionales`. Los años se cuentan por AÑO
    CALENDARIO del período (año con el que termina), no por resta de días
    exacta — intencional, ver docstring original (bug real corregido
    2026-07-10 en el .pyw: una resta de días exacta da sistemáticamente <1
    año completo y trunca de menos).

    Retorna (dias_adicionales, anios_servicio).
    """
    fi, ref = _fecha(fecha_ingreso), _fecha(fecha_fin_periodo)
    anios = ref.year - fi.year
    return max(0, anios - 5), anios


# ─── dbtablas (cargo/depto/seccion) ──────────────────────────────────────────
# Caché propio: vacaciones.py no puede importar core.repos.empleados
# (test_repos_no_se_importan_entre_si) aunque haga una consulta equivalente.

_dbt_cache: dict[tuple[str, str], str] = {}


def _dbt(tipo: str, codigo: str) -> str:
    """Nombre de catálogo (FNC=cargo, DPT=depto, SEC=sección); código si no existe."""
    codigo = str(codigo or "").strip()
    if not codigo:
        return ""
    key = (tipo, codigo)
    if key not in _dbt_cache:
        with contextlib.suppress(Exception):
            sb = supabase_client.get_client()
            rows = (
                sb.table("dbtablas").select("codigo,nombre")
                .eq("codemp", "10").eq("tipo", tipo).eq("codigo", codigo)
                .limit(1).execute().data or []
            )
            if rows:
                _dbt_cache[key] = str(rows[0].get("nombre") or "").strip()
    return _dbt_cache.get(key, codigo)


def _emp_row_to_dict(row: dict) -> dict:
    cedula = normalizar_cedula(row.get("cedula"))
    cargo_cod = str(row.get("cargo") or "").strip()
    depto_cod = str(row.get("depto") or "").strip()
    return {
        "cod_empleado": str(row.get("empleado", "")).strip(),
        "cedula": cedula,
        "nombres": str(row.get("nombres") or "").strip(),
        "apellidos": str(row.get("apellidos") or "").strip(),
        "cargo": _dbt("FNC", cargo_cod),
        "departamento": _dbt("DPT", depto_cod),
        "fecha_ingreso": str(row.get("fecha_ing") or "")[:10] or None,
        "fecha_salida": str(row.get("fecha_sal") or "")[:10] or None,
        "sueldo": a_float(row.get("sueldo")),
        "estado": str(row.get("estado") or "ACT").strip(),
        "hor25": a_float(row.get("hor25")), "hor50": a_float(row.get("hor50")), "hor100": a_float(row.get("hor100")),
    }


# ─── Empleados (rpemplea) ────────────────────────────────────────────────────
# Porta las funciones equivalentes de supabase_client.py del .pyw. No se
# reutiliza core.repos.empleados (regla: un repo no importa otro repo).


def buscar_empleados(query: str, solo_activos: bool = False) -> list[dict]:
    """Busca en rpemplea por cédula o nombre/apellido. Porta `buscar_empleados` (SB)."""
    sb = supabase_client.get_client()
    query_digits = query.replace(".", "").replace(" ", "")
    is_cedula = query_digits.isdigit() and len(query_digits) >= 7
    terminos = query.upper().split()
    cols = "empleado,apellidos,nombres,cedula,sueldo,cargo,depto,fecha_ing,fecha_sal,estado,hor25,hor50,hor100"

    def _base():
        q = sb.table("rpemplea").select(cols).eq("codemp", "10").eq("codsuc", "10")
        return q.eq("estado", "ACT") if solo_activos else q

    try:
        if is_cedula:
            rows = _base().eq("cedula", int(query_digits)).limit(50).execute().data or []
        else:
            merged: dict = {}
            q_ap = _base()
            for t in terminos:
                q_ap = q_ap.ilike("apellidos", f"%{t}%")
            for r in q_ap.limit(100).execute().data or []:
                merged[r["empleado"]] = r
            q_nm = _base()
            for t in terminos:
                q_nm = q_nm.ilike("nombres", f"%{t}%")
            for r in q_nm.limit(40).execute().data or []:
                merged[r["empleado"]] = r
            rows = list(merged.values())[:50]
        return [_emp_row_to_dict(r) for r in rows if normalizar_cedula(r.get("cedula"))]
    except Exception as e:  # noqa: BLE001
        log.error("buscar_empleados: %s", e)
        return []


def get_empleado_by_cedula(cedula: str) -> dict | None:
    """Empleado exacto por cédula. Porta `get_empleado_by_cedula` (SB)."""
    if not cedula:
        return None
    sb = supabase_client.get_client()
    try:
        cedula_int = int(str(cedula).lstrip("0") or "0")
        rows = (
            sb.table("rpemplea")
            .select("empleado,apellidos,nombres,cedula,sueldo,cargo,depto,fecha_ing,fecha_sal,estado,hor25,hor50,hor100")
            .eq("codemp", "10").eq("codsuc", "10").eq("cedula", cedula_int)
            .limit(1).execute().data or []
        )
        return _emp_row_to_dict(rows[0]) if rows else None
    except Exception as e:  # noqa: BLE001
        log.error("get_empleado_by_cedula cedula=%s: %s", cedula, e)
        return None


def batch_emp_data(cedulas: list[str]) -> dict[str, dict]:
    """rpemplea para una lista de cédulas → {cedula: datos}. Porta `batch_emp_data` (SB)."""
    if not cedulas:
        return {}
    sb = supabase_client.get_client()
    cedulas_int = []
    for c in cedulas:
        with contextlib.suppress(Exception):
            cedulas_int.append(int(str(c).lstrip("0") or "0"))
    result: dict[str, dict] = {}
    for i in range(0, len(cedulas_int), 100):
        lote = cedulas_int[i:i + 100]
        try:
            rows = (
                sb.table("rpemplea")
                .select("empleado,apellidos,nombres,cedula,cargo,depto,fecha_ing,fecha_sal,estado,sueldo")
                .eq("codemp", "10").eq("codsuc", "10").in_("cedula", lote)
                .execute().data or []
            )
            for row in rows:
                ced = normalizar_cedula(row.get("cedula"))
                if ced:
                    result[ced] = _emp_row_to_dict(row)
        except Exception as e:  # noqa: BLE001
            log.warning("batch_emp_data lote %d: %s", i, e)
    return result


def fetch_empleados_activos(departamento: str | None = None) -> list[dict]:
    """Todos los empleados ACT de rpemplea, paginado. Porta `fetch_empleados_activos` (SB)."""
    sb = supabase_client.get_client()
    result: list[dict] = []
    offset, page = 0, 1000
    while True:
        rows = (
            sb.table("rpemplea")
            .select("empleado,apellidos,nombres,cedula,cargo,depto,fecha_ing")
            .eq("codemp", "10").eq("codsuc", "10").eq("estado", "ACT")
            .order("apellidos").range(offset, offset + page - 1)
            .execute().data or []
        )
        if not rows:
            break
        for r in rows:
            emp = _emp_row_to_dict(r)
            if not emp["cedula"]:
                continue
            if departamento and emp["departamento"] != departamento:
                continue
            result.append(emp)
        offset += page
        if len(rows) < page:
            break
    return result


def get_count_activos() -> int:
    sb = supabase_client.get_client()
    try:
        r = (
            sb.table("rpemplea").select("empleado", count=CountMethod.exact)
            .eq("codemp", "10").eq("codsuc", "10").eq("estado", "ACT").execute()
        )
        return r.count or 0
    except Exception as e:  # noqa: BLE001
        log.error("get_count_activos: %s", e)
        return 0


# ─── Movimientos de nómina (rphistor_temp + rpingdesres) ────────────────────


def get_movimientos_empleado(cod_empleado: str, fecha_inicio, fecha_fin) -> list[dict]:
    """Movimientos de nómina en [fecha_inicio, fecha_fin]. Porta `get_movimientos_empleado` (SB).

    Mismas tablas que `core/repos/nomina.py::_mov_supabase`: `rphistor_temp`
    (meses cerrados) + `rpingdesres` (mes abierto, solo meses no cubiertos
    por rphistor_temp).
    """
    if not cod_empleado:
        return []
    fi = fecha_inicio.strftime("%Y-%m-%d") if isinstance(fecha_inicio, (date, datetime)) else str(fecha_inicio)
    ff = fecha_fin.strftime("%Y-%m-%d") if isinstance(fecha_fin, (date, datetime)) else str(fecha_fin)
    ff_date = datetime.strptime(ff, "%Y-%m-%d").date()
    ff_next = (ff_date + dt.timedelta(days=1)).strftime("%Y-%m-%d")

    sb = supabase_client.get_client()

    def _parse(rows):
        out = []
        for row in rows:
            try:
                clase = int(row.get("clase"))
                fv_raw = row.get("fecha_ven")
                if not fv_raw:
                    continue
                fv = datetime.strptime(str(fv_raw)[:10], "%Y-%m-%d")
                out.append({"clase": clase, "valor": a_float(row.get("valor")), "fecha_ven": fv})
            except Exception:  # noqa: BLE001
                continue
        return out

    movimientos: list[dict] = []
    histor_meses: set[str] = set()
    try:
        rows_h = (
            sb.table("rphistor_temp").select("empleado,clase,valor,fecha_ven")
            .eq("empleado", str(cod_empleado)).gte("fecha_ven", fi).lt("fecha_ven", ff_next)
            .execute().data or []
        )
        for mov in _parse(rows_h):
            if mov["fecha_ven"].date() <= ff_date:
                movimientos.append(mov)
                histor_meses.add(mov["fecha_ven"].strftime("%Y-%m"))
    except Exception as e:  # noqa: BLE001
        log.warning("get_movimientos_empleado rphistor_temp: %s", e)

    try:
        rows_i = (
            sb.table("rpingdesres").select("empleado,clase,valor,fecha_ven")
            .eq("empleado", str(cod_empleado)).gte("fecha_ven", fi).lt("fecha_ven", ff_next)
            .execute().data or []
        )
        for mov in _parse(rows_i):
            if mov["fecha_ven"].date() <= ff_date and mov["fecha_ven"].strftime("%Y-%m") not in histor_meses:
                movimientos.append(mov)
    except Exception as e:  # noqa: BLE001
        log.warning("get_movimientos_empleado rpingdesres: %s", e)

    return movimientos


def get_codigos_base() -> set[int]:
    """Códigos CLASE base de cálculo desde `vac_codigos_nomina`. Porta `get_codigos_base`."""
    try:
        sb = supabase_client.get_client()
        rows = sb.table("vac_codigos_nomina").select("codigo").eq("en_base", True).execute().data or []
        if rows:
            return {int(r["codigo"]) for r in rows}
    except Exception as e:  # noqa: BLE001
        log.warning("get_codigos_base: usando defaults: %s", e)
    return set(CODIGOS_BASE_DEFAULT)


def agrupar_movimientos_por_mes(movimientos: list[dict], inicio, fin) -> dict:
    """Agrupa movimientos por (anio,mes) sumando solo códigos base. Porta `calculos.agrupar_movimientos_por_mes`."""
    inicio, fin = _fecha(inicio), _fecha(fin)
    codigos_base = get_codigos_base()
    por_mes: dict[tuple[int, int], dict] = {}
    for mov in movimientos:
        fv = mov.get("fecha_ven")
        fv = _fecha(fv) if fv else None
        if not fv or not (inicio <= fv <= fin):
            continue
        clase = int(mov.get("clase", 0))
        if clase not in codigos_base:
            continue
        key = (fv.year, fv.month)
        por_mes.setdefault(key, dict.fromkeys(codigos_base, 0.0))
        por_mes[key][clase] = por_mes[key].get(clase, 0.0) + a_float(mov.get("valor"))
    return por_mes


def get_config(clave: str, default=None):
    """Parámetro de `vac_config` (empresa, firmante, divisores...). Porta `get_config`."""
    sb = supabase_client.get_client()
    try:
        rows = sb.table("vac_config").select("valor").eq("clave", clave).limit(1).execute().data or []
        return rows[0]["valor"] if rows else default
    except Exception as e:  # noqa: BLE001
        log.warning("get_config %s: %s", clave, e)
        return default


# ─── Fórmula de pago (producción) ────────────────────────────────────────────


def calcular_pago(
    *, dias_gozados: int, dias_adicionales: int, total_periodo_12m: float,
    anticipo: float = 0.0, dias_basicos: int = 15,
) -> dict:
    """Fórmula real de pago de vacaciones. Porta `app.py::_recalcular_totales`
    (NO `calculos.calcular_vacaciones_pagadas`, que es código muerto con otra
    fórmula — ver docstring del módulo).

        dias_a_pagar = max(0, dias_basicos + dias_adicionales - dias_gozados)
        valor_15_dias = total_periodo_12m / 24
        valor_dia     = valor_15_dias / 15
        valor_total   = valor_dia * dias_a_pagar
        valor_neto    = max(0, valor_total - anticipo)

    `total_periodo_12m` = suma de `total_mes` de los primeros 12 meses del
    período (ver `agrupar_movimientos_por_mes` + `calcular_total_periodo`).
    """
    dias_a_pagar = max(0, dias_basicos + dias_adicionales - dias_gozados)
    if total_periodo_12m > 0:
        valor_15_dias = round(total_periodo_12m / 24, 2)
        valor_dia = valor_15_dias / 15
        valor_total = round(valor_dia * dias_a_pagar, 2)
    else:
        valor_15_dias = valor_dia = valor_total = 0.0
    valor_neto = round(max(0.0, valor_total - anticipo), 2)
    return {
        "dias_a_pagar": dias_a_pagar,
        "total_periodo": round(total_periodo_12m, 2),
        "vacaciones_calc": valor_15_dias,
        "valor_dia": round(valor_dia, 4),
        "anticipo": round(anticipo, 2),
        "total_pagar": valor_neto,
    }


def calcular_total_periodo(detalles: list[dict]) -> tuple[float, dict]:
    """Suma sueldo/bonif/maniobras/h25/h50/h100 de una lista de meses. Porta `calculos.calcular_total_periodo`."""
    sueldo = bonif = maniobras = h25 = h50 = h100 = 0.0
    for d in detalles:
        sueldo += a_float(d.get("sueldo"))
        bonif += a_float(d.get("bonificacion"))
        maniobras += a_float(d.get("maniobras"))
        h25 += a_float(d.get("hor25"))
        h50 += a_float(d.get("hor50"))
        h100 += a_float(d.get("hor100"))
    total = sueldo + bonif + maniobras + h25 + h50 + h100
    return total, {
        "sueldo": round(sueldo, 2), "bonificacion": round(bonif, 2), "maniobras": round(maniobras, 2),
        "hor25": round(h25, 2), "hor50": round(h50, 2), "hor100": round(h100, 2),
    }


def sobretiempo_teorico(sueldo: float, hor25: float, hor50: float, hor100: float) -> tuple[float, float, float]:
    """Sobretiempo teórico del mes en curso (no cerrado en nómina), a partir de
    las horas asignadas en rpemplea. Porta `calculos.sobretiempo_teorico`."""
    if sueldo <= 0:
        return 0.0, 0.0, 0.0
    hora = sueldo / 240  # salario hora
    return (
        round(hora * 1.25 * (hor25 or 0), 2),
        round(hora * 1.50 * (hor50 or 0), 2),
        round(hora * 2.00 * (hor100 or 0), 2),
    )


def calcular_meses_periodo(
    movimientos: list[dict], inicio, fin, *, sueldo_base: float = 0, hor25: float = 0,
    hor50: float = 0, hor100: float = 0,
) -> list[dict]:
    """Tabla mensual (12 filas) del período a partir de movimientos ya
    descargados. Porta `sync_sqlserver.calcular_periodo_desde_movimientos` —
    usado tanto por `calcular_pago` (vía el state) como por `datos_comprobante`
    cuando `vac_calculo` no tiene datos guardados para ese (cédula, período).

    Para el mes en curso (no cerrado en nómina) calcula sobretiempo teórico
    desde las horas de `rpemplea` en vez de dejarlo en cero.
    """
    por_mes = agrupar_movimientos_por_mes(movimientos, inicio, fin)
    hoy = date.today()
    filas = []
    for anio, mes in meses_en_periodo(inicio, fin):
        datos_mes = dict(por_mes.get((anio, mes), dict.fromkeys(CODIGOS_BASE_DEFAULT, 0.0)))
        if anio == hoy.year and mes == hoy.month and sueldo_base > 0:
            v25, v50, v100 = sobretiempo_teorico(sueldo_base, hor25, hor50, hor100)
            datos_mes[113], datos_mes[114], datos_mes[115] = v25, v50, v100
            if not datos_mes.get(100) and sueldo_base:
                datos_mes[100] = sueldo_base
        fila = {
            "mes": mes, "anio": anio,
            "fecha_mes": _fecha(date(anio, mes, calendar.monthrange(anio, mes)[1])).isoformat(),
            "sueldo": round(datos_mes.get(100, 0), 2), "bonificacion": round(datos_mes.get(102, 0), 2),
            "maniobras": round(datos_mes.get(110, 0), 2), "hor25": round(datos_mes.get(113, 0), 2),
            "hor50": round(datos_mes.get(114, 0), 2), "hor100": round(datos_mes.get(115, 0), 2),
            "es_manual": 0, "fuente": "supabase",
        }
        fila["total_mes"] = round(
            sum(fila[k] for k in ("sueldo", "bonificacion", "maniobras", "hor25", "hor50", "hor100")), 2
        )
        filas.append(fila)
    return filas


# ─── CRUD vac_registros ──────────────────────────────────────────────────────


def _norm_vac_row(row: dict) -> dict:
    r = dict(row)
    for campo in ("valor_vacaciones", "total_periodo", "vacaciones_calc", "anticipo", "total_pagar"):
        if r.get(campo) is not None:
            r[campo] = a_float(r[campo])
    for campo in ("dias_tomados", "dias_adicionales", "anio_registro"):
        if r.get(campo) is not None:
            r[campo] = a_int(r[campo])
    return r


def get_vacacion(vac_id: int) -> dict | None:
    """Una vacación por ID, enriquecida con datos del empleado. Porta `get_vacacion_sb`."""
    sb = supabase_client.get_client()
    try:
        rows = sb.table("vac_registros").select(_VAC_COLS).eq("id", vac_id).limit(1).execute().data or []
        if not rows:
            return None
        vac = _norm_vac_row(rows[0])
        emp = get_empleado_by_cedula(vac.get("cedula", ""))
        if emp:
            vac["emp_nombres"] = emp.get("nombres", "")
            vac["emp_apellidos"] = emp.get("apellidos", "")
            vac["emp_fecha_ingreso"] = emp.get("fecha_ingreso", "")
            vac["emp_sueldo"] = emp.get("sueldo", 0)
        return vac
    except Exception as e:  # noqa: BLE001
        log.error("get_vacacion id=%s: %s", vac_id, e)
        return None


def get_vacaciones_empleado(cedula: str, tipo: str | None = None) -> list[dict]:
    """Vacaciones de un empleado por cédula. Porta `get_vacaciones_empleado_sb`."""
    cedula_n = normalizar_cedula(cedula)
    if not cedula_n:
        return []
    sb = supabase_client.get_client()
    try:
        q = sb.table("vac_registros").select(_VAC_COLS).eq("cedula", cedula_n)
        if tipo:
            q = q.eq("tipo", tipo)
        rows = (
            q.order("periodo", desc=True).order("desde", desc=True)
            .order("fecha_pago", desc=True).execute().data or []
        )
        return [_norm_vac_row(r) for r in rows]
    except Exception as e:  # noqa: BLE001
        log.error("get_vacaciones_empleado cedula=%s: %s", cedula, e)
        return []


def get_pagada_existente(cedula: str, periodo: str) -> dict | None:
    """Pago ya registrado para (cedula, periodo), si existe. Porta `get_pagada_existente_sb`."""
    cedula_n = normalizar_cedula(cedula)
    if not cedula_n:
        return None
    sb = supabase_client.get_client()
    try:
        rows = (
            sb.table("vac_registros").select("id,estado_doc,total_pagar,fecha_pago")
            .eq("cedula", cedula_n).eq("tipo", "pagada").eq("periodo", periodo)
            .neq("estado_doc", "borrador").order("id", desc=True).limit(1).execute().data or []
        )
        if not rows:
            return None
        r = rows[0]
        return {"id": r["id"], "estado_doc": r.get("estado_doc"),
                "total_pagar": a_float(r.get("total_pagar")), "fecha_pago": r.get("fecha_pago")}
    except Exception as e:  # noqa: BLE001
        log.error("get_pagada_existente cedula=%s periodo=%s: %s", cedula, periodo, e)
        return None


def resumen_empleado(cedula: str) -> dict:
    """Totales de vacaciones de un empleado (días gozados, pagado, pendientes).
    Porta `model.get_resumen_empleado` / `get_resumen_empleado_sb`."""
    cedula_n = normalizar_cedula(cedula)
    vacio = {"dias_gozados": 0, "gozada_count": 0, "total_pagado": 0.0, "pagada_count": 0, "pendientes": 0}
    if not cedula_n:
        return vacio
    sb = supabase_client.get_client()
    try:
        rows = (
            sb.table("vac_registros").select("tipo,dias_tomados,total_pagar,estado_doc")
            .eq("cedula", cedula_n).execute().data or []
        )
    except Exception as e:  # noqa: BLE001
        log.error("resumen_empleado cedula=%s: %s", cedula, e)
        return vacio
    dias_goz = gozada_count = pagada_count = pendientes = 0
    total_pag = 0.0
    for r in rows:
        if r.get("tipo") == "gozada":
            dias_goz += a_int(r.get("dias_tomados"))
            gozada_count += 1
        else:
            if r.get("estado_doc") == "completado":
                total_pag += a_float(r.get("total_pagar"))
            pagada_count += 1
        if r.get("estado_doc") == "pendiente":
            pendientes += 1
    return {
        "dias_gozados": dias_goz, "gozada_count": gozada_count,
        "total_pagado": round(total_pag, 2), "pagada_count": pagada_count, "pendientes": pendientes,
    }


def get_dias_gozados_periodo(cedula: str, periodo: str) -> int:
    """Suma de días gozados en un período. Porta `get_dias_gozados_periodo_sb`."""
    cedula_n = normalizar_cedula(cedula)
    if not cedula_n:
        return 0
    sb = supabase_client.get_client()
    try:
        rows = (
            sb.table("vac_registros").select("dias_tomados")
            .eq("cedula", cedula_n).eq("tipo", "gozada").eq("periodo", str(periodo))
            .execute().data or []
        )
        return sum(a_int(r.get("dias_tomados")) for r in rows)
    except Exception as e:  # noqa: BLE001
        log.error("get_dias_gozados_periodo cedula=%s periodo=%s: %s", cedula, periodo, e)
        return 0


def crear_gozada(datos: dict, *, usuario: str, roles: set[str]) -> int:
    """Registra una vacación GOCE. Porta `DlgGozada._guardar` + `model.insertar_vacacion`.

    `datos` espera: cedula, periodo, fecha_comprobante, desde, hasta,
    dias_tomados, dias_adicionales, firmado, lo_cubrio_agente, referencia,
    estado_doc, observaciones. Si `lo_cubrio_agente` viene con valor, se anexa
    a `observaciones` (mismo comportamiento del diálogo original).
    """
    cedula_n = normalizar_cedula(datos.get("cedula"))
    if not cedula_n:
        raise ValueError("No se pudo identificar al empleado (cédula vacía).")
    if not datos.get("desde") and not a_int(datos.get("dias_tomados")):
        raise ValueError("Ingrese al menos la fecha Desde o los días tomados.")

    agente = str(datos.get("lo_cubrio_agente") or "").strip()
    observaciones = str(datos.get("observaciones") or "").strip()
    if agente:
        observaciones = f"{observaciones} - {agente}" if observaciones else agente

    return _insertar(
        {**datos, "cedula": cedula_n, "tipo": "gozada", "observaciones": observaciones,
         "dias_tomados": a_int(datos.get("dias_tomados")),
         "dias_adicionales": a_int(datos.get("dias_adicionales"))},
        usuario=usuario, roles=roles,
    )


def crear_pagada(
    *, cedula: str, periodo: str, dias_gozados: int, dias_adicionales: int,
    total_periodo_12m: float, forma_pago: str, anticipo: float = 0.0,
    banco: str = "", cta_cte_no: str = "", no_cheque: str = "",
    fecha_pago: str | None = None, observaciones: str = "",
    dias_basicos: int = 15, detalles_mensuales: list[dict] | None = None,
    usuario: str, roles: set[str],
) -> tuple[int, dict]:
    """Registra una vacación PAGO calculada (flujo pestaña "Cálculo").

    Porta `app.py::_registrar_pagada`. Reglas del original conservadas:
    - `estado_doc` = `'pendiente'` si `forma_pago == 'CHEQUE'` (financiero
      completa el número después), si no `'completado'`.
    - No valida "días adicionales" con confirmación aparte — eso es UI
      (mostrar el aviso es responsabilidad del state/página); aquí solo se
      exige `dias_a_pagar > 0` y `total_pagar > 0`, igual que el original.
    - `valor_vacaciones` y `total_pagar` guardan el mismo valor neto (post-
      anticipo) — así lo hace `_registrar_pagada`.
    - Si se pasa `detalles_mensuales` (la tabla de 12 meses que armó
      `calcular_meses_periodo`/el state), se persiste en `vac_calculo` vía
      `guardar_calculo_detalle` — igual que `_registrar_pagada` hace al final
      ("Guardar calculo_detalle... para que el PDF lo encuentre"). Sin esto,
      `datos_comprobante()` tendría que recalcular desde movimientos cada vez
      que se genera el PDF, con riesgo de dar un valor distinto si la nómina
      cambió entre el registro del pago y la generación del comprobante.

    Retorna `(vac_id, calculo)` — `calculo` es el dict de `calcular_pago()`
    para que la UI lo muestre/audite.
    """
    cedula_n = normalizar_cedula(cedula)
    if not cedula_n:
        raise ValueError("No se pudo identificar al empleado (cédula vacía).")
    forma_pago = (forma_pago or "").strip().upper()
    if not forma_pago:
        raise ValueError('Indique la forma de pago (TRANSFERENCIA / CHEQUE / EFECTIVO).')

    calculo = calcular_pago(
        dias_gozados=dias_gozados, dias_adicionales=dias_adicionales,
        total_periodo_12m=total_periodo_12m, anticipo=anticipo, dias_basicos=dias_basicos,
    )
    if calculo["dias_a_pagar"] <= 0:
        raise ValueError("No hay días a pagar.")
    if calculo["total_pagar"] <= 0:
        raise ValueError("No hay valor a pagar.")

    anio = periodo.split("-")[0] if periodo else "0000"
    estado = "pendiente" if forma_pago == "CHEQUE" else "completado"

    vac_id = _insertar(
        {
            "cedula": cedula_n, "tipo": "pagada", "periodo": periodo,
            "dias_tomados": calculo["dias_a_pagar"], "dias_adicionales": dias_adicionales,
            "valor_vacaciones": calculo["total_pagar"], "total_pagar": calculo["total_pagar"],
            "total_periodo": calculo["total_periodo"], "vacaciones_calc": calculo["vacaciones_calc"],
            "anticipo": calculo["anticipo"], "forma_pago": forma_pago, "banco": banco,
            "cta_cte_no": cta_cte_no, "no_cheque": no_cheque, "fecha_pago": fecha_pago,
            "observaciones": observaciones or f"Período: {periodo}", "estado_doc": estado,
        },
        usuario=usuario, roles=roles,
    )
    if vac_id:
        actualizar(vac_id, {"cod_acta": f"ACTA-{anio}-{vac_id:05d}"}, usuario=usuario, roles=roles)
        if detalles_mensuales:
            with contextlib.suppress(Exception):
                guardar_calculo_detalle(cedula_n, periodo, detalles_mensuales, vac_id=vac_id)
    return vac_id, calculo


def crear_pagada_manual(datos: dict, *, usuario: str, roles: set[str]) -> int:
    """Registra una vacación PAGO con valores ingresados a mano. Porta `DlgPagada._guardar`.

    A diferencia de `crear_pagada`, no recalcula nada: usa los valores que
    trae `datos` (total_periodo, vacaciones_calc, dias_adicionales, anticipo,
    total_pagar...) tal como el diálogo manual del `.pyw`, para los casos que
    no pasan por la pestaña "Cálculo". `valor_vacaciones` se iguala a
    `total_pagar`, igual que el original.
    """
    cedula_n = normalizar_cedula(datos.get("cedula"))
    if not cedula_n:
        raise ValueError("No se pudo identificar al empleado (cédula vacía).")
    if not a_float(datos.get("total_pagar")) and not datos.get("periodo"):
        raise ValueError("Ingrese el período y el total a pagar.")

    payload = dict(datos)
    for campo in ("total_periodo", "vacaciones_calc", "anticipo", "total_pagar", "dias_adicionales"):
        payload[campo] = a_float(payload.get(campo))
    payload["valor_vacaciones"] = payload.get("total_pagar", 0)
    payload["cedula"] = cedula_n
    payload["tipo"] = "pagada"
    return _insertar(payload, usuario=usuario, roles=roles)


def _insertar(datos: dict, *, usuario: str, roles: set[str]) -> int:
    cedula_n = datos["cedula"]
    sb = supabase_client.get_client()
    payload = {
        "cedula": cedula_n, "tipo": datos.get("tipo"), "periodo": datos.get("periodo"),
        "anio_registro": datos.get("anio_registro"), "estado_doc": datos.get("estado_doc", "completado"),
        "observaciones": datos.get("observaciones"), "source": datos.get("source", "sistema"),
        "cod_acta": datos.get("cod_acta"), "fecha_comprobante": datos.get("fecha_comprobante"),
        "desde": datos.get("desde"), "hasta": datos.get("hasta"),
        "dias_tomados": a_int(datos.get("dias_tomados")), "referencia": datos.get("referencia"),
        "firmado": datos.get("firmado"), "lo_cubrio_agente": datos.get("lo_cubrio_agente"),
        "fecha_pago": datos.get("fecha_pago"), "valor_vacaciones": a_float(datos.get("valor_vacaciones")),
        "banco": datos.get("banco"), "no_cheque": datos.get("no_cheque"),
        "forma_pago": datos.get("forma_pago"), "cta_cte_no": datos.get("cta_cte_no"),
        "total_periodo": a_float(datos.get("total_periodo")), "vacaciones_calc": a_float(datos.get("vacaciones_calc")),
        "dias_adicionales": a_int(datos.get("dias_adicionales")), "anticipo": a_float(datos.get("anticipo")),
        "total_pagar": a_float(datos.get("total_pagar")), "fecha_cobro": datos.get("fecha_cobro"),
    }
    payload = {
        k: v for k, v in payload.items()
        if v is not None or k in ("tipo", "cedula", "dias_tomados", "dias_adicionales")
    }
    resp = sb.table("vac_registros").insert(payload).execute()
    if not resp.data:
        raise RuntimeError("Supabase no devolvió ID al insertar vacación.")
    vac_id = resp.data[0]["id"]
    tipo_lbl = "GOCE" if datos.get("tipo") == "gozada" else "PAGO"
    _auditar_vac(vac_id, "crear", usuario, roles, detalle=f"Nuevo {tipo_lbl} | periodo={datos.get('periodo')}")
    return vac_id


def actualizar(vac_id: int, campos: dict, *, usuario: str, roles: set[str]) -> None:
    """Actualiza campos permitidos de una vacación. Porta `actualizar_vacacion_sb`."""
    payload = {k: v for k, v in campos.items() if k in _PERMITIDOS_UPDATE}
    if not payload:
        return
    payload["updated_at"] = datetime.now(dt.UTC).isoformat()
    sb = supabase_client.get_client()
    sb.table("vac_registros").update(payload).eq("id", vac_id).execute()
    _auditar_vac(vac_id, "editar", usuario, roles, detalle=f"Campos: {', '.join(campos)}")


def eliminar(vac_id: int, *, usuario: str, roles: set[str]) -> None:
    """Elimina una vacación (vac_calculo cae en cascade). Porta `eliminar_vacacion_sb`."""
    sb = supabase_client.get_client()
    sb.table("vac_registros").delete().eq("id", vac_id).execute()
    _auditar_vac(vac_id, "eliminar", usuario, roles, detalle=f"Eliminado id={vac_id}")


def registrar_pago(vac_id: int, *, banco: str, no_cheque: str, fecha_pago: str | None = None,
                    usuario: str, roles: set[str]) -> None:
    """Completa una pagada 'pendiente' (cheque) con su número. Porta `model.registrar_pago`."""
    actualizar(vac_id, {
        "banco": banco, "no_cheque": no_cheque,
        "fecha_pago": fecha_pago or date.today().strftime("%Y-%m-%d"),
        "estado_doc": "completado",
    }, usuario=usuario, roles=roles)


def marcar_firmada(vac_id: int, *, usuario: str, roles: set[str]) -> None:
    """Marca una gozada como firmada/confirmada. Porta `model.marcar_gozada_firmada`."""
    actualizar(vac_id, {"firmado": "POSITIVO", "estado_doc": "completado"}, usuario=usuario, roles=roles)


def _auditar_vac(vac_id: int, accion: str, usuario: str, roles: set[str], *, detalle: str = "") -> None:
    """Doble registro: `vac_auditoria` (Supabase, tabla propia del módulo — el
    `.pyw` original NO la usa, ver docstring del módulo) + `core.audit`
    (historial compartido de la app web, como hace `bitacora.py`)."""
    with contextlib.suppress(Exception):
        supabase_client.get_client().table("vac_auditoria").insert({
            "vac_id": vac_id, "accion": accion, "usuario": usuario, "detalle": detalle,
        }).execute()
    registrar_evento("vacaciones", accion, usuario=usuario, roles=roles, fuente="supabase",
                     target_table="vac_registros", target_key=str(vac_id))


# ─── Cálculo detalle (vac_calculo) ───────────────────────────────────────────

_CALC_COLS = (
    "id,vac_id,cedula,periodo,mes,anio,fecha_mes,"
    "sueldo,bonificacion,maniobras,hor25,hor50,hor100,total_mes,es_manual,fuente"
)


def get_calculo_detalle(cedula: str, periodo: str) -> list[dict]:
    """Desglose mensual de un período. Porta `get_calculo_detalle_sb`."""
    cedula_n = normalizar_cedula(cedula)
    if not cedula_n:
        return []
    sb = supabase_client.get_client()
    try:
        rows = (
            sb.table("vac_calculo").select(_CALC_COLS)
            .eq("cedula", cedula_n).eq("periodo", periodo).order("anio").order("mes")
            .execute().data or []
        )
        return rows
    except Exception as e:  # noqa: BLE001
        log.error("get_calculo_detalle cedula=%s periodo=%s: %s", cedula, periodo, e)
        return []


def guardar_calculo_detalle(cedula: str, periodo: str, filas: list[dict], vac_id: int | None = None) -> bool:
    """Reemplaza el desglose mensual de (cedula, periodo). Porta `guardar_calculo_detalle_sb`."""
    cedula_n = normalizar_cedula(cedula)
    if not cedula_n or not filas:
        return False
    sb = supabase_client.get_client()
    try:
        sb.table("vac_calculo").delete().eq("cedula", cedula_n).eq("periodo", periodo).execute()
        payload = []
        for f in filas:
            mes, anio = a_int(f.get("mes")), a_int(f.get("anio"))
            if not mes or not anio:
                continue
            ultimo_dia = calendar.monthrange(anio, mes)[1]
            payload.append({
                "vac_id": vac_id, "cedula": cedula_n, "periodo": periodo, "mes": mes, "anio": anio,
                "fecha_mes": f.get("fecha_mes") or f"{anio}-{mes:02d}-{ultimo_dia:02d}",
                "sueldo": round(a_float(f.get("sueldo")), 2),
                "bonificacion": round(a_float(f.get("bonificacion")), 2),
                "maniobras": round(a_float(f.get("maniobras")), 2),
                "hor25": round(a_float(f.get("hor25")), 2), "hor50": round(a_float(f.get("hor50")), 2),
                "hor100": round(a_float(f.get("hor100")), 2), "total_mes": round(a_float(f.get("total_mes")), 2),
                "es_manual": 1 if f.get("es_manual") else 0, "fuente": str(f.get("fuente") or "sistema"),
            })
        if payload:
            sb.table("vac_calculo").insert(payload).execute()
        return True
    except Exception as e:  # noqa: BLE001
        log.error("guardar_calculo_detalle cedula=%s: %s", cedula, e)
        return False


# ─── Comprobante (datos para el PDF individual GOCE/PAGO) ───────────────────


def _normalizar_periodo_legado(periodo: str) -> str:
    """'2025' (convenio AÑO FINAL del Excel histórico) -> '2024-2025'. Porta
    `data_extractor._normalizar_periodo`."""
    if periodo and "-" not in str(periodo) and str(periodo).isdigit():
        yr = int(periodo)
        return f"{yr - 1}-{yr}"
    return periodo or ""


def datos_comprobante(vac_id: int) -> dict:
    """Todos los datos para generar el PDF individual GOCE/PAGO (y su QR).
    Porta `VACACIONES_SISTEMA_INSEVIG/src/data_extractor.py::get_vacacion_data`
    — mismas claves de salida, para que el builder de PDF (`core/pdf/...`) sea
    un trasplante directo de `src/pdf_generator.py`.

    A diferencia del `.pyw` (que resuelve el empleado con `get_empleado_sqlserver`,
    sensible a `fuente_nomina`), aquí siempre se lee de Supabase `rpemplea`
    — esta app todavía no modela ese toggle para vacaciones. Diferencia
    deliberada, no un bug: repórtese si hace falta el fallback a SQL Server.

    Lanza `ValueError` si la vacación o el empleado no existen (igual que el original).
    """
    vac = get_vacacion(vac_id)
    if not vac:
        raise ValueError(f"Vacacion id={vac_id} no encontrada")
    cedula = vac.get("cedula") or ""
    if not cedula:
        raise ValueError(f"Vacacion id={vac_id} no tiene cédula asociada")
    empleado = get_empleado_by_cedula(cedula)
    if not empleado:
        raise ValueError(f"Empleado cedula={cedula} no encontrado")

    periodo_completo = _normalizar_periodo_legado(vac.get("periodo") or "")
    anio_base = int(periodo_completo.split("-")[0]) if periodo_completo else None
    nombre_completo = (
        f"{vac.get('emp_apellidos') or empleado.get('apellidos', '')} "
        f"{vac.get('emp_nombres') or empleado.get('nombres', '')}"
    ).strip()
    fecha_ingreso = vac.get("emp_fecha_ingreso") or empleado.get("fecha_ingreso") or ""
    tipo = vac.get("tipo") or ""

    # ── Fechas del período (para PAGO se recalculan, igual que el Excel) ────
    fecha_desde = vac.get("desde") or ""
    fecha_hasta = vac.get("hasta") or ""
    if tipo == "pagada" and fecha_ingreso and anio_base:
        try:
            calcular_periodo(fecha_ingreso, anio_base)  # valida que el período exista
            fi_real = _fecha(fecha_ingreso)
            fecha_1_periodo = date(anio_base, 1, 1)
            desde_date = date(anio_base, fi_real.month, 1) if fi_real <= fecha_1_periodo else fi_real
            fecha_desde = desde_date.isoformat()
            m_h = desde_date.month + 11
            y_h = desde_date.year + (m_h - 1) // 12
            m_h = ((m_h - 1) % 12) + 1
            fecha_hasta = f"{y_h}-{m_h:02d}-{calendar.monthrange(y_h, m_h)[1]:02d}"
        except Exception:  # noqa: BLE001
            pass

    dias_adicionales = a_int(vac.get("dias_adicionales"))
    if dias_adicionales == 0 and fecha_ingreso and fecha_hasta:
        with contextlib.suppress(Exception):
            dias_adicionales, _ = calcular_dias_adicionales(fecha_ingreso, fecha_hasta)

    # ── Detalle mensual: vac_calculo primero, si no hay recalcula de nómina ──
    detalles = get_calculo_detalle(cedula, periodo_completo)
    tiene_valores = any(a_float(d.get("total_mes")) > 0 for d in detalles)
    if not tiene_valores and empleado.get("cod_empleado") and fecha_ingreso and anio_base:
        with contextlib.suppress(Exception):
            per = calcular_periodo(fecha_ingreso, anio_base)
            movs = get_movimientos_empleado(empleado["cod_empleado"], per["inicio"], per["fin"])
            filas = calcular_meses_periodo(
                movs, per["inicio"], per["fin"], sueldo_base=empleado.get("sueldo", 0),
            )
            if any(a_float(f.get("total_mes")) > 0 for f in filas) or not detalles:
                # OJO: `filas` puede traer 13 meses calendario (no se trunca a
                # [:12] aquí) — igual que `data_extractor.get_vacacion_data`
                # original, que tampoco lo hace en este fallback (a diferencia
                # de `_registrar_pagada`, que sí trunca antes de guardar en
                # vac_calculo). Es una inconsistencia preexistente del .pyw,
                # solo se activa si esta vacación nunca tuvo vac_calculo
                # guardado (pagos históricos); portada tal cual, no corregida.
                detalles = filas

    total_ingresos = sum(a_float(d.get("total_mes")) for d in detalles)
    meses_detalle = [
        {"mes": d["mes"], "anio": d["anio"], "valor": round(a_float(d.get("total_mes")), 2)}
        for d in detalles
    ][:12]

    if tipo == "pagada" and detalles:
        ultimo = detalles[-1]
        fecha_mes = ultimo.get("fecha_mes") or ""
        if not fecha_mes:
            with contextlib.suppress(Exception):
                mes_u, ano_u = a_int(ultimo.get("mes")), a_int(ultimo.get("anio"))
                if mes_u and ano_u:
                    fecha_mes = f"{ano_u}-{mes_u:02d}-{calendar.monthrange(ano_u, mes_u)[1]:02d}"
        if fecha_mes:
            fecha_hasta = fecha_mes

    valor_15_dias = total_ingresos / 24 if total_ingresos > 0 else 0.0
    valor_dia = valor_15_dias / 15 if valor_15_dias > 0 else 0.0

    # Fallback para pagadas históricas sin vac_calculo: usar lo guardado en el registro.
    if total_ingresos == 0 and tipo == "pagada":
        stored_total = a_float(vac.get("total_periodo"))
        stored_vc = a_float(vac.get("vacaciones_calc"))
        stored_val_vac = a_float(vac.get("valor_vacaciones"))
        if stored_total > 0:
            total_ingresos, valor_15_dias = stored_total, stored_total / 24
        elif stored_vc > 0:
            valor_15_dias, total_ingresos = stored_vc, stored_vc * 24
        elif stored_val_vac > 0:
            dias_pag = a_int(vac.get("dias_tomados"))
            if dias_pag > 0:
                valor_dia_est = stored_val_vac / dias_pag
                valor_15_dias, total_ingresos = valor_dia_est * 15, valor_dia_est * 15 * 24
            else:
                valor_15_dias, total_ingresos = stored_val_vac, stored_val_vac * 24
        valor_dia = valor_15_dias / 15 if valor_15_dias > 0 else 0.0

    dias_gozados_periodo = get_dias_gozados_periodo(cedula, periodo_completo) if periodo_completo else 0
    anticipo = a_float(vac.get("anticipo"))
    dias_este_registro = a_int(vac.get("dias_tomados"))

    if tipo == "pagada" and dias_este_registro > 0:
        base_dias = max(0, 15 - dias_gozados_periodo)
        dias_adicionales_efectivos = max(0, dias_este_registro - base_dias)
    else:
        dias_adicionales_efectivos = dias_adicionales

    dias_goce_derecho = 15 + dias_adicionales
    return {
        "cedula": cedula, "nombre": nombre_completo, "cargo": empleado.get("cargo") or "",
        "area": empleado.get("departamento") or "", "fecha_ingreso": fecha_ingreso,
        "vacacion_id": vac_id, "empleado_id": empleado.get("cod_empleado") or cedula,
        "tipo": tipo, "periodo": periodo_completo, "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta,
        "meses_detalle": meses_detalle, "subtotal": round(total_ingresos, 2),
        "valor_15_dias": round(valor_15_dias, 2), "dias_basicos": 15,
        "dias_adicionales": dias_adicionales_efectivos if tipo == "pagada" else dias_adicionales,
        "dias_gozados": dias_este_registro if tipo == "gozada" else dias_gozados_periodo,
        "dias_gozados_periodo": dias_gozados_periodo,
        "dias_a_pagar": (dias_este_registro if tipo == "pagada" and dias_este_registro > 0
                         else max(0, 15 + dias_adicionales - dias_gozados_periodo)),
        "valor_dia": round(valor_dia, 4),
        "valor_adicionales": round(dias_adicionales_efectivos * valor_dia, 2),
        "valor_gozados": round(dias_gozados_periodo * valor_dia, 2), "anticipo": round(anticipo, 2),
        "total_pagar": a_float(vac.get("total_pagar")),
        "forma_pago": vac.get("forma_pago") or "", "banco": vac.get("banco") or "",
        "cta_cte_no": vac.get("cta_cte_no") or "", "cheque_no": vac.get("no_cheque") or "",
        "fecha_pago": vac.get("fecha_pago") or "",
        "dias_goce": dias_goce_derecho, "dias_este_goce": dias_este_registro,
        "dias_pendientes": max(0, dias_goce_derecho - dias_gozados_periodo),
        "observaciones": vac.get("observaciones") or "",
    }


def qr_texto(data: dict) -> str:
    """Contenido exacto del QR del comprobante (mismo formato que
    `src/pdf_generator.py::_make_qr`, NO json, NO url — texto plano `|`-separado):
    `ID:<empleado_id>|CED:<cedula>|<nombre>|PER:<periodo>|VAL:<total formateado, si hay>`.
    Único punto de verdad de ese formato — no reimplementar en `core/pdf/`."""
    valor = data.get("total_pagar") or data.get("valor_vacaciones") or data.get("vacaciones_calc") or ""
    valor_str = f"{float(valor):,.2f}" if valor else ""
    parts = [
        f"ID:{data.get('empleado_id', '')}", f"CED:{data.get('cedula', '')}",
        data.get("nombre", ""), f"PER:{data.get('periodo', '')}",
    ]
    if valor_str:
        parts.append(f"VAL:{valor_str}")
    return "|".join(parts)


# ─── Alertas (períodos pendientes / gozadas sin firmar) ─────────────────────


def get_alertas(cedula: str, fecha_ingreso: str) -> dict:
    """Períodos pendientes + gozadas sin firmar. Porta `model.get_alertas_vacaciones`
    (usado por `app.py::_panel_alertas_vacaciones` / `_confirmar_periodo_prioritario`
    — la UI de confirmación es responsabilidad del state/página, esto solo
    calcula los datos)."""
    pendientes: list[dict] = []
    sin_firmar: list[dict] = []
    if not fecha_ingreso:
        return {"pendientes": pendientes, "sin_firmar": sin_firmar}
    cedula_n = normalizar_cedula(cedula)
    if not cedula_n:
        return {"pendientes": pendientes, "sin_firmar": sin_firmar}

    vac_rows = get_vacaciones_empleado(cedula_n)
    gozados_map: dict[str, int] = {}
    pagados_set: set[str] = set()
    for r in vac_rows:
        per = str(r.get("periodo") or "")
        if r.get("tipo") == "gozada":
            if (r.get("firmado") or "").upper() != "POSITIVO" and r.get("estado_doc") in ("pendiente", "completado"):
                sin_firmar.append({"id": r["id"], "periodo": per, "desde": r.get("desde"),
                                    "hasta": r.get("hasta"), "dias_tomados": a_int(r.get("dias_tomados"))})
            gozados_map[per] = gozados_map.get(per, 0) + a_int(r.get("dias_tomados"))
        else:
            pagados_set.add(per)
    sin_firmar.sort(key=lambda x: (x.get("periodo") or "", x.get("desde") or ""))

    try:
        periodos = periodos_disponibles(fecha_ingreso, n=4)
    except Exception:  # noqa: BLE001
        return {"pendientes": pendientes, "sin_firmar": sin_firmar}

    for pinfo in periodos:
        lbl = pinfo["label"]
        if lbl in pagados_set:
            continue
        gozados = gozados_map.get(lbl, 0)
        if gozados >= 15:
            continue
        dias_adic, _ = calcular_dias_adicionales(fecha_ingreso, pinfo["fin"].strftime("%Y-%m-%d"))
        dias_pend = max(0, 15 + dias_adic - gozados)
        if dias_pend > 0:
            pendientes.append({"periodo": lbl, "dias_pendientes": dias_pend})

    return {"pendientes": pendientes, "sin_firmar": sin_firmar}


def periodos_anteriores_pendientes(cedula: str, fecha_ingreso: str, periodo_actual: str) -> list[dict]:
    """Períodos ANTERIORES a `periodo_actual` (por año de inicio) que aún
    tienen días pendientes. Porta `app.py::_confirmar_periodo_prioritario`
    (la parte de cálculo — la confirmación bloqueante es responsabilidad de
    la UI: si esta lista no está vacía, el state debe preguntar antes de
    guardar, igual que el `messagebox.askyesno` del original)."""
    def _anio_inicio(per: str) -> int:
        try:
            return int(str(per).split("-")[0])
        except (ValueError, IndexError):
            return 0

    alertas = get_alertas(cedula, fecha_ingreso)
    anio_actual = _anio_inicio(periodo_actual)
    return [
        p for p in alertas["pendientes"]
        if p["periodo"] != periodo_actual and _anio_inicio(p["periodo"]) < anio_actual
    ]


# ─── Reportes ────────────────────────────────────────────────────────────────


def _todas_las_filas(query) -> list[dict]:
    """PostgREST corta a 1000 filas: pagina con .range()."""
    filas: list[dict] = []
    paso, desde = 1000, 0
    while True:
        lote = query.range(desde, desde + paso - 1).execute().data or []
        filas.extend(lote)
        if len(lote) < paso:
            return filas
        desde += paso


def fetch_vac_registros(tipo=None, periodo=None, estado=None, fecha_desde=None,
                         fecha_hasta=None, banco=None) -> list[dict]:
    """Todos los vac_registros con filtros, paginado. Porta `fetch_vac_registros` (SB)."""
    sb = supabase_client.get_client()
    cols = ("id,cedula,tipo,periodo,estado_doc,desde,hasta,dias_tomados,fecha_pago,"
            "fecha_comprobante,total_pagar,total_periodo,vacaciones_calc,valor_vacaciones,"
            "dias_adicionales,anticipo,banco,no_cheque,forma_pago,cod_acta,referencia,firmado,observaciones")
    result, last_id, page_size = [], 0, 1000
    while True:
        q = sb.table("vac_registros").select(cols).gt("id", last_id).order("id").limit(page_size)
        if tipo:
            q = q.eq("tipo", tipo)
        if periodo:
            q = q.eq("periodo", periodo)
        if estado:
            q = q.eq("estado_doc", estado)
        if banco:
            q = q.eq("banco", banco)
        rows = q.execute().data or []
        if not rows:
            break
        for r in rows:
            if fecha_desde or fecha_hasta:
                ref = r.get("fecha_pago") or r.get("fecha_comprobante") or ""
                if fecha_desde and ref and ref < fecha_desde:
                    continue
                if fecha_hasta and ref and ref > fecha_hasta:
                    continue
            result.append(r)
        last_id = rows[-1]["id"]
        if len(rows) < page_size:
            break
    return result


def reporte_completo(periodo=None, departamento=None, estado=None) -> list[dict]:
    """Reporte combinado PAGOS + GOCES. Porta `model.get_reporte_completo`."""
    estado_sb = estado if estado in ESTADOS_DOC else None
    rows = fetch_vac_registros(periodo=periodo, estado=estado_sb)
    cedulas = list({r["cedula"] for r in rows if r.get("cedula")})
    emp_data = batch_emp_data(cedulas)
    result = []
    for r in rows:
        emp = emp_data.get(normalizar_cedula(r.get("cedula", "")), {})
        if departamento and emp.get("departamento") != departamento:
            continue
        tipo = r.get("tipo", "")
        result.append({
            "cedula": r.get("cedula"), "apellidos": emp.get("apellidos", ""), "nombres": emp.get("nombres", ""),
            "cargo": emp.get("cargo", ""), "departamento": emp.get("departamento", ""),
            "periodo": r.get("periodo"), "tipo": tipo, "estado_doc": r.get("estado_doc"),
            "desde": r.get("desde"), "hasta": r.get("hasta"), "dias_tomados": a_int(r.get("dias_tomados")),
            "dias_adicionales": a_int(r.get("dias_adicionales")), "total_pagar": a_float(r.get("total_pagar")),
            "anticipo": a_float(r.get("anticipo")) if tipo == "pagada" else 0.0,
            "fecha_pago": r.get("fecha_pago") if tipo == "pagada" else r.get("fecha_comprobante"),
            "banco": r.get("banco") if tipo == "pagada" else "",
            "no_cheque": r.get("no_cheque") if tipo == "pagada" else "",
            "observaciones": r.get("observaciones"),
        })
    result.sort(key=lambda x: (x.get("periodo") or "", x.get("apellidos") or "", x.get("tipo") or ""), reverse=True)
    return result


def reporte_nomina_pagos(periodo=None, fecha_desde=None, fecha_hasta=None, banco=None) -> list[dict]:
    """Reporte de pagadas. Porta `model.get_reporte_nomina_pagos`."""
    rows = fetch_vac_registros(
        tipo="pagada", periodo=periodo, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, banco=banco
    )
    cedulas = list({r["cedula"] for r in rows if r.get("cedula")})
    emp_data = batch_emp_data(cedulas)
    result = []
    for r in rows:
        emp = emp_data.get(normalizar_cedula(r.get("cedula", "")), {})
        result.append({
            "cedula": r.get("cedula"), "apellidos": emp.get("apellidos", ""), "nombres": emp.get("nombres", ""),
            "cargo": emp.get("cargo", ""), "departamento": emp.get("departamento", ""),
            "vac_id": r["id"], "periodo": r.get("periodo"), "fecha_pago": r.get("fecha_pago"),
            "dias_tomados": a_int(r.get("dias_tomados")), "dias_adicionales": a_int(r.get("dias_adicionales")),
            "total_periodo": a_float(r.get("total_periodo")), "vacaciones_calc": a_float(r.get("vacaciones_calc")),
            "valor_vacaciones": a_float(r.get("valor_vacaciones")), "anticipo": a_float(r.get("anticipo")),
            "total_pagar": a_float(r.get("total_pagar")), "banco": r.get("banco"), "no_cheque": r.get("no_cheque"),
            "forma_pago": r.get("forma_pago"), "cod_acta": r.get("cod_acta"),
        })
    result.sort(key=lambda x: (x.get("fecha_pago") or "", x.get("apellidos") or ""), reverse=True)
    return result


def reporte_nomina_gozadas(periodo=None, fecha_desde=None, fecha_hasta=None,
                            departamento=None, estado=None) -> list[dict]:
    """Reporte de gozadas. Porta `model.get_reporte_nomina_gozadas`."""
    rows = fetch_vac_registros(
        tipo="gozada", periodo=periodo, estado=estado, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta
    )
    cedulas = list({r["cedula"] for r in rows if r.get("cedula")})
    emp_data = batch_emp_data(cedulas)
    result = []
    for r in rows:
        emp = emp_data.get(normalizar_cedula(r.get("cedula", "")), {})
        if departamento and emp.get("departamento") != departamento:
            continue
        result.append({
            "cedula": r.get("cedula"), "apellidos": emp.get("apellidos", ""), "nombres": emp.get("nombres", ""),
            "cargo": emp.get("cargo", ""), "departamento": emp.get("departamento", ""),
            "vac_id": r["id"], "periodo": r.get("periodo"), "estado_doc": r.get("estado_doc"),
            "fecha_comprobante": r.get("fecha_comprobante"), "desde": r.get("desde"), "hasta": r.get("hasta"),
            "dias_tomados": a_int(r.get("dias_tomados")), "referencia": r.get("referencia"),
            "firmado": r.get("firmado"), "observaciones": r.get("observaciones"),
        })
    result.sort(key=lambda x: (x.get("fecha_comprobante") or "", x.get("apellidos") or ""), reverse=True)
    return result


def resumen_periodos(tipo: str | None = None) -> list[dict]:
    """Agregado por (periodo, tipo). Porta `model.get_reporte_resumen_periodos`."""
    rows = fetch_vac_registros(tipo=tipo)
    agg: dict[tuple[str, str], dict] = {}
    for r in rows:
        per, tp = r.get("periodo") or "", r.get("tipo") or ""
        if not per:
            continue
        key = (per, tp)
        agg.setdefault(key, {"periodo": per, "tipo": tp, "num_empleados": set(),
                              "num_registros": 0, "total_dias": 0, "total_valor": 0.0, "pendientes": 0})
        a = agg[key]
        a["num_empleados"].add(r.get("cedula", ""))
        a["num_registros"] += 1
        a["total_dias"] += a_int(r.get("dias_tomados"))
        a["total_valor"] += a_float(r.get("total_pagar"))
        if r.get("estado_doc") == "pendiente":
            a["pendientes"] += 1
    result = [
        {"periodo": v["periodo"], "tipo": v["tipo"], "num_empleados": len(v["num_empleados"]),
         "num_registros": v["num_registros"], "total_dias": v["total_dias"],
         "total_valor": round(v["total_valor"], 2), "pendientes": v["pendientes"]}
        for v in agg.values()
    ]
    result.sort(key=lambda x: (x["periodo"], x["tipo"]), reverse=True)
    return result


def reporte_pendientes_global(
    n_periodos: int = 5, solo_15: bool = False, departamento: str | None = None
) -> list[dict]:
    """Días pendientes por empleado × período, para todos los activos. Porta `model.get_reporte_pendientes_global`."""
    empleados = fetch_empleados_activos(departamento=departamento)
    if not empleados:
        return []
    vac_rows = fetch_vac_registros()
    vac_idx: dict[str, dict] = {}
    for r in vac_rows:
        ced, per = r.get("cedula", ""), str(r.get("periodo") or "")
        if not ced or not per:
            continue
        vac_idx.setdefault(ced, {"gozada": {}, "pagada": set()})
        if r.get("tipo") == "gozada":
            vac_idx[ced]["gozada"][per] = vac_idx[ced]["gozada"].get(per, 0) + a_int(r.get("dias_tomados"))
        else:
            vac_idx[ced]["pagada"].add(per)

    resultado = []
    for emp in empleados:
        fi, ced = emp.get("fecha_ingreso") or "", emp.get("cedula", "")
        if not fi:
            continue
        try:
            periodos = periodos_disponibles(fi, n=n_periodos)
        except Exception:  # noqa: BLE001
            continue
        ev = vac_idx.get(ced, {"gozada": {}, "pagada": set()})
        for pinfo in periodos:
            lbl, per_fin = pinfo["label"], pinfo["fin"].strftime("%Y-%m-%d")
            if lbl in ev["pagada"]:
                continue
            dias_adic, _ = calcular_dias_adicionales(fi, per_fin)
            derecho = 15 if solo_15 else (15 + dias_adic)
            gozados = ev["gozada"].get(lbl, 0)
            pendientes = max(0, derecho - gozados)
            if pendientes > 0:
                resultado.append({
                    "cedula": ced, "apellidos": emp.get("apellidos", ""), "nombres": emp.get("nombres", ""),
                    "cargo": emp.get("cargo", ""), "departamento": emp.get("departamento", ""),
                    "fecha_ingreso": fi, "periodo": lbl, "dias_derecho": derecho, "dias_gozados": gozados,
                    "dias_adicionales": 0 if solo_15 else dias_adic, "dias_pendientes": pendientes,
                })
    return resultado


def dashboard_stats() -> dict:
    """Estadísticas del dashboard vía queries count='exact'. Porta `model.get_dashboard_stats`."""
    sb = supabase_client.get_client()
    anio = str(date.today().year)
    fi = f"{anio}-01-01"

    def _count(q) -> int:
        try:
            return q.execute().count or 0
        except Exception as e:  # noqa: BLE001
            log.warning("dashboard count error: %s", e)
            return 0

    def _sel():
        return sb.table("vac_registros").select("id", count=CountMethod.exact)

    n_activos = get_count_activos()
    n_sin_firmar = _count(
        _sel().eq("tipo", "gozada").in_("estado_doc", ["pendiente", "completado"])
    ) - _count(
        _sel().eq("tipo", "gozada")
        .in_("estado_doc", ["pendiente", "completado"]).eq("firmado", "POSITIVO")
    )
    n_pagadas_sf = _count(
        _sel().eq("tipo", "pagada").eq("estado_doc", "completado")
    ) - _count(
        _sel().eq("tipo", "pagada").eq("estado_doc", "completado").eq("firmado", "POSITIVO")
    )
    n_gozadas_anio = _count(_sel().eq("tipo", "gozada").gte("desde", fi))
    n_pagadas_anio = _count(_sel().eq("tipo", "pagada").gte("fecha_pago", fi))

    try:
        cols = "id,cedula,tipo,periodo,desde,hasta,dias_tomados,estado_doc,firmado"
        sf_goz = sb.table("vac_registros").select(cols).eq("tipo", "gozada").in_(
            "estado_doc", ["pendiente", "completado"]).order("id", desc=True).limit(10).execute().data or []
        sf_pag = sb.table("vac_registros").select(cols).eq("tipo", "pagada").eq(
            "estado_doc", "completado").order("id", desc=True).limit(10).execute().data or []
        sin_firmar_raw = [r for r in sf_goz + sf_pag if (r.get("firmado") or "").upper() != "POSITIVO"]
        sin_firmar_raw.sort(key=lambda x: str(x.get("desde") or x.get("id") or 0), reverse=True)
        cedulas_t5 = list({r["cedula"] for r in sin_firmar_raw[:10] if r.get("cedula")})
        emp_t5 = batch_emp_data(cedulas_t5)
        top5_sf = [
            {
                "cedula": r.get("cedula"),
                "nombre": (f"{emp_t5.get(r.get('cedula',''), {}).get('apellidos','')} "
                           f"{emp_t5.get(r.get('cedula',''), {}).get('nombres','')}").strip() or r.get("cedula"),
                "tipo": r.get("tipo"), "periodo": r.get("periodo"), "desde": r.get("desde"),
                "hasta": r.get("hasta"), "dias": a_int(r.get("dias_tomados")), "vac_id": r["id"],
            }
            for r in sin_firmar_raw[:5]
        ]
    except Exception as e:  # noqa: BLE001
        log.warning("dashboard top5: %s", e)
        top5_sf = []

    try:
        anio_hoy = date.today().year
        periodos_check = [
            f"{anio_hoy - 1}-{anio_hoy}", f"{anio_hoy - 2}-{anio_hoy - 1}", f"{anio_hoy - 3}-{anio_hoy - 2}",
        ]
        pag_rows = (sb.table("vac_registros").select("cedula,periodo").eq("tipo", "pagada")
                    .in_("periodo", periodos_check).limit(5000).execute().data or [])
        pagadas_por_per: dict[str, set] = {}
        for r in pag_rows:
            per, ced = r.get("periodo") or "", r.get("cedula") or ""
            if per and ced:
                pagadas_por_per.setdefault(per, set()).add(ced)
        pendientes_periodos = []
        for per in periodos_check:
            anio_base = int(per.split("-")[0])
            corte = f"{anio_base + 1}-12-31"
            n_elegibles = _count(
                sb.table("rpemplea").select("empleado", count=CountMethod.exact)
                .eq("codemp", "10").eq("codsuc", "10").eq("estado", "ACT").lt("fecha_ing", corte)
            )
            n_pagados = len(pagadas_por_per.get(per, set()))
            n_pendientes = max(0, n_elegibles - n_pagados)
            if n_pendientes > 0:
                pendientes_periodos.append(
                    {"periodo": per, "n_empleados": n_pendientes, "total_dias": n_pendientes * 15}
                )
    except Exception as e:  # noqa: BLE001
        log.warning("dashboard pendientes_periodos: %s", e)
        pendientes_periodos = []

    return {
        "n_activos": n_activos, "n_sin_firmar": n_sin_firmar, "n_pagadas_sin_firmar": n_pagadas_sf,
        "n_gozadas_anio": n_gozadas_anio, "n_pagadas_anio": n_pagadas_anio,
        "top5_sin_firmar": top5_sf, "pendientes_periodos": pendientes_periodos,
    }


def sin_firmar_activos() -> list[dict]:
    """Gozadas y pagadas sin firmar de empleados activos. Porta `model.get_sin_firmar_activos`."""
    sb = supabase_client.get_client()
    try:
        cols = "id,cedula,tipo,periodo,desde,hasta,dias_tomados,firmado,estado_doc"
        gozadas = (sb.table("vac_registros").select(cols).eq("tipo", "gozada")
                   .in_("estado_doc", ["pendiente", "completado"])
                   .order("id", desc=True).limit(2000).execute().data or [])
        pagadas = (sb.table("vac_registros").select(cols).eq("tipo", "pagada")
                   .eq("estado_doc", "completado").order("id", desc=True).limit(2000).execute().data or [])
        pendientes = [r for r in gozadas + pagadas if (r.get("firmado") or "").upper() != "POSITIVO"]
        if not pendientes:
            return []
        cedulas = list({r["cedula"] for r in pendientes if r.get("cedula")})
        emp_data = batch_emp_data(cedulas)
        result = []
        for r in pendientes:
            ced = r.get("cedula", "")
            emp = emp_data.get(ced, {})
            if str(emp.get("estado") or "").upper() in ("LIQ", "SUS"):
                continue
            result.append({
                "cedula": ced, "apellidos": emp.get("apellidos", ""), "nombres": emp.get("nombres", ""),
                "cargo": emp.get("cargo", ""), "departamento": emp.get("departamento", ""),
                "vac_id": r["id"], "tipo": r.get("tipo", ""), "periodo": r.get("periodo", ""),
                "desde": r.get("desde", ""), "hasta": r.get("hasta", ""), "dias_tomados": a_int(r.get("dias_tomados")),
            })
        result.sort(
            key=lambda x: (x.get("apellidos", ""), x.get("nombres", ""), x.get("tipo", ""), x.get("periodo", ""))
        )
        return result
    except Exception as e:  # noqa: BLE001
        log.error("sin_firmar_activos: %s", e)
        return []


def periodos_bd() -> list[str]:
    """Períodos distintos registrados, paginado. Porta `model.get_periodos_bd`."""
    sb = supabase_client.get_client()
    try:
        periodos: set[str] = set()
        last_id, page_size = 0, 1000
        while True:
            rows = (sb.table("vac_registros").select("id,periodo").gt("id", last_id)
                    .order("id").limit(page_size).execute().data or [])
            if not rows:
                break
            for r in rows:
                if r.get("periodo"):
                    periodos.add(r["periodo"])
            last_id = rows[-1]["id"]
            if len(rows) < page_size:
                break
        return sorted(periodos, reverse=True)
    except Exception as e:  # noqa: BLE001
        log.warning("periodos_bd: %s", e)
        return []
