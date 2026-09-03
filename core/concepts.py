"""Mapa canónico de conceptos de nómina (código CLASE → nombre).

★ ÚNICA fuente de verdad. Reemplaza las copias duplicadas de:
  - shared/obtener_datos.py  (dos veces: ~línea 173 y ~línea 347)
  - reportes/reporte_nomina_GUI.pyw  (MAPEO_CONCEPTOS)
  - reportes/reporte_nomina_COMPARADOR_SUPABASE_vs_SQL.pyw  (variante amplia)
  - roles/Roles_Principal.pyw  y demás roles/*

La base es la variante amplia (la del COMPARADOR), que es superconjunto de
las demás. NO CAMBIAR sin revisar todos los consumidores de nómina y sin
re-validar contra un período real (ver tests/unit/test_concepts.py y la
prueba de integración test_concepts_cubre_periodo_real).
"""

from __future__ import annotations

CLASE_A_CONCEPTO: dict[int, str] = {
    100: "SUELDO",
    102: "BONIFICACION",
    104: "FONDO_RESERVA",
    107: "DECIMO_TERCERA",
    108: "DECIMO_CUARTA",
    110: "MANIOBRAS",
    111: "REEMBOLSOS",
    113: "SOBRETIEMPO_25",
    114: "SOBRETIEMPO_50",
    115: "SOBRETIEMPO_100",
    120: "MOVILIZACION",
    200: "APORT_IESS",
    201: "ANTICIPOS_OTROS",
    202: "ANTICIPO_SUELDO",
    203: "MULTAS",
    204: "PRESTAMOS_QUIROGRAFARIOS",
    205: "PRESTAMOS_COMPANIA",
    206: "PENSION_ALIMENTICIA",
    207: "PRESTAMO_HIPOTECARIO",
    217: "ANTICIPOS_OTROS",
    218: "APORT_IESS_CONYUGE",
    219: "IMPUESTO_RENTA",
    250: "ANTICIPOS_SURTIDOS",
}

# CLASE que no entran en la consolidación (herencia de shared/obtener_datos.py)
CLASES_IGNORADAS: frozenset[int] = frozenset({105, 126, 199})

# CLASE 101 no es un concepto monetario: aporta el número de DIAS del período
CLASE_DIAS: int = 101

# Conceptos que solo se suman si el movimiento está ASENTADO
CONCEPTOS_CONDICIONADOS_ASENTADO: frozenset[str] = frozenset(
    {"DECIMO_TERCERA", "DECIMO_CUARTA"}
)

CAMPOS_INGRESO: tuple[str, ...] = (
    "SUELDO",
    "BONIFICACION",
    "FONDO_RESERVA",
    "DECIMO_TERCERA",
    "DECIMO_CUARTA",
    "MANIOBRAS",
    "REEMBOLSOS",
    "SOBRETIEMPO_25",
    "SOBRETIEMPO_50",
    "SOBRETIEMPO_100",
    "MOVILIZACION",
)

CAMPOS_EGRESO: tuple[str, ...] = (
    "APORT_IESS",
    "PRESTAMOS_QUIROGRAFARIOS",
    "PRESTAMOS_COMPANIA",
    "ANTICIPO_SUELDO",
    "ANTICIPOS_OTROS",
    "ANTICIPOS_SURTIDOS",
    "APORT_IESS_CONYUGE",
    "IMPUESTO_RENTA",
    "MULTAS",
    "PENSION_ALIMENTICIA",
    "PRESTAMO_HIPOTECARIO",
)


def concepto_de_clase(clase: int) -> str:
    """Nombre del concepto para una CLASE; ``CONCEPTO_<n>`` si no está mapeada."""
    return CLASE_A_CONCEPTO.get(clase, f"CONCEPTO_{clase}")
