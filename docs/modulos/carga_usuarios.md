# Módulo: carga_usuarios (Creador Masivo de Usuarios — Supabase Auth)

> Estado en el repo Reflex: **NO existe.** Decisión de producto pendiente:
> ¿módulo web o utilidad suelta de admin? Opera sobre **Supabase Auth**
> (`auth/v1/admin/users` + tabla `profiles`) del proyecto **sanciones**
> (`syxzopyevfuwymmltbwn`), es decir crea/gestiona los **logins de supervisores
> de la app Flutter**, NO empleados de nómina ni usuarios `usuarios_rrhh`.

## Qué hace (para el usuario)

Herramienta de administración de cuentas de la app de sanciones:
- **Crear/actualizar un usuario** individual (email + contraseña + metadata en
  `profiles`).
- **Carga masiva** de usuarios pegando desde Excel/CSV (`email`, `nombre`,
  `password`…), con opción de generar contraseñas seguras.
- **Ver usuarios** existentes (Auth + `profiles`), buscar, exportar.
- **Resetear contraseñas** (individual o masivo), generar *recovery link*.
- **Probar conexión** a Supabase.

## Origen (código legado)

| Archivo legado | Qué se reutiliza | Qué se reescribe |
|---|---|---|
| `carga maciva usuarios6.0.py` (~3000 líneas, clase `SupabaseUserCreatorEnhanced`) | llamadas REST a Supabase Auth Admin + `profiles`, generación de contraseñas, parsing CSV/Excel, validación de contraseña | toda la UI Tkinter (4 pestañas), `filedialog`, `scrolledtext` log, threading |

**Credenciales**: hoy la SERVICE key del proyecto sanciones está **hardcodeada**
en el archivo. En `nucleo_modular`/Reflex debe venir de env
(`SUPABASE_SERVICE_KEY`), default vacío.

## Lógica a extraer → `nucleo_modular/repos/carga_usuarios.py`

Fachada nueva (aún no escrita en detalle — el archivo `repos/carga_usuarios.py`
tiene los stubs con firma y el mapeo al método original):

| Función | Porta de | Botón/pestaña original |
|---|---|---|
| `probar_conexion(service_key, url)` | `test_conexion_supabase` | "🔧 Probar Conexión" |
| `buscar_usuario_auth(email, ...)` | `buscar_usuario_por_email_auth` | "🔍 Verificar Usuario" |
| `buscar_usuario_profiles(email)` | `buscar_usuario_en_profiles_solo` | "👤 Profiles" |
| `crear_o_actualizar_usuario(datos)` | `crear_usuario_supabase` + `crear_actualizar_individual` | "👤 Crear/Actualizar" |
| `resetear_password(user_id, nueva)` | `resetear_password_usuario` | "🔄 Resetear Contraseña" |
| `generar_password_segura(length=8)` | `generar_password_segura` | "🎲 Generar" |
| `validar_password(pwd)` | `validar_password` | (validación inline) |
| `parsear_usuarios_pegado(texto)` | (parsing en `procesar_datos`) | "🧪 Procesar Datos" |
| `listar_usuarios()` | `verificar_usuarios_existentes` + merge Auth/profiles | "👥 Listar Todos" |

## Rebanada (si se hace módulo web)

- `core/repos/carga_usuarios.py` (o `core/repos/usuarios_auth.py`)
- `insevig_web/states/carga_usuarios_state.py`
- `insevig_web/pages/carga_usuarios/*.py` (ver `carga_usuarios_UI.md` → 4 rutas)
- `tests/unit/test_carga_usuarios_*.py`
- este documento

## Datos

- **Supabase Auth Admin API** del proyecto sanciones: `POST /auth/v1/admin/users`,
  `PUT /auth/v1/admin/users/{id}`, `GET /auth/v1/admin/users`.
- Tabla `profiles` (`POST`/`GET /rest/v1/profiles`).
- Requiere **SERVICE key** (no ANON). Nunca exponerla al frontend — todas estas
  llamadas van server-side (`core/repos/`).

## Rutas y permisos (si aplica)

| Ruta | Acción |
|---|---|
| `/carga-usuarios/individual` | `usuarios_auth.crear` |
| `/carga-usuarios/masivo` | `usuarios_auth.crear` |
| `/carga-usuarios/listado` | `usuarios_auth.ver` |
| `/carga-usuarios/reset` | `usuarios_auth.reset` |

## Riesgos / decisiones abiertas

- ¿Este proyecto Supabase (sanciones) sigue vivo tras la migración a Reflex, o
  el frontend de sanciones (Flutter) también se retira? Si se retira, este
  módulo no tiene sentido.
- Manejo de contraseñas en claro al generarlas masivamente (el legado las
  guarda en un `.txt` junto al script) — en la web hay que decidir cómo se
  entregan (descarga única, email, etc.).

## Criterio de "hecho"

- [ ] Decisión de producto: módulo web / utilidad / se descarta.
- [ ] Si va: SERVICE key solo server-side, nunca en el bundle del cliente.
- [ ] Contraseñas generadas: mecanismo de entrega definido y auditado.
