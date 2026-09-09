"""Cálculos de negocio del módulo Faltas / Permisos / Suspensiones / Restas de Horas.

Trasplante **verbatim** de `sistema_sanciones_RRHH/nucleo_modular/faltas_calculo.py`
(origen legado: `gestion_faltas.py`). Cero I/O, cero SQL, cero Tkinter.

Regla de la migración (`PROMPT_IMPLEMENTAR_TODO_NOMINA.md` §1.3): los bugs del
legado NO se corrigen en silencio — cada uno lleva su nota `# LEGADO: <bug> —
[replicado | corregido]: <por qué>` y los que son decisión de negocio están
escalados al usuario (ver `docs/modulos/faltas.md`).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Constantes de negocio (idénticas a gestion_faltas.py)
# ---------------------------------------------------------------------------

HORAS_POR_FALTA = 8
FACTOR_CONV_50A100 = 0.75
MAX_FALTAS = 3

# LEGADO: "SUSPENSION" (sin tilde) vs "SUSPENSIÓN" (con tilde) — replicado.
# El botón "✓ VALIDAR" (masivo) usa este set SIN tilde; "✔ REGISTRAR TODO" usa
# TIPOS_REGISTRO_MASIVO CON tilde. VALIDAR rechaza como "tipo inválido" filas de
# tipo SUSPENSIÓN que REGISTRAR TODO sí aceptaría. Decisión de negocio pendiente
# del usuario (bug #1 de faltas.md).
TIPOS_VALIDACION_MASIVA = ("FALTA", "PERMISO", "SUSPENSION")

TIPOS_REGISTRO_MASIVO = ("FALTA", "PERMISO", "SUSPENSIÓN")

TIPOS_REGISTRO_UNO_A_UNO = [
    "FALTA", "PERMISO", "SUSPENSIÓN", "LEVANTAMIENTO SUSPENSIÓN", "PERMISO MÉDICO",
]


# ---------------------------------------------------------------------------
# Fechas / períodos
# ---------------------------------------------------------------------------

def obtener_fecha_fin_mes(anio: int, mes: int) -> date:
    """Último día del mes (FECHA_VEN del período). Puerto exacto."""
    if mes == 12:
        return date(anio + 1, 1, 1) - timedelta(days=1)
    return date(anio, mes + 1, 1) - timedelta(days=1)


def parse_fecha(s: str) -> date | None:
    """Parsea DD/MM/YYYY (principal), YYYY-MM-DD o DD-MM-YYYY. `None` si no matchea."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except Exception:  # noqa: BLE001, PERF203 - puerto exacto
            pass
    return None


def formatear_cedula(ced: object) -> str:
    """Cédula a 10 dígitos con ceros a la izquierda. Puerto exacto."""
    if ced is None:
        return ""
    ced_str = str(ced).strip()
    if "." in ced_str:
        ced_str = ced_str.split(".")[0]
    ced_str = "".join(c for c in ced_str if c.isdigit())
    if not ced_str:
        return ""
    return ced_str.zfill(10)


# ---------------------------------------------------------------------------
# Cálculo de horas por tipo de registro
# ---------------------------------------------------------------------------

def calcular_horas(tipo: str, cantidad: int) -> tuple[int, int]:
    """(horas, dias) para FALTA/PERMISO/PERMISO MÉDICO. Puerto exacto.

    FALTA = 16h y 2 "días" por unidad; PERMISO (y todo lo demás, incluido
    PERMISO MÉDICO) = 8h y 1 "día" por unidad.
    """
    t = tipo.upper()
    if t == "FALTA":
        return cantidad * 16, cantidad * 2
    elif t == "PERMISO":
        return cantidad * 8, cantidad
    else:
        return cantidad * 8, cantidad


