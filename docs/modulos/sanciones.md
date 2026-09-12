# Módulo: sanciones (Procesamiento de Sanciones RRHH)

> **C3 REVISADO (2026-09-09): `sanciones` ES un módulo Reflex completo.**
> El usuario aclaró que `sistema_sanciones_RRHH/main.py` (app de escritorio, 227 KB,
> **activa y en desarrollo**) es la herramienta con la que **RRHH y gerencia
> revisan / aprueban / rechazan / procesan los reportes de supervisores y
> coordinadores**, + novedades de horario + estadísticas + reportes. Eso necesita
> UI web (el objetivo de la migración es "no más .exe para RRHH"). La app Flutter
> — el lado "el supervisor carga el reporte" — es otro asunto, para más adelante,
> **fuera del alcance de esta migración**.
>
> **Hecho:**
> - `core/sanciones/{catalogos,validadores,imagenes,valores}.py`.
> - `core/repos/sanciones.py`: buscar / pendientes (aprobación + proceso) / aprobar
>   / rechazar / procesar (individual + masivo) / novedades / categorizar /
>   `nombres_supervisores` (profiles, service key) / `estadisticas` (desde Supabase,
>   reemplaza el SQLite del escritorio) / `exportar_excel` / `ficha_pdf`. Cliente
>   Supabase inyectable, cédula en la frontera, auditoría → `core.audit`.
> - `core/excel/sanciones_builders.py` (`sanciones_xlsx`), `core/pdf/sancion_ficha.py`.
> - `core/db/supabase_client.get_client_sanciones(service=bool)`.
> - `insevig_web/states/sanciones_state.py` + 5 páginas
>   `/sanciones/{bandeja,historial,buscar,novedades,estadisticas}` + diálogo de ficha.
> - `"sanciones"` en `registry`/`MODULOS`/`auth`/sidebar. Roles: `editor` =
>   ver/exportar/editar (aprobar/rechazar/procesar), `consulta` = ver/exportar.
> Commits `6b630d7` (base) + `1cb0820` (UI + reportes). 18 tests.
>
> **NO portado:** `usuarios_rrhh` (login propio del .exe — en la web se usa el auth
> de nómina; la gestión de cuentas Auth de la app va en el módulo `carga_usuarios`);
> el fallback SQLite de `local_db.py` (reemplazado por `core.audit`).
>
> (El párrafo de abajo, de antes del revert de C3, quedaba contradiciendo esto
> — eliminado 2026-09-12, sincronizado contra `docs/ESTADO_MIGRACION.md`, que
> es la fuente de verdad del lado Nómina.)

## Qué hace (para el usuario)

