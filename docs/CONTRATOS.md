# Contratos — lo que NO se toca sin acuerdo

La migración a Reflex está pensada para trabajarse **un módulo por agente**. Para
que eso funcione sin pisarse, hay un núcleo compartido y **congelado**. Un agente
de módulo que necesite cambiar algo de aquí lo **reporta como cambio de contrato**;
no lo hace por su cuenta.

## Archivos congelados

### Núcleo (`core/`)
| Archivo | Contrato |
|---|---|
| `core/config.py` | `Settings` y sus campos. Añadir un campo nuevo es aceptable; renombrar/quitar no. |
| `core/concepts.py` | `CLASE_A_CONCEPTO`, `CLASES_IGNORADAS`, `CAMPOS_INGRESO/EGRESO`, regla ASENTADO. "NO CAMBIAR" — ver `tests/unit/test_concepts.py`. |
| `core/datos/port.py` | `EmpleadoNomina`, `DatosCrudos`, `FuenteDatos`. Forma estable (consumida por roles/, reportes/). |
| `core/datos/service.py` | firma de `datos_empleado(periodo, id, fuente)`. |
| `core/db/*` | `conexion()`, `filas()`, `get_client()`, `appdb.session()`, `fuente_recomendada()`. |
| `core/audit/writer.py` | `AuditWriter.record(...)` (pendiente de crear). |
| `core/jobs/runner.py` | API de `Job` + `JobRunner` (pendiente). |
| `core/storage.py` | API de almacenamiento de salidas (pendiente). |
| `core/utils.py` | `normalizar_cedula`, `a_int`, `a_float`. |

### Web (`insevig_web/`)
| Archivo | Contrato |
|---|---|
| `state.py` | `AppState`. **No importa nada del proyecto.** |
| `models.py` | Todas las tablas. Cambiar = migración + revisión. |
| `auth.py` | `puede()`, `hash_password`, `verify_password`, `ACCIONES`, `PERMISOS_POR_DEFECTO`. |
| `states/auth_state.py` | `AuthState` (`autenticado`, `roles`, `permisos_flat`, `can`, `login`, `logout`). |
| `states/datasource_state.py` | `DataSourceState.fuente_de(modulo)` / `set_fuente`. |
| `registry.py` | `ModuleSpec`, `NavItem`, `MODULES`. Editarlo = integrar un módulo (no es tarea de módulo). |
| `theme.py` + `components/ui/*` | Sistema de diseño. Los módulos usan estos componentes, no crean estilos. |
| `components/layout.py` | `pagina(*contenido, requiere=(modulo, accion))`. Envoltura obligatoria de toda página. |
| `components/sidebar.py`, `components/data_source_selector.py` | Se consumen, no se editan. |

## Lo que SÍ es de cada módulo `<mod>`

```
core/repos/<mod>.py                       (+ core/<dominio>/ propio: pdf/, email/, ...)
core/excel/<mod>_*.py                      builders/parsers con prefijo del módulo
insevig_web/states/<mod>_state.py
insevig_web/pages/<mod>/*.py               (reemplazan el placeholder)
insevig_web/components/<mod>/*.py          solo del módulo
tests/unit/test_<mod>_*.py
tests/integration/test_<mod>_*.py
docs/modulos/<mod>.md
```

## Reglas verificadas por `tests/test_arquitectura.py`

- `core/` no importa `insevig_web`.
- `core/repos/<a>` no importa `core/repos/<b>`.
- `state.py` no importa el proyecto.
- Los `states/<mod>_state.py` no se importan entre sí (salvo `auth_state` y
  `datasource_state`, que son compartidos).
- La app Reflex compila (`reflex export --backend-only`).

## Cómo se pide un cambio de contrato

Abrir tarea aparte: qué se cambia, por qué, y **qué consumidores hay que actualizar**
(buscar usos con `grep`). Se revisa, se cambia el contrato + todos los consumidores +
los tests en un solo cambio.