def generar_observacion(tipo: str, cantidad: int, fecha_str: str, observ_libre: str,
                        horas: int, dias: int) -> str:
    """Texto de OBSERV para FALTA/PERMISO/PERMISO MÉDICO. Puerto exacto.

    LEGADO: la rama `else` produce texto "SUSPENSION: ..." pero NINGÚN llamador
    real invoca esta función con tipo SUSPENSIÓN (usan
    `generar_observacion_suspension`). Rama inalcanzable — replicada por fidelidad
    (bug #5 de faltas.md).
    """
    t = tipo.upper()
    obs = observ_libre.strip() or "Sin observación"
    if t == "FALTA":
        return f"FALTA: {horas}h ({dias}d) - {fecha_str} - {obs}"
    elif t == "PERMISO":
        return f"PERMISO: {horas}h ({dias}d) - {fecha_str} - {obs}"
    else:
        return f"SUSPENSION: {horas}h ({dias}d) - {fecha_str} - {obs}"


def concatenar_observ(actual: object, nueva: str) -> str:
    """Concatena con separador " + ". Puerto exacto."""
    if not actual or str(actual).strip() == "":
        return nueva
    return f"{actual} + {nueva}"


def validar_longitud_observacion(observacion: str, maximo: int = 255) -> bool:
    """True si cabe en el campo OBSERV (255 chars)."""
    return len(observacion or "") <= maximo


# ---------------------------------------------------------------------------
# Suspensión / Levantamiento de suspensión
# ---------------------------------------------------------------------------

def calcular_suspension(fecha_inicio: date, fecha_ven: date) -> tuple[int, int]:
    """(dias_suspension, horas) para una SUSPENSIÓN. dias = (fv - fi).days + 1.

    LEGADO: la vista previa en vivo del campo "Cantidad" (uno a uno) calcula los
    días SIN sumar 1; el registro real (esta función) SÍ suma 1. El valor
    mostrado puede diferir en 1 día del registrado — replicado (bug #2 de
    faltas.md). Decisión de negocio pendiente del usuario.
    """
    dias = (fecha_ven - fecha_inicio).days + 1
    horas = dias * HORAS_POR_FALTA
    return dias, horas


def calcular_horas_levantamiento_suspension(dias: int) -> int:
    """horas = dias * 8, para LEVANTAMIENTO SUSPENSIÓN. Puerto exacto.

    LEGADO: el registro de LEVANTAMIENTO termina en el mismo camino que una FALTA
    (`TOTAUS = TOTAUS + horas`), es decir SUMA horas al total en vez de
    restarlas. Un "levantamiento" conceptualmente debería devolver/restar —
    replicado (bug #4 de faltas.md). Decisión de negocio pendiente del usuario.
    """
    return dias * HORAS_POR_FALTA


def calcular_porcentaje_descuento_suspension(dias_suspension: int) -> int:
    """porcentaje = int((dias_suspension / 30) * 100). Puerto exacto.

    LEGADO: si dias_suspension > 30 el porcentaje supera 100 y, con `clamp=False`
    (flujo masivo), puede dejar HOR25/50/100 negativos en RPEMPLEA. El flujo uno
    a uno lo evita con `clamp=True` — replicado (bug #3 de faltas.md).
    """
    return int((dias_suspension / 30) * 100)


def calcular_descuento_horas_extra(hor25: int, hor50: int, hor100: int,
                                   porcentaje: int, clamp: bool = False) -> tuple[int, int, int]:
    """(desc_25, desc_50, desc_100). desc_x = int(hor_x * porcentaje / 100).

    `clamp=False` (default) = rama SUSPENSIÓN de `_registrar_todo` (masivo, NO
    acota). `clamp=True` = `registrar_uno()` (uno a uno, hace
    `min(desc_x, hor_x)`). LEGADO bug #3 — replicado.
    """
    if porcentaje <= 0:
        return 0, 0, 0
    desc25 = int((hor25 * porcentaje) / 100)
    desc50 = int((hor50 * porcentaje) / 100)
    desc100 = int((hor100 * porcentaje) / 100)
    if clamp:
        desc25 = min(desc25, hor25)
        desc50 = min(desc50, hor50)
        desc100 = min(desc100, hor100)
    return desc25, desc50, desc100


