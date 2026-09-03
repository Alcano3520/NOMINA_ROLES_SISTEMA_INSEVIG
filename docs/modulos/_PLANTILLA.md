# Módulo: <nombre>

> Plantilla. Copiar a `docs/modulos/<nombre>.md` y completar antes de encargar el
> módulo a un agente. El agente trabaja SOLO los archivos listados en "Rebanada".

## Qué hace (para el usuario)
- …

## Origen (código legado a portar)
| Archivo `.pyw` legado | Qué se reutiliza | Qué se reescribe |
|---|---|---|
| `…/…​.pyw` | queries / cálculos / … | UI, `filedialog`, threading |

## Rebanada (los únicos archivos que toca el agente)
- `core/repos/<mod>.py`
- `core/…​/` (dominio propio, si aplica)
- `core/excel/<mod>_*.py` (si aplica)
- `insevig_web/states/<mod>_state.py`
- `insevig_web/pages/<mod>/*.py`
- `insevig_web/components/<mod>/*.py` (si aplica)
- `tests/unit/test_<mod>_*.py`, `tests/integration/test_<mod>_*.py`
- este documento

## Contratos que consume (NO edita — ver docs/CONTRATOS.md)
- `core.datos.service.datos_empleado` / `core.concepts` / `core.db.*`
- `core.audit`, `core.jobs`, `core.storage`
- `insevig_web.components.layout.pagina`, `components/ui/*`
- `AuthState`, `DataSourceState`, `registry.ModuleSpec`

## Rutas y permisos
| Ruta | Acción requerida |
|---|---|
| `/<mod>/…​` | `ver` / `exportar` / … |

## Datos
- Fuentes: SQL Server (tablas …) / Supabase (tablas …). Lecturas respetan el selector.
- Escrituras (si hay): SQL Server, con `AuditWriter`. Concurrencia: …

## Jobs / operaciones largas
- …  → `core.jobs` + `job_progress`

## Responsividad
- Tablas: `ui.scroll_x`. Formularios: `rx.grid` 1col móvil / N escritorio.

## Criterio de "hecho"
- [ ] Paridad con el legado para una muestra (qué muestra)
- [ ] `pytest tests/…/test_<mod>_*` verde
- [ ] `ruff` + (si aplica) `mypy core` limpios
- [ ] Página compila (incluida en `test_arquitectura`)
- [ ] Revisado a 360 / 768 / 1280 px
