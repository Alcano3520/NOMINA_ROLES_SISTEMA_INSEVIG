"""Importar aquí cada módulo de página para que se registre en la app.

`placeholders` se importa AL FINAL: genera páginas para las rutas de módulos que
aún no tienen página real (mira `_RUTAS_MIGRADAS`).
"""

from insevig_web.pages import (  # noqa: F401, I001
    index,
    login,
    reportes,
    prestamos,
    observaciones,
    empleados,
    roles,
    envio,
    registrador,
    admin,
)
from insevig_web.pages import placeholders  # noqa: F401