def generar_observacion_suspension(fecha_str: str, dias_suspension: int, horas: int,
                                   observ_libre: str | None, descuento_pct: int = 0,
                                   desc_25: int = 0, desc_50: int = 0, desc_100: int = 0) -> str:
    """Texto de OBSERV realmente usado al registrar una SUSPENSIÓN. Puerto exacto."""
    obs = observ_libre.strip() if observ_libre else observ_libre
    base = f"SUSPENSIÓN desde {fecha_str} — {dias_suspension} días ({horas}h) — {obs}"
    if desc_25 > 0 or desc_50 > 0 or desc_100 > 0:
        return (
            f"SUSPENSIÓN desde {fecha_str} — {dias_suspension} días ({horas}h) — "
            f"Descuento {descuento_pct}%: HOR25-{desc_25}h, HOR50-{desc_50}h, "
            f"HOR100-{desc_100}h — {obs}"
        )
    return base


def generar_observacion_levantamiento(fecha_str: str, dias: int, horas: int,
                                      observ_libre: str) -> str:
    """Texto de OBSERV para LEVANTAMIENTO SUSPENSIÓN (uno a uno). Puerto exacto."""
    return (
        f"LEVANTAMIENTO SUSPENSIÓN el {fecha_str} — "
        f"Devuelve {dias} días ({horas}h) — {observ_libre}"
    )


def evaluar_alerta_faltas(totaus_actual: int, horas_agregar: int,
                          limite_horas: int = 48) -> dict:
    """Alerta de "motivo de investigación" (>3 faltas = 48h, 1 falta = 16h). Puerto exacto.

    Devuelve dict {'nivel', 'mensaje', 'totaus_nuevo', 'faltas_actual', 'faltas_nuevo'}.
    """
    totaus_nuevo = totaus_actual + horas_agregar
    faltas_actual = totaus_actual // 16
    faltas_nuevo = totaus_nuevo // 16

    if totaus_actual >= limite_horas:
        nivel = "ya_supero"
        mensaje = (
            f"⚠ ATENCIÓN — MOTIVO DE INVESTIGACIÓN\n"
            f"Este empleado YA registra {faltas_actual} falta(s) ({totaus_actual}h).\n"
            f"Más de 3 faltas requiere proceso disciplinario."
        )
    elif totaus_nuevo > limite_horas:
        nivel = "superara"
        mensaje = (
            f"⚠ ATENCIÓN — SUPERARÁ EL LÍMITE\n"
            f"Alcanzará {faltas_nuevo} falta(s) ({totaus_nuevo}h).\n"
            f"Más de 3 faltas es motivo de investigación."
        )
    else:
        nivel = "ok"
        mensaje = ""

    return {
        "nivel": nivel,
        "mensaje": mensaje,
        "totaus_nuevo": totaus_nuevo,
        "faltas_actual": faltas_actual,
        "faltas_nuevo": faltas_nuevo,
    }


# ---------------------------------------------------------------------------
# Restas de horas extra (HOR50/HOR100) por número de faltas
# ---------------------------------------------------------------------------

def calcular_resta_horas(hor50: float, hor100: float, num_faltas: int) -> tuple[int, int, str]:
    """(hor50_nuevo, hor100_nuevo, estado). Descuenta num_faltas*8h de HOR50 y,
    si no alcanza, del remanente convertido a HOR100 con factor 0.75. Puerto exacto.

    `estado` = 'OK' si se cubrió, 'ERROR' si HOR100 quedaría negativo.
    """
    horas = num_faltas * HORAS_POR_FALTA
    if hor50 >= horas:
        return round(hor50 - horas), round(hor100), "OK"
    faltante = horas - hor50
    equiv100 = faltante * FACTOR_CONV_50A100
    hor100_nuevo = hor100 - equiv100
    if hor100_nuevo < 0:
        return 0, 0, "ERROR"
    return 0, round(hor100_nuevo), "OK"