Flujo de una sanción disciplinaria:
`borrador → enviado` (supervisor, app Flutter) `→ aprobado / rechazado`
(gerencia) `→ procesado` (RRHH agrega `comentarios_rrhh` = "Procesado para
nomina").

La herramienta de escritorio (`main.py`) permite a RRHH/gerencia:
- Ver sanciones **pendientes de aprobación** (`status=enviado`) y aprobarlas /
  rechazarlas (individual o masivo).
- Ver sanciones **pendientes de procesamiento** (`status=aprobado` sin
  `comentarios_rrhh`) y procesarlas (individual o masivo).
- **Buscar en Supabase** (server-side, `ilike`) por nombre/cédula/código/tipo.
- Ver el **historial** paginado de procesadas.
- Abrir la **ficha de detalle** de una sanción (datos de empleado enriquecidos,
  firma, foto de evidencia, comentarios) y exportarla a **PDF**.
- **Exportar a Excel** (varias hojas por categoría + "Detalle Resumen" con el
  valor monetario calculado por tipo de sanción).
- **Administración de usuarios** (`usuarios_rrhh`, solo admin — ver módulo
  aparte, no incluido aquí).

## Origen (código legado)

| Archivo legado | Qué se reutiliza | Qué se reescribe |
|---|---|---|
| `procesador.py` (~2400 líneas, ya sin Tkinter) | **todo** — es la capa de API | nada; se transcribió a funciones puras |
| `main.py` (flujo de sanciones embebido) | lógica de búsqueda/filtros/dispatch | toda la UI (sidebar, Treeview, diálogos) |
| `modern_viewer.py` | `_buscar_campo_imagen`, `_exportar_pdf` | los widgets de la ficha |
| `editor_sancion.py` | `validar_datos`, tabla de permisos | **código muerto** (nadie lo instancia) |
| `utils_nuevo.py` | `validar_estado_transicion`, `validar_datos_sancion` | **código muerto y roto** (`NameError` al importar) |

## Lógica ya extraída (sin Tkinter)

| `nucleo_modular/…` | Contenido | Espejo Reflex |
|---|---|---|
| `repos/sanciones.py` | Fachada del módulo. | `core/repos/sanciones.py` |
| `sanciones.py` | CRUD/búsqueda de la tabla `sanciones` (Supabase): `buscar_sanciones`, `obtener_sancion`, `obtener_sanciones_pendientes[_aprobacion]`, `obtener_procesadas_completas` (paginada), `aprobar_*`, `rechazar_*`, `procesar_*`, `categorizar_sanciones`, `guardar_*_supabase`, novedades. | `core/repos/sanciones.py` |
| `empleados.py` | Enriquecimiento con `empleados` (proyecto Supabase Empleados-INSEVIG) + `profiles` (nombres de supervisor). Caché con TTL. Reintento sin `es_activo` para retirados. | `core/repos/empleados.py` (ya existe allá — verificar overlap) |
| `usuarios.py` | `validar_usuario` (login), CRUD `usuarios_rrhh`, `permisos_por_rol`. | `core/repos/` (auth) |
| `local_db.py` | SQLite de auditoría/caché offline: `inicializar_db`, `log_operacion`, `guardar_*_local`, `enriquecer_con_datos_locales`, `obtener_estadisticas`. | `core/audit` + `core/db` |
| `reportes.py` | `generar_excel_sanciones(...) -> bytes`, `generar_pdf_sancion(...) -> bytes` (+ wrappers a disco). | `core/excel/sanciones_*.py`, `core/pdf/sancion_*.py` |
| `imagenes.py` | Resolución de URL de firma/foto (http o ruta relativa de Supabase Storage). | `core/repos/sanciones.py` helper |
| `validadores.py` | `validar_datos_sancion`, `validar_estado_transicion`. | `core/sanciones/` |

## Rutas y permisos

| Ruta | Acción requerida |
|---|---|
| `/sanciones/bandeja` | `sanciones.ver` (aprobar/rechazar/procesar requiere `sanciones.editar`) |
| `/sanciones/historial` | `sanciones.ver` |
| `/sanciones/buscar` | `sanciones.ver` |
| `/sanciones/novedades` | `sanciones.ver` (`sanciones.editar` para registrar) |
| `/sanciones/estadisticas` | `sanciones.ver` |

Roles: `editor` = ver/exportar/editar (aprobar/rechazar/procesar), `consulta`
= ver/exportar. `"sanciones"` está en `registry.MODULES`/`auth`/sidebar.

## Datos

- **Dos proyectos Supabase**: `sanciones` (`syxzopyevfuwymmltbwn`: tablas
  `sanciones`, `profiles`, `usuarios_rrhh`, `*_rrhh`) y **Empleados-INSEVIG**
  (`buzcapcwmksasrtjofae`: tabla `empleados`). Cada uno con su par de keys
  ANON + SERVICE.
- **SQLite local** `procesadas.db` (auditoría, caché, fallback offline).
- **Sin SQL Server.** Sanciones no toca `insevig`.
- Columnas reales de `sanciones` (de logs): `id, supervisor_id, empleado_cod,
  empleado_nombre, puesto, agente, fecha, hora, tipo_sancion, observaciones,
  observaciones_adicionales, pendiente, foto_url, firma_path, horas_extras,
  status, comentarios_gerencia, comentarios_rrhh, fecha_revision, reviewed_by,
  created_at, updated_at`. `empleado_cedula/cargo/departamento` **no existen**
  en la tabla — vienen del enriquecimiento con `empleados`.

## Diferencias / bugs del legado (ver `nucleo_modular/README.md` §1-8)

- `editor_sancion.py` y `utils_nuevo.py` son código muerto (el 2º ni importa).
- Dos esquemas de hash de contraseña incompatibles (`sha256` plano vs.
  `sha256+sal`).
- `ROLES_USUARIOS` se indexaba por username en vez de por rol.
- **Bug vivo**: `guardar_aprobacion_supabase` llama a su fallback local con la
  firma equivocada → `TypeError` si el POST a Supabase falla.
- `obtener_empleado_por_cedula` no reintenta sin `es_activo` (los otros dos sí).
- Cédula: el legado **no** normaliza (`str(int).zfill(10)`); el repo Reflex sí
  (`core.utils.normalizar_cedula`, regla "NO ROMPER"). Aplicar en la frontera.

## Criterio de "hecho"

- [x] `core/repos/sanciones.py` importable sin I/O, cliente Supabase inyectado.
- [x] Cédula normalizada en entrada/salida.
- [x] `pytest tests/unit/test_sanciones_*` verde (18 tests).
- [x] `"sanciones"` en `registry.MODULES` + 5 páginas Reflex + sidebar + auth.
- [x] `reflex export` OK.
- [ ] Desplegado en el NAS con `SUPABASE_SANCIONES_SERVICE_KEY` configurada —
      pedido 2026-09-12, en curso (ver `docs/ESTADO_MIGRACION.md`).
- [ ] Rotar las SERVICE keys del proyecto de sanciones.
- [ ] Paridad end-to-end contra `main.py` en uso real. **Pendiente.**
- [ ] Revisado a 360 / 768 / 1280 px. **Pendiente.**
