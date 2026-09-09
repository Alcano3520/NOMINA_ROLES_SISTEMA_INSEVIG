# Cambios de contrato — migración sanciones/faltas (C1–C6)

> Estado: **PROPUESTA — pendiente de OK del usuario.** No se mergea nada de aquí
> sin aprobación explícita (regla de `PROMPT_IMPLEMENTAR_TODO_NOMINA.md` §2 y §9.2
> + `docs/CONTRATOS.md` → "Cómo se pide un cambio de contrato").
>
> Todos los cambios se aplican **juntos, en un solo commit**, con sus consumidores
> y tests. HEAD al preparar esto: `623a000`.

---

## Resumen

| # | Qué | Archivos congelados que toca | Riesgo | Para |
|---|---|---|---|---|
| C1 | `RPHORTOT` entra a la superficie de escritura permitida | `docs/CONTRATOS.md` | Bajo (solo doc; no hay allowlist en código) | faltas |
| C2 | Alta del módulo `"faltas"` (registry + tests + permisos + sidebar) | `registry.py`, `tests/test_arquitectura.py`, `auth.py`, `seed.py`, `components/sidebar.py`, `states/datasource_state.py` | Medio (varios consumidores acoplados) | faltas |
| C3 | Dejar por escrito que `"sanciones"` NO va en `registry`/`MODULOS` (backend puro) | `docs/CONTRATOS.md`, `docs/modulos/sanciones.md` | Nulo (doc) | sanciones |
| C4 | `Settings` para el proyecto Supabase de sanciones (`syxzopyevfuwymmltbwn`) + service key del de empleados | `core/config.py`, `.env.example` | Bajo (campos nuevos, default vacío — additivo, permitido por CONTRATOS.md) | sanciones, carga_usuarios |
| C5 | Regla escrita: `normalizar_cedula` en la frontera de `core/repos/`; diferencias de formato se documentan, no se corrigen | `docs/CONTRATOS.md` | Nulo (doc) | todos |
| C6 | Alta del módulo `"carga_usuarios"` | igual que C2 | Medio | carga_usuarios — **BLOQUEADO por decisión de producto** (ver abajo) |

---

## C1 — `RPHORTOT` a la superficie de escritura

**Archivo:** `docs/CONTRATOS.md`, sección "SQL Server 2008 R2 — escribir lo MÍNIMO".

**Cambio (texto exacto):**

```diff
- Superficie de escritura permitida: **exactamente** `RPEMPLEA`, `RPEMPOBSERV`,
-   `RPINGDES`. Ninguna otra tabla. Ningún `ALTER`, ningún cambio de esquema.
+ Superficie de escritura permitida: **exactamente** `RPEMPLEA`, `RPEMPOBSERV`,
+   `RPINGDES`, `RPHORTOT`. Ninguna otra tabla. Ningún `ALTER`, ningún cambio de
+   esquema. `RPHORTOT` = período de faltas ABIERTO (módulo faltas). `RPHORHIS`
+   (meses cerrados) es **solo lectura**, nunca se escribe.
```

**Por qué:** el módulo faltas registra faltas/permisos/suspensiones sumando horas
al acumulado `TOTAUS` de `RPHORTOT` (período abierto). El descuento de horas extra
de una suspensión y el Cargador de Restas escriben `HOR25/HOR50/HOR100` en
`RPEMPLEA`, que **ya está permitida** → sin cambio para eso.

**Consumidores a actualizar:** ninguno en código. No existe una allowlist
programática de tablas (verificado: `core/audit/writer.py` no valida `target_table`;
`grep -rn RPHORTOT core/` solo aparece en `observaciones.py:143`, lectura). El
contrato es documental. `core/repos/faltas.py` (nuevo) respetará `ejecutar=False`
(vista previa) + `audit_scope(...)` + `WHERE ... AND CODEMP='10' AND CODSUC='10'`
parametrizado, igual que el resto.

**Test:** se añade `tests/test_arquitectura.py::test_superficie_escritura_documentada`
que parsea `docs/CONTRATOS.md` y verifica que la lista sea exactamente
`{RPEMPLEA, RPEMPOBSERV, RPINGDES, RPHORTOT}` (candado para que no crezca sin
pasar por aquí).

---

## C2 — Alta del módulo `"faltas"`

Módulo **aparte** (`/faltas/*`); el visor de lectura de faltas que ya vive en
`observaciones` (pestaña "Faltas", `core/repos/observaciones.py`) **queda igual**.
(Decisión de FASE -1, ver `docs/modulos/faltas.md`.)

### C2.a — `insevig_web/registry.py`

Añadir el `ModuleSpec` (propuesto, dentro del bloque "Personal" conceptual):

```python
ModuleSpec(
    "faltas", "Gestión de faltas", "calendar-x",
    [NavItem("Registro masivo", "/faltas/masivo", "crear"),
     NavItem("Registro uno a uno", "/faltas/individual", "crear"),
     NavItem("Ver / editar período", "/faltas/periodo", "ver"),
     NavItem("Cargador de restas de horas", "/faltas/restas", "cargar_masivo")],
),
```