def contar_faltas_por_cedula(registros: list[dict], anio: int, mes: int) -> dict[str, int]:
    """Cuenta faltas por cédula normalizada (`str(x).strip().lstrip('0')`),
    filtrando por período. Filas con fecha None/inválida se descartan. Puerto exacto.
    """
    conteo: dict[str, int] = {}
    for r in registros:
        fecha = r.get("fecha")
        if fecha is None:
            continue
        try:
            anio_f, mes_f = fecha.year, fecha.month
        except AttributeError:
            continue
        if anio_f != anio or mes_f != mes:
            continue
        ced_n = str(r.get("cedula", "")).strip().lstrip("0")
        conteo[ced_n] = conteo.get(ced_n, 0) + 1
    return conteo


def calcular_resultados_resta(conteo_faltas: dict[str, int], empleados: list[dict],
                              max_faltas: int = MAX_FALTAS) -> list[dict]:
    """Combina el conteo de faltas por cédula con RPEMPLEA y calcula la resta.
    Puerto exacto (Python puro, sin pandas). Estados: ERROR_CEDULA / REVISION /
    SIN_HORAS / OK / ERROR.
    """
    emp_por_ced = {e.get("CED_N", ""): e for e in empleados}
    resultados: list[dict] = []

    for ced_n, num in conteo_faltas.items():
        emp = emp_por_ced.get(ced_n)
        if not emp or not emp.get("EMPLEADO"):
            resultados.append({
                "EMPLEADO": "", "CEDULA": formatear_cedula(ced_n),
                "APELLIDOS": emp.get("APELLIDOS", "?") if emp else "?",
                "NOMBRES": emp.get("NOMBRES", "?") if emp else "?",
                "NUM_FALTAS": num, "HOR50_ACTUAL": 0, "HOR50_NUEVO": 0,
                "HOR100_ACTUAL": 0, "HOR100_NUEVO": 0, "ESTADO": "ERROR_CEDULA",
            })
            continue

        h50 = int(emp.get("HOR50") or 0)
        h100 = int(emp.get("HOR100") or 0)
        ced = formatear_cedula(emp.get("CEDULA", ced_n))
        base = {
            "EMPLEADO": emp["EMPLEADO"], "CEDULA": ced,
            "APELLIDOS": emp.get("APELLIDOS", ""), "NOMBRES": emp.get("NOMBRES", ""),
            "NUM_FALTAS": num,
        }

        if num > max_faltas:
            resultados.append({
                **base, "HOR50_ACTUAL": h50, "HOR50_NUEVO": h50,
                "HOR100_ACTUAL": h100, "HOR100_NUEVO": h100, "ESTADO": "REVISION",
            })
            continue

        if h50 == 0 and h100 == 0:
            resultados.append({
                **base, "HOR50_ACTUAL": 0, "HOR50_NUEVO": 0,
                "HOR100_ACTUAL": 0, "HOR100_NUEVO": 0, "ESTADO": "SIN_HORAS",
            })
            continue

        h50n, h100n, estado = calcular_resta_horas(h50, h100, num)
        resultados.append({
            **base, "HOR50_ACTUAL": h50, "HOR50_NUEVO": h50n,
            "HOR100_ACTUAL": h100, "HOR100_NUEVO": h100n, "ESTADO": estado,
        })

    return resultados


# ---------------------------------------------------------------------------
# Parsing de pegado masivo (Ctrl+V, tab "Registro Masivo")
# ---------------------------------------------------------------------------

