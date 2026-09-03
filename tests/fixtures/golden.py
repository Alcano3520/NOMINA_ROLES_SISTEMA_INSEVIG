"""Dataset "golden" compartido: un empleado, un período, movimientos que cubren
varias CLASE, la regla ASENTADO, una CLASE ignorada y una no mapeada.

Se usa para verificar que SQL Server y Supabase producen el MISMO
`EmpleadoNomina` (regresión de la de-duplicación) y para los golden files de
reportes/PDF en fases posteriores.
"""

from __future__ import annotations

from core.datos.port import DatosCrudos

PERIODO = "2026-06"

# clase, valor, asentado, dias
MOVIMIENTOS_GOLDEN: list[dict] = [
    {"clase": 101, "valor": 0.0, "asentado": True, "dias": 28.0},   # aporta DIAS=28
    {"clase": 100, "valor": 800.0, "asentado": True, "dias": None},  # SUELDO
    {"clase": 102, "valor": 50.0, "asentado": True, "dias": None},   # BONIFICACION
    {"clase": 104, "valor": 66.64, "asentado": True, "dias": None},  # FONDO_RESERVA
    {"clase": 107, "valor": 66.67, "asentado": True, "dias": None},  # DECIMO_TERCERA (asentado -> cuenta)
    {"clase": 108, "valor": 40.0, "asentado": False, "dias": None},  # DECIMO_CUARTA (NO asentado -> se ignora)
    {"clase": 200, "valor": 75.60, "asentado": True, "dias": None},  # APORT_IESS (egreso)
    {"clase": 205, "valor": 120.0, "asentado": True, "dias": None},  # PRESTAMOS_COMPANIA (egreso)
    {"clase": 205, "valor": 30.0, "asentado": True, "dias": None},   # se suma al anterior -> 150
    {"clase": 105, "valor": 999.0, "asentado": True, "dias": None},  # CLASE ignorada
    {"clase": 333, "valor": 12.0, "asentado": True, "dias": None},   # no mapeada -> CONCEPTO_333
]

CATALOGO_CARGOS = {"01": "GUARDIA", "05": "SUPERVISOR"}
CATALOGO_DEPTOS = {"10": "OPERACIONES"}

# Totales esperados:
#   ingresos = 800 + 50 + 66.64 + 66.67                      = 983.31
#   egresos  = 75.60 + 150.0                                 = 225.60
#   recibir  = 757.71
INGRESOS_ESPERADOS = 983.31
EGRESOS_ESPERADOS = 225.60
RECIBIR_ESPERADO = 757.71
DIAS_ESPERADOS = 28.0
CEDULA_ESPERADA = "0920116811"


def crudos_sqlserver() -> DatosCrudos:
    """Como los devolvería `fuente_sqlserver` (cédula float, códigos string)."""
    return DatosCrudos(
        empleado="1012 ",
        apellidos="PEREIRA",
        nombres="JUAN CARLOS",
        cedula=920116811.0,
        cargo_codigo="01",
        depto_codigo="10",
        movimientos=[dict(m) for m in MOVIMIENTOS_GOLDEN],
        catalogo_cargos=dict(CATALOGO_CARGOS),
        catalogo_deptos=dict(CATALOGO_DEPTOS),
    )


def crudos_supabase() -> DatosCrudos:
    """Equivalente desde Supabase: mismos datos, otra representación
    (cédula como string, códigos con espacios, clase/valor como str)."""
    movs = []
    for m in MOVIMIENTOS_GOLDEN:
        movs.append(
            {
                "clase": str(m["clase"]),
                "valor": str(m["valor"]),
                "asentado": m["asentado"],
                "dias": (str(m["dias"]) if m["dias"] is not None else None),
            }
        )
    return DatosCrudos(
        empleado="1012",
        apellidos="PEREIRA",
        nombres="JUAN CARLOS",
        cedula="920116811",
        cargo_codigo=" 01 ",
        depto_codigo="10",
        movimientos=movs,
        catalogo_cargos=dict(CATALOGO_CARGOS),
        catalogo_deptos=dict(CATALOGO_DEPTOS),
    )


class _FuenteFake:
    def __init__(self, crudos: DatosCrudos | None):
        self._crudos = crudos

    def fetch_empleado(self, periodo: str, cedula_o_nombre: str) -> DatosCrudos | None:
        return self._crudos


def fuentes_fake(sql: DatosCrudos | None, sup: DatosCrudos | None) -> dict:
    return {"sqlserver": _FuenteFake(sql), "supabase": _FuenteFake(sup)}