### C2.b — `tests/test_arquitectura.py`

```diff
 MODULOS = (
     "reportes", "prestamos", "observaciones", "empleados", "roles",
-    "registrador", "bitacora", "liquidaciones", "vacaciones", "admin",
+    "registrador", "bitacora", "liquidaciones", "vacaciones", "faltas", "admin",
 )
```

(`test_registry_coherente` exige `sorted(nombres registry) == sorted(MODULOS)` →
los dos cambian en el mismo commit.)

### C2.c — `insevig_web/auth.py`  (permisos)

**Sin acciones nuevas.** Se reutiliza el vocabulario existente de `ACCIONES`:

| Ruta faltas | Acción del contrato | Significado |
|---|---|---|
| `/faltas/masivo`, `/faltas/individual` | `crear` | registrar falta/permiso/suspensión/levantamiento |
| `/faltas/periodo` (ver) | `ver` | consultar `RPHORTOT`/`RPHORHIS` |
| `/faltas/periodo` (editar/eliminar) | `editar` / `eliminar` | solo sobre `RPHORTOT` |
| `/faltas/restas` | `cargar_masivo` | Cargador de Restas de Horas |
| exportar reportes Excel | `exportar` | log de registro / período |

```diff
 _TODOS_MODULOS = (
     "reportes", "prestamos", "observaciones", "empleados", "roles",
-    "registrador", "bitacora", "liquidaciones", "vacaciones", "admin",
+    "registrador", "bitacora", "liquidaciones", "vacaciones", "faltas", "admin",
 )
```

`PERMISOS_POR_DEFECTO`:
- `admin`: hereda `set(ACCIONES)` para `faltas` automáticamente (usa
  comprehension sobre `_TODOS_MODULOS`).
- `editor`: `"faltas": {"ver", "exportar", "crear", "editar", "eliminar", "cargar_masivo"}`
- `consulta`: `"faltas": {"ver"}`

### C2.d — `insevig_web/seed.py`

No cambia el código (itera `PERMISOS_POR_DEFECTO`), pero hay que **re-sembrar** en
el deploy: `scripts/seed.py` / `alembic` ya corren en `deploy-nas.ps1`. Los
permisos de `faltas` para roles existentes se insertan al re-seedear.

### C2.e — `insevig_web/components/sidebar.py`

```diff
 _SECCIONES = [
-    ("Personal", ("empleados", "observaciones", "vacaciones", "prestamos")),
+    ("Personal", ("empleados", "observaciones", "faltas", "vacaciones", "prestamos")),
     ("Nómina", ("roles", "reportes", "registrador")),
     ...
```

### C2.f — `insevig_web/states/datasource_state.py`

```diff
 _MODULOS = (
     "reportes", "prestamos", "observaciones", "empleados", "roles", "registrador",
-    "bitacora", "liquidaciones",
+    "bitacora", "liquidaciones", "faltas",
 )
```

(para que el selector de fuente SQL Server/Supabase aplique a las páginas de faltas
en lectura).

### C2.g — nuevo `docs/modulos/faltas.md` + `faltas_UI.md`

Copia de los de `sistema_sanciones_RRHH/docs/modulos/`, con la decisión de FASE -1
registrada.

**Consumidores:** los 7 puntos de arriba. `test_todas_las_paginas_compilan` exige
≥20 páginas y que cada `@rx.page` compile → las 4 páginas de `/faltas/*` deben
existir (aunque sea con contenido mínimo) en el mismo commit que registra el
módulo, o el test rompe.

---

## C3 — `"sanciones"` NO es un módulo Reflex

**Archivos:** `docs/CONTRATOS.md` (nota nueva) + `docs/modulos/sanciones.md`.

**Texto a añadir en `docs/CONTRATOS.md`, tras la tabla de `registry.py`:**

> **`sanciones` es backend puro.** El frontend de sanciones es la app Flutter
> `sistema_sanciones_insevig/`. `core/repos/sanciones.py` existe (trasplante), pero
> **no** se añade `"sanciones"` a `MODULES`/`MODULOS`, **no** hay páginas en
> `insevig_web/pages/sanciones/`, **no** hay `sanciones_state.py`.
> `test_registry_coherente` debe seguir verde sin `"sanciones"`.

**Consumidores:** ninguno (es una barrera, no un cambio de comportamiento).

---

## C4 — `Settings` para el Supabase de sanciones

**Archivos:** `core/config.py` (campos nuevos, additivo → permitido), `.env.example`.

Contexto de los proyectos:

| Proyecto | Ref | Tablas | Ya configurado |
|---|---|---|---|
| Nómina / Empleados-INSEVIG | `buzcapcwmksasrtjofae` | `rpemplea`, `empleados`, `vac_*`, ... | **Sí** → `supabase_url` / `supabase_key` |
| Sanciones | `syxzopyevfuwymmltbwn` | `sanciones`, `profiles`, `usuarios_rrhh` | **No** |

