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

## Reglas de datos (obligatorias para todos los módulos)

### SQL Server 2008 R2 — escribir lo MÍNIMO
Es un sistema obsoleto y frágil (parche TLS 1.0) y a futuro se retira. Por tanto:

- La app **lee** de SQL Server; **escribe solo lo imprescindible**, nunca "por modificar".
- Superficie de escritura permitida: **exactamente** `RPEMPLEA`, `RPEMPOBSERV`,
  `RPINGDES`. Ninguna otra tabla. Ningún `ALTER`, ningún cambio de esquema.
- Toda escritura: **vista previa obligatoria** + `core/audit` + (en lotes) `dry-run`.
- Nada de `UPDATE`/`DELETE` masivos sin filtro por empleado y sin confirmación.
- Siempre `WHERE ... AND CODEMP='10' AND CODSUC='10'` y parámetros, nunca concatenación.
- Escrituras con el login `insevig_rw` (permisos mínimos), no `sa`.

### Fuente de datos
- El selector (`DataSourceState.fuente_de(modulo)`) solo afecta **lecturas**.
- Escrituras: siempre SQL Server (en v1). Ver "Futuro" abajo.

### Futuro (post-v1): Supabase-nube como fuente de verdad + operación offline
Decidido: a futuro todo migra a **Supabase en la nube**, pero el servidor de la
empresa tiene Internet intermitente → la app debe seguir funcionando offline.
Esto NO se construye en v1, pero **el diseño no debe cerrarse esa puerta**:

- Todo acceso a datos va por `core/repos/*` (nunca queries sueltas en la UI), para
  que añadir una tercera fuente `"local"` sea un cambio de capa repo, no de la app.
- Las tablas propias de la app que a futuro se sincronizarán llevan desde ya:
  PK `uuid` estable (no solo autoincrement), `updated_at`, `synced_at`, `origen`,
  borrado lógico (`deleted_at`), para permitir sync bidireccional / last-write-wins.
- Patrón previsto: Postgres **local** en el servidor como BD operativa + worker
  `core/sync/` que reconcilia con Supabase-nube (pull cuando hay Internet; push de
  un *outbox* de escrituras encoladas). Cola de conflictos para revisión humana.

## Cómo se pide un cambio de contrato

Abrir tarea aparte: qué se cambia, por qué, y **qué consumidores hay que actualizar**
(buscar usos con `grep`). Se revisa, se cambia el contrato + todos los consumidores +
los tests en un solo cambio.