def parse_line(line: str) -> list[str]:
    """Separador simple: tab, '|', ';', ',' (si >=2 comas), si no la línea entera.

    LEGADO: coexiste con `parse_linea_pegado` (que además detecta 2+ espacios).
    `parse_line` es efectivamente código legado no conectado al pegado real —
    replicado por fidelidad (bug #21 del README de nucleo_modular).
    """
    if "\t" in line:
        return [v.strip() for v in line.split("\t")]
    if "|" in line:
        return [v.strip() for v in line.split("|")]
    if ";" in line:
        return [v.strip() for v in line.split(";")]
    if "," in line and line.count(",") >= 2:
        return [v.strip() for v in line.split(",")]
    return [line.strip()]


def parse_linea_pegado(line: str) -> list[str]:
    """Igual que `parse_line` + detecta 2+ espacios consecutivos como separador.
    Puerto exacto de `_parse_linea` (el pegado real Ctrl+V del tab masivo).
    """
    if "\t" in line:
        return [v.strip() for v in line.split("\t")]
    if "|" in line:
        return [v.strip() for v in line.split("|")]
    if ";" in line:
        return [v.strip() for v in line.split(";")]
    if "," in line and line.count(",") >= 2:
        return [v.strip() for v in line.split(",")]
    if "  " in line:
        parts = re.split(r"  +", line)
        return [v.strip() for v in parts if v.strip()]
    return [line.strip()]


def mapear_pegado_a_campos(start_col: int, valores: list[str]) -> dict[str, str]:
    """Mapea valores parseados a campos del grid ('codigo','tipo','cant','fecha',
    'observ'), saltando la columna "Nombre" (readonly) al pegar desde Código.
    Puerto exacto de `_pegar_en_fila`.
    """
    col_to_field = {0: "codigo", 2: "tipo", 3: "cant", 4: "fecha", 5: "observ"}
    resultado: dict[str, str] = {}
    for j, val in enumerate(valores):
        if not val or not val.strip():
            continue
        target_col = (0 if j == 0 else j + 1) if start_col == 0 else start_col + j
        if target_col in col_to_field:
            resultado[col_to_field[target_col]] = val.strip()
    return resultado


def validar_fila_grid_masivo(codigo: object, tipo: object, cantidad: object, fecha: object,
                             tipos_validos: tuple[str, ...] = TIPOS_VALIDACION_MASIVA) -> tuple[bool, str | None]:
    """Valida una fila como el botón "✓ VALIDAR" (`_validar_manual`). Puerto exacto.

    NO valida el formato de fecha (solo que no esté vacía), a diferencia de
    `validar_fila_registro`. `tipos_validos` por defecto SIN tilde (LEGADO bug #1).
    """
    if not codigo or not str(codigo).strip():
        return False, "código requerido"
    if not tipo or tipo not in tipos_validos:
        return False, f"tipo debe ser {'/'.join(tipos_validos)}"
    if not cantidad or not str(cantidad).isdigit():
        return False, "cantidad debe ser numérica"
    if not fecha or not str(fecha).strip():
        return False, "fecha requerida"
    return True, None


def validar_fila_registro(
    codigo: object, tipo: str, cantidad_str: str, fecha_str: str,
    tipos_validos: tuple[str, ...] = TIPOS_REGISTRO_MASIVO,
) -> tuple[bool, str | None, date | None]:
    """Valida una fila como el botón "✔ REGISTRAR TODO" (`_registrar_todo`). Puerto exacto.

    `tipos_validos` por defecto CON tilde en SUSPENSIÓN (distinto de
    `validar_fila_grid_masivo` — LEGADO bug #1). Exige fecha parseable.
    Devuelve (valido, error, fecha_parseada).
    """
    if tipo not in tipos_validos:
        return False, f"tipo '{tipo}' inválido (use {'/'.join(tipos_validos)})", None
    try:
        cant = int(cantidad_str)
        if cant <= 0:
            raise ValueError
    except Exception:  # noqa: BLE001 - puerto exacto
        return False, "cantidad inválida", None
    fecha = parse_fecha(fecha_str)
    if not fecha:
        return False, f"fecha '{fecha_str}' inválida (use DD/MM/YYYY)", None
    return True, None, fecha
