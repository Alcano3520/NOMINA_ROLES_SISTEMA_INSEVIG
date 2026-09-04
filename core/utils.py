"""Utilidades pequeñas y sin dependencias de negocio."""

from __future__ import annotations


def normalizar_cedula(valor: object) -> str:
    """Cédula ecuatoriana a 10 dígitos con ceros a la izquierda.

    SQL Server y Supabase devuelven la cédula como float (ej. ``920116811.0``);
    Excel pierde el cero inicial. Esta función es la regla única "NO ROMPER"
    documentada en shared/CLAUDE.md: ``str(int(cedula)).zfill(10)``.

    >>> normalizar_cedula(920116811.0)
    '0920116811'
    >>> normalizar_cedula("1712345678")
    '1712345678'
    >>> normalizar_cedula(None)
    ''
    """
    if valor is None:
        return ""
    s = str(valor).strip()
    if not s:
        return ""
    if s.replace(".", "", 1).replace("-", "", 1).isdigit():
        try:
            return str(abs(int(float(s)))).zfill(10)
        except (ValueError, OverflowError):
            pass
    digitos = "".join(c for c in s if c.isdigit())
    return digitos.zfill(10) if digitos else s


def cedula_valida(cedula: object) -> bool:
    """Valida el dígito verificador de una cédula ecuatoriana (módulo 10).

    >>> cedula_valida("0926815564")
    True
    >>> cedula_valida("1234567890")
    False
    """
    c = "".join(ch for ch in str(cedula or "") if ch.isdigit())
    if len(c) == 9:
        c = "0" + c
    if len(c) != 10:
        return False
    if not 1 <= int(c[:2]) <= 24:
        return False
    if int(c[2]) > 6:
        return False
    coef = (2, 1, 2, 1, 2, 1, 2, 1, 2)
    suma = 0
    for i in range(9):
        v = int(c[i]) * coef[i]
        suma += v - 9 if v >= 10 else v
    return (10 - suma % 10) % 10 == int(c[9])


def a_int(valor: object, default: int = 0) -> int:
    try:
        if valor is None or valor == "":
            return default
        return int(float(valor))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def a_float(valor: object, default: float = 0.0) -> float:
    try:
        if valor is None or valor == "":
            return default
        return float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
