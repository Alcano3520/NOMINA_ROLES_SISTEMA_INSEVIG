"""Consulta de préstamos (CLASE 205). Solo lectura.

Porta `prestamos/HISTORIAL_PRESTAMOS_10.pyw`. Combina:
  - SQL Server RPINGDES (vivo) / RPHISTOR (cerrado), CLASE 205
  - LoanHistoryMigrated (Postgres app) — lo que antes vivía en el SQLite sobre SMB

Cero acceso a SMB / SQLite en runtime.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlmodel

from core.config import get_settings
from core.db import appdb, sqlserver, supabase_client
from core.db.health import FUENTE_SUPABASE
from core.db.models import LoanHistoryMigrated
from core.utils import a_float, normalizar_cedula

CLASE_PRESTAMO = 205

# NUMERO de RPHISTOR ya migrados al SQLite (herencia de obtener_numeros_excluir()).
_NUMEROS_MIGRADOS = frozenset({
    "27958", "28215", "28592", "29301", "29633", "29790", "30062", "30437",
    "30691", "30928", "31777", "32211", "32721", "33089", "33634", "33944",
    "33964", "34483", "34492", "34797", "35168", "35616", "35923",
})


def _num_norm(v: object) -> str:
    """NUMERO canónico. En estas tablas `NUMERO` es numérico (float), así que
    `str(x)` puede dar `'35923.0'`; sin normalizar, la exclusión de
    `_NUMEROS_MIGRADOS` fallaba en silencio y esos movimientos se contaban de
    más (doble conteo cuando el SQLite ya está migrado)."""
    s = str(v or "").strip()
    try:
        return str(int(float(s)))
    except (ValueError, TypeError):
        return s


@dataclass
class SaldoPrestamo:
    empleado: str
    apellidos_nombres: str
    cedula: str
    saldo: float
    situacion: str = ""   # RPEMPLEA.SITUACION ('ACT' = activo) — para el filtro "Act."


@dataclass
class MovimientoPrestamo:
    fecha: str
    valor: float                 # valor crudo de la tabla (normalmente > 0)
    concepto: str
    numero: str
    origen: str                  # RPINGDES | RPHISTOR | MIGRADO
    tipo: str = "pago"           # pendiente (RPINGDES) | pago (RPHISTOR/egreso migrado)
    #                              | desembolso (ingreso migrado)
    es_cuadre: bool = False


# ── Saldos (todos los empleados) ─────────────────────────────────────────────


def saldos(fuente: str) -> list[SaldoPrestamo]:
    if fuente == FUENTE_SUPABASE:
        return _saldos_supabase()
    return _saldos_sqlserver()


def _saldos_sqlserver() -> list[SaldoPrestamo]:
    flt = get_settings().sqlserver_filter
    filas = sqlserver.filas(
        f"""SELECT i.EMPLEADO,
                   RTRIM(e.APELLIDOS) + ' ' + RTRIM(e.NOMBRES) AS NOMBRE,
                   e.CEDULA,
                   ISNULL(e.SITUACION, '') AS SITUACION,
                   ISNULL(SUM(i.VALOR), 0) AS SALDO
            FROM [insevig].[dbo].[RPINGDES] i
            LEFT JOIN [insevig].[dbo].[RPEMPLEA] e ON e.EMPLEADO = i.EMPLEADO
            WHERE i.CLASE = {CLASE_PRESTAMO} AND {flt.replace('CODEMP', 'i.CODEMP').replace('CODSUC', 'i.CODSUC')}
            GROUP BY i.EMPLEADO, RTRIM(e.APELLIDOS) + ' ' + RTRIM(e.NOMBRES), e.CEDULA, ISNULL(e.SITUACION, '')
            HAVING ISNULL(SUM(i.VALOR), 0) <> 0
            ORDER BY SALDO DESC"""
    )
    return [
        SaldoPrestamo(
            empleado=str(r["EMPLEADO"]).strip(),
            apellidos_nombres=(r.get("NOMBRE") or "").strip(),
            cedula=normalizar_cedula(r.get("CEDULA")),
            saldo=round(a_float(r.get("SALDO")), 2),
            situacion=str(r.get("SITUACION") or "").strip().upper(),
        )
        for r in filas
    ]


def _saldos_supabase() -> list[SaldoPrestamo]:
    sb = supabase_client.get_client()
    r = (
        sb.table("rpingdesres")
        .select("empleado,valor")
        .eq("codemp", "10")
        .eq("clase", CLASE_PRESTAMO)
        .execute()
    )
    por_emp: dict[str, float] = {}
    for row in r.data or []:
        cod = str(row["empleado"]).strip()
        por_emp[cod] = por_emp.get(cod, 0.0) + a_float(row.get("valor"))
    emps = {
        str(x["empleado"]).strip(): x
        for x in (
            sb.table("rpemplea").select("empleado,apellidos,nombres,cedula,situacion")
            .eq("codemp", "10").execute().data
            or []
        )
    }
    out = []
    for cod, saldo in por_emp.items():
        if round(saldo, 2) == 0:
            continue
        e = emps.get(cod, {})
        nombre = f"{(e.get('apellidos') or '').strip()} {(e.get('nombres') or '').strip()}".strip()
        out.append(SaldoPrestamo(
            cod, nombre, normalizar_cedula(e.get("cedula")), round(saldo, 2),
            str(e.get("situacion") or "").strip().upper(),
        ))
    out.sort(key=lambda s: s.saldo, reverse=True)
    return out


# ── Historial de un empleado ─────────────────────────────────────────────────


def historial_empleado(codigo: str, fuente: str) -> list[MovimientoPrestamo]:
    movs: list[MovimientoPrestamo] = list(_historial_migrado(codigo))
    if fuente == FUENTE_SUPABASE:
        movs += _historial_supabase(codigo)
    else:
        movs += _historial_sqlserver(codigo)
    movs.sort(key=lambda m: m.fecha)
    return movs


def _historial_migrado(codigo: str) -> list[MovimientoPrestamo]:
    with appdb.session() as s:
        filas = s.exec(
            sqlmodel.select(LoanHistoryMigrated).where(LoanHistoryMigrated.empleado == str(codigo))
        ).all()
    out = []
    for f in filas:
        es_desembolso = bool(f.ingreso) and not f.egreso
        out.append(
            MovimientoPrestamo(
                fecha=f.fecha,
                valor=round(abs(f.ingreso or f.egreso), 2),
                concepto=f.concepto or "",
                numero=f"MIG_{f.numero_fila}",
                origen="MIGRADO",
                tipo="desembolso" if es_desembolso else "pago",
                es_cuadre=f.tipo in ("CUADRE", "CRUZE"),
            )
        )
    return out


def _historial_sqlserver(codigo: str) -> list[MovimientoPrestamo]:
    flt = get_settings().sqlserver_filter
    out: list[MovimientoPrestamo] = []
    for tabla, origen in (("RPINGDES", "RPINGDES"), ("RPHISTOR", "RPHISTOR")):
        filas = sqlserver.filas(
            f"""SELECT [NUMERO],[FECHA],[VALOR],[CONCEPTO],[OBSERV]
                FROM [insevig].[dbo].[{tabla}]
                WHERE {flt} AND [EMPLEADO] = ? AND [CLASE] = {CLASE_PRESTAMO}
                ORDER BY [NUMERO], [FECHA]""",
            (str(codigo),),
        )
        for r in filas:
            num = _num_norm(r.get("NUMERO"))
            if origen == "RPHISTOR" and num in _NUMEROS_MIGRADOS:
                continue
            fecha = str(r.get("FECHA") or "")[:10]
            out.append(
                MovimientoPrestamo(
                    fecha=fecha,
                    valor=round(a_float(r.get("VALOR")), 2),
                    concepto=(r.get("CONCEPTO") or r.get("OBSERV") or "").strip(),
                    numero=num,
                    origen=origen,
                    tipo="pendiente" if origen == "RPINGDES" else "pago",
                )
            )
    return out


def _historial_supabase(codigo: str) -> list[MovimientoPrestamo]:
    sb = supabase_client.get_client()
    out: list[MovimientoPrestamo] = []
    for tabla, origen in (("rpingdesres", "RPINGDES"), ("rphistor_temp", "RPHISTOR")):
        r = (
            sb.table(tabla)
            .select("numero,fecha,valor,concepto,observ")
            .eq("codemp", "10")
            .eq("empleado", str(codigo))
            .eq("clase", CLASE_PRESTAMO)
            .execute()
        )
        for row in r.data or []:
            num = _num_norm(row.get("numero"))
            if origen == "RPHISTOR" and num in _NUMEROS_MIGRADOS:
                continue
            out.append(
                MovimientoPrestamo(
                    fecha=str(row.get("fecha") or "")[:10],
                    valor=round(a_float(row.get("valor")), 2),
                    concepto=(row.get("concepto") or row.get("observ") or "").strip(),
                    numero=num,
                    origen=origen,
                    tipo="pendiente" if origen == "RPINGDES" else "pago",
                )
            )
    return out


def saldo_total(codigo: str, fuente: str) -> float:
    """Saldo pendiente de préstamos del empleado = suma de lo que sigue en
    RPINGDES (`tipo == "pendiente"`), igual que `obtener_datos_rpingdes_combinados`
    del `.pyw`. Los movimientos de RPHISTOR son pagos ya hechos, NO suman al saldo."""
    return round(
        sum(m.valor for m in historial_empleado(codigo, fuente) if m.tipo == "pendiente"), 2
    )


@dataclass
class ResumenPrestamo:
    numero: str
    desde: str
    hasta: str
    prestado: float       # monto desembolsado (real si viene del histórico migrado;
    #                       si no, sintético = abonado + saldo, como el `.pyw`)
    abonado: float        # suma de pagos (movimientos de RPHISTOR / egresos migrados)
    saldo: float          # pendiente = suma de RPINGDES de ese número
    cuotas: int
    cuota_promedio: float = 0.0
    meses_brecha: int = 0          # meses sin descuento entre la primera y última cuota
    cancelado: bool = False
    meses_para_cancelar: int = 0   # estimación: saldo / cuota_promedio
    estado: str = ""              # texto legible


def _meses_brecha(claves: list[tuple[int, int]]) -> int:
    """Meses sin descuento entre cuotas consecutivas (como el legado)."""
    faltantes = 0
    for i in range(1, len(claves)):
        py, pm = claves[i - 1]
        cy, cm = claves[i]
        diff = (cy - py) * 12 + (cm - pm)
        if diff > 1:
            faltantes += diff - 1
    return faltantes


def agrupar_por_numero(movs: list[MovimientoPrestamo]) -> list[ResumenPrestamo]:
    """Agrupa los movimientos por NUMERO de préstamo con el modelo del `.pyw`:
    `saldo` = suma de RPINGDES (`tipo == "pendiente"`); `abonado` = suma de pagos
    (RPHISTOR / egresos migrados); `prestado` = desembolso real si lo hay, si no
    el sintético `abonado + saldo`.
    """
    import math

    grupos: dict[str, list[MovimientoPrestamo]] = {}
    for m in movs:
        grupos.setdefault(m.numero or "(sin nº)", []).append(m)
    out: list[ResumenPrestamo] = []
    for num, ms in grupos.items():
        pagos = [x for x in ms if x.tipo == "pago"]
        fechas = sorted(x.fecha for x in pagos if x.fecha) or sorted(x.fecha for x in ms if x.fecha)
        abonado = round(sum(x.valor for x in pagos), 2)
        saldo = round(sum(x.valor for x in ms if x.tipo == "pendiente"), 2)
        desembolso = round(sum(x.valor for x in ms if x.tipo == "desembolso"), 2)
        prestado = desembolso if desembolso else round(abonado + saldo, 2)
        n_cuotas = len(pagos)
        cuota_prom = round(abonado / n_cuotas, 2) if n_cuotas else 0.0
        claves = sorted({(int(x.fecha[:4]), int(x.fecha[5:7])) for x in pagos if len(x.fecha) >= 7})
        brecha = _meses_brecha(claves)
        cancelado = saldo <= 0.01
        meses_rest = math.ceil(saldo / cuota_prom) if (cuota_prom > 0 and not cancelado) else 0
        if cancelado:
            estado = f"Cancelado · {n_cuotas} cuotas de ~{cuota_prom:,.2f}"
        else:
            cont = "pagos continuos" if not brecha else f"{brecha} mes(es) sin descuento"
            estado = (
                f"Pendiente {saldo:,.2f} · ~{meses_rest} mes(es) para cancelar "
                f"({n_cuotas} cuotas ~{cuota_prom:,.2f}/mes, {cont})"
            )
        out.append(
            ResumenPrestamo(
                numero=num,
                desde=fechas[0] if fechas else "",
                hasta=fechas[-1] if fechas else "",
                prestado=prestado, abonado=abonado, saldo=saldo, cuotas=n_cuotas,
                cuota_promedio=cuota_prom, meses_brecha=brecha, cancelado=cancelado,
                meses_para_cancelar=meses_rest, estado=estado,
            )
        )
    out.sort(key=lambda r: r.hasta, reverse=True)
    return out


def movimientos_de_numero(movs: list[MovimientoPrestamo], numero: str) -> list[MovimientoPrestamo]:
    """Los movimientos individuales de un préstamo (para el detalle por fila)."""
    return sorted((m for m in movs if (m.numero or "(sin nº)") == numero), key=lambda m: m.fecha)


def filtrar_movimientos(
    movs: list[dict],
    *,
    tipo: str = "",       # "" | "pago" | "pendiente" | "desembolso"
    origen: str = "",     # "" | RPINGDES | RPHISTOR | MIGRADO
    numero: str = "",     # substring del N°
    texto: str = "",      # substring del concepto/observación
    desde: str = "",      # fecha ISO YYYY-MM-DD
    hasta: str = "",
    monto_min: float | None = None,   # sobre el valor absoluto
    monto_max: float | None = None,
) -> list[dict]:
    """Filtra la lista de movimientos (dicts como los de `MovimientoPrestamo`),
    con los mismos criterios que `aplicar_filtros` del `.pyw`."""
    num = numero.strip()
    txt = texto.strip().lower()
    orig = origen.strip().upper()
    # compatibilidad: "ingreso"/"egreso" del filtro viejo
    tp = {"ingreso": "pendiente", "egreso": "pago"}.get(tipo.strip(), tipo.strip())

    def _ok(m: dict) -> bool:
        v = a_float(m.get("valor"))
        if tp and str(m.get("tipo", "pago")) != tp:
            return False
        if orig and str(m.get("origen", "")).upper() != orig:
            return False
        if num and num not in str(m.get("numero", "")):
            return False
        if txt and txt not in str(m.get("concepto", "")).lower():
            return False
        f = str(m.get("fecha", ""))[:10]
        if desde and f < desde:
            return False
        if hasta and f > hasta:
            return False
        av = abs(v)
        if monto_min is not None and av < monto_min:
            return False
        if monto_max is not None and av > monto_max:  # noqa: SIM103
            return False
        return True

    return [m for m in movs if _ok(m)]


# ── Filas del historial tal como las pinta el árbol del `.pyw` ───────────────
#
# El árbol de `HISTORIAL_PRESTAMOS_10.pyw` NO muestra los movimientos crudos:
# reconstruye, por cada NÚMERO de préstamo, una fila INGRESO sintética (el
# desembolso) y una fila EGRESO por cada descuento de nómina; después ordena
# todo por fecha y calcula un SALDO progresivo (+ingreso / -egreso). Esto porta
# esa lógica (`buscar_prestamos` + `mostrar_movimientos_en_tree`).


@dataclass
class FilaHistorial:
    posicion: int          # columna "#" (1-based, sobre las filas visibles)
    fecha: str             # ISO YYYY-MM-DD (ordenable)
    fecha_fmt: str         # DD/MM/AAAA para mostrar (como `formatear_fecha`)
    ingreso: float         # columna INGRESO ($); 0.0 si la fila es egreso
    egreso: float          # columna EGRESO ($); 0.0 si la fila es ingreso
    numero: str            # NÚMERO, con sufijo " [H]" si es histórico
    observacion: str       # observación completa
    tipo: str              # "INGRESO" | "EGRESO"
    saldo: float           # SALDO progresivo tras esta fila
    historico: bool        # viene del histórico (RPHISTOR / migrado)
    origen: str            # RPINGDES | RPHISTOR | MIGRADO


@dataclass
class InfoPrestamosEmpleado:
    nombre: str
    cedula: str
    saldo_total: float     # suma de lo pendiente en RPINGDES
    historicos: int        # nº de movimientos que vienen del histórico
    total: int             # nº de filas mostradas


def _datos_empleado_prestamos(codigo: str, fuente: str) -> tuple[str, str]:
    """(nombre, cédula) de RPEMPLEA — como `obtener_datos_empleado()` del `.pyw`."""
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        r = (
            sb.table("rpemplea").select("apellidos,nombres,cedula")
            .eq("codemp", "10").eq("empleado", str(codigo)).limit(1).execute()
        )
        row = (r.data or [{}])[0]
        nombre = f"{(row.get('apellidos') or '').strip()} {(row.get('nombres') or '').strip()}".strip()
        return nombre, normalizar_cedula(row.get("cedula"))
    flt = get_settings().sqlserver_filter
    filas = sqlserver.filas(
        f"""SELECT RTRIM(APELLIDOS) + ' ' + RTRIM(NOMBRES) AS NOMBRE, CEDULA
            FROM [insevig].[dbo].[RPEMPLEA]
            WHERE {flt} AND [EMPLEADO] = ?""",
        (str(codigo),),
    )
    if not filas:
        return "", ""
    return (filas[0].get("NOMBRE") or "").strip(), normalizar_cedula(filas[0].get("CEDULA"))


_ORIGEN_HIST = ("RPHISTOR", "MIGRADO")


def historial_display(codigo: str, fuente: str) -> tuple[list[dict], InfoPrestamosEmpleado]:
    """Filas crudas (sin numerar) del historial + info del empleado.

    Cada fila: ``{fecha, tipo, valor, numero, observacion, origen, historico}``.
    Pasar por `numerar_historial()` (y opcionalmente `filtrar_historial()`) para
    obtener las `FilaHistorial` finales con `#` y `saldo` progresivo.
    """
    movs = historial_empleado(codigo, fuente)
    nombre, cedula = _datos_empleado_prestamos(codigo, fuente)

    # egresos marcados como cuadre → si un INGRESO sintético coincide en monto,
    # se oculta (igual que el `.pyw`, que salta las filas ES_CUADRE)
    valores_cuadre = {round(m.valor, 2) for m in movs if m.es_cuadre and m.tipo == "pago"}

    grupos: dict[str, list[MovimientoPrestamo]] = {}
    for m in movs:
        grupos.setdefault(m.numero or "(sin nº)", []).append(m)

    crudas: list[dict] = []
    for num, ms in grupos.items():
        pagos = [x for x in ms if x.tipo == "pago" and not x.es_cuadre]
        pendientes = [x for x in ms if x.tipo == "pendiente"]
        desembolsos = [x for x in ms if x.tipo == "desembolso"]
        historico_grupo = any(x.origen in _ORIGEN_HIST for x in ms)

        if desembolsos:
            for d in desembolsos:
                crudas.append({
                    "fecha": d.fecha, "tipo": "INGRESO", "valor": round(d.valor, 2),
                    "numero": num, "observacion": d.concepto, "origen": d.origen,
                    "historico": True,
                })
        else:
            saldo_num = round(sum(x.valor for x in pendientes), 2)
            total_pagado = round(sum(x.valor for x in pagos), 2)
            valor_prestamo = round(total_pagado + saldo_num, 2)
            if valor_prestamo > 0 and valor_prestamo not in valores_cuadre:
                fechas = sorted(x.fecha for x in (pendientes or ms) if x.fecha)
                obs = next((x.concepto for x in [*pendientes, *pagos] if x.concepto), "")
                crudas.append({
                    "fecha": fechas[0] if fechas else "",
                    "tipo": "INGRESO", "valor": valor_prestamo, "numero": num,
                    "observacion": obs,
                    "origen": "RPHISTOR" if historico_grupo else "RPINGDES",
                    "historico": historico_grupo,
                })

        for p in pagos:
            crudas.append({
                "fecha": p.fecha, "tipo": "EGRESO", "valor": round(p.valor, 2),
                "numero": num, "observacion": p.concepto, "origen": p.origen,
                "historico": p.origen in _ORIGEN_HIST,
            })

    # ingreso antes que egreso a igualdad de fecha (para un saldo progresivo sensato)
    crudas.sort(key=lambda d: (d["fecha"] or "9999", 0 if d["tipo"] == "INGRESO" else 1))

    info = InfoPrestamosEmpleado(
        nombre=nombre, cedula=cedula,
        saldo_total=round(sum(x.valor for x in movs if x.tipo == "pendiente"), 2),
        historicos=sum(1 for x in movs if x.origen in _ORIGEN_HIST),
        total=len(crudas),
    )
    return crudas, info


def filtrar_historial(
    crudas: list[dict],
    *,
    tipo: str = "",       # "" | "INGRESO" | "EGRESO"
    origen: str = "",     # "" | "SISTEMA" | "HISTORICO"
    numero: str = "",
    texto: str = "",
    desde: str = "",      # ISO YYYY-MM-DD
    hasta: str = "",
    monto_min: float | None = None,
    monto_max: float | None = None,
) -> list[dict]:
    """Filtra las filas crudas con los criterios de `aplicar_filtros()` del `.pyw`."""
    tp, org = tipo.strip().upper(), origen.strip().upper()
    num, txt = numero.strip(), texto.strip().lower()

    def _ok(d: dict) -> bool:
        if tp and d["tipo"] != tp:
            return False
        if org == "SISTEMA" and d["historico"]:
            return False
        if org == "HISTORICO" and not d["historico"]:
            return False
        if num and num not in str(d["numero"]):
            return False
        if txt and txt not in str(d.get("observacion", "")).lower():
            return False
        f = str(d.get("fecha", ""))[:10]
        if desde and f < desde:
            return False
        if hasta and f > hasta:
            return False
        v = abs(a_float(d.get("valor")))
        if monto_min is not None and v < monto_min:
            return False
        if monto_max is not None and v > monto_max:  # noqa: SIM103
            return False
        return True

    return [d for d in crudas if _ok(d)]


def numerar_historial(crudas: list[dict]) -> list[FilaHistorial]:
    """Añade `#` y SALDO progresivo (como `mostrar_movimientos_en_tree`).

    El saldo se recalcula sobre las filas que se pasan: si vienen ya filtradas,
    `#` y SALDO reflejan el subconjunto — mismo comportamiento que el `.pyw`.
    """
    out: list[FilaHistorial] = []
    saldo = 0.0
    for i, d in enumerate(crudas, 1):
        val = round(a_float(d.get("valor")), 2)
        if d["tipo"] == "INGRESO":
            saldo = round(saldo + val, 2)
            ingreso, egreso = val, 0.0
        else:
            saldo = round(saldo - val, 2)
            ingreso, egreso = 0.0, val
        fecha = str(d.get("fecha", ""))
        iso = fecha[:10]
        fecha_fmt = f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if len(iso) == 10 else fecha
        out.append(FilaHistorial(
            posicion=i, fecha=fecha, fecha_fmt=fecha_fmt,
            ingreso=ingreso, egreso=egreso,
            numero=str(d["numero"]) + (" [H]" if d.get("historico") else ""),
            observacion=str(d.get("observacion", "") or ""),
            tipo=d["tipo"], saldo=saldo,
            historico=bool(d.get("historico")), origen=str(d.get("origen", "")),
        ))
    return out
