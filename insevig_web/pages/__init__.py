"""Importar aquí cada módulo de página para que se registre en la app.

`placeholders` debe importarse AL FINAL: genera páginas para las rutas de los
módulos que aún no tienen página real (mira `_YA_MIGRADOS`).
"""

from insevig_web.pages import index, login, reportes  # noqa: F401, I001
from insevig_web.pages import placeholders  # noqa: F401