El repo de sanciones lee `empleados` del **mismo** proyecto que ya usa nómina
(`buzcapcwmksasrtjofae`) → se **reutiliza** `supabase_url`. Solo hace falta:

```diff
 # ── Supabase (solo lectura) ──────────────────────────────────────────────
 supabase_url: str = ""
 supabase_key: str = ""
+# service key del proyecto de nómina/empleados — SOLO server-side (carga_usuarios / admin auth).
+# Vacío = las operaciones que la requieren quedan deshabilitadas.
+supabase_service_key: str = ""
+
+# ── Supabase — proyecto SANCIONES (syxzopyevfuwymmltbwn) ─────────────────
+# Backend puro (core/repos/sanciones.py). Sin estas vars, las funciones de red
+# reciben 401 al ejecutarse; el import nunca falla.
+supabase_sanciones_url: str = ""
+supabase_sanciones_anon_key: str = ""
+supabase_sanciones_service_key: str = ""   # SOLO server-side
```

`.env.example` — bloque nuevo, todo vacío:

```
# ── Supabase — proyecto SANCIONES (backend puro, sin UI) ──────────────────────
SUPABASE_SANCIONES_URL=
SUPABASE_SANCIONES_ANON_KEY=
SUPABASE_SANCIONES_SERVICE_KEY=
# service key del proyecto de empleados/nómina (carga masiva de usuarios):
SUPABASE_SERVICE_KEY=
```

**Reglas (van al docstring de `core/config.py` y a `sanciones.md`):**
- Las `*_SERVICE_KEY` **solo** se usan server-side (`core/`), nunca se serializan
  a un `State` ni llegan al browser.
- `core/repos/sanciones.py` recibe el **cliente Supabase como parámetro**
  (inyección), no lee la config global directamente.
- No se replica el volcado de contraseñas generadas a un `.txt` que hace el legado.

**Consumidores:** `core/config.Settings` (nuevos campos), `core/db/supabase_client.py`
(nuevo factory `cliente_sanciones()` — se añade cuando se porte el repo, no ahora).
Ningún consumidor existente cambia.

**Pendiente de rotación (ya registrado en memoria, no es parte de este cambio):**
las SERVICE keys del legado de sanciones están hardcodeadas en
`sistema_sanciones_RRHH` → hay que emitir keys nuevas antes de production, igual
que la de nómina.

---

## C5 — `normalizar_cedula` en la frontera

**Archivo:** `docs/CONTRATOS.md`, sección "Reglas de datos".

**Texto a añadir:**

> ### Cédulas: normalización en la frontera de `core/repos/`
> - `core.utils.normalizar_cedula` se aplica **al entrar** (parámetros que llegan
>   como cédula) y **al salir** (cédulas en dicts/DataFrames que devuelve el repo),
>   nunca en medio de la lógica trasplantada.
> - SQL Server / Supabase devuelven `cedula` como float (`920116811.0`);
>   la forma canónica es `str(int(x)).zfill(10)`.
> - Si al trasplantar lógica legada aparece una diferencia de formato de cédula
>   entre dos fuentes, se **documenta** (`# LEGADO: ...`), no se "arregla" en
>   silencio dentro del código portado.

**Consumidores:** ninguno (formaliza lo que ya hace `normalizar_cedula`).

---

## C6 — `"carga_usuarios"` — BLOQUEADO por producto

**Pregunta al usuario (decisión de negocio, no técnica):**

> El módulo "carga masiva de usuarios" administra cuentas de **Supabase Auth del
> proyecto de sanciones** (`syxzopyevfuwymmltbwn`) — los usuarios de la app Flutter
> de supervisores. ¿Ese proyecto Supabase **sigue vivo** después de la migración,
> o se retira junto con la app Flutter?

- **Si sigue vivo** → C6 se activa: `core/repos/usuarios_auth.py` + C4 + alta de
  módulo (igual que C2) + 4 páginas `/carga-usuarios/{individual,listado,reset,masivo}`.
  Falta además definir el **mecanismo de entrega de contraseñas generadas**
  (auditado; el legado las tira a un `.txt` — no se replica).
- **Si se retira** → C6 se descarta. `nucleo_modular/carga_usuarios.py` queda como
  utilidad sin páginas. Se documenta la decisión y listo.

Hasta esa respuesta, C6 **no se prepara**.

---

## Orden de aplicación (si el usuario aprueba C1–C5)

1. Un commit con C1 + C3 + C5 (solo `docs/CONTRATOS.md` + `docs/modulos/*.md`) — cero riesgo.
2. Un commit con C4 (`core/config.py` + `.env.example`) — additivo.
3. Un commit con C2 (registry + tests + auth + sidebar + datasource + 4 páginas
   stub `/faltas/*` que compilan + `docs/modulos/faltas*.md`). Este deja el módulo
   "faltas" visible en el sidebar pero con páginas vacías; el trabajo real
   (`core/repos/faltas.py`, estados, UI) viene después, ya sin tocar congelados.
4. Deploy con re-seed de permisos.
