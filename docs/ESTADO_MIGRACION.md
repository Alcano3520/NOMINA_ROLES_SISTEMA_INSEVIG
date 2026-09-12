# Estado de la migración — INSEVIG RRHH → Reflex web

> **Leé esto primero.** Es el índice vivo de dónde está todo, qué falta, qué NO
> se toca y cómo dos personas (o dos sesiones de IA) trabajan sin pisarse.
> Última actualización: 2026-09-10.

---

## 1. Qué es este repo

`NOMINA_ROLES_SISTEMA_INSEVIG` es el **destino** de una migración: las ~15 apps
de escritorio Tkinter de RRHH/Nómina de INSEVIG se están reescribiendo como
**una sola app web Reflex**, servida en el servidor NAS de la empresa
(`http://192.168.2.181:3000`).

Cada app vieja se "anexa" como un **módulo** (ver §6). No se migra todo de una
vez: es incremental, un módulo por vez, y el legado se retira cuando su
contraparte web llega a paridad.

### Arquitectura (3 capas)

```
core/            lógica de negocio pura, SIN UI, testeable con pytest
                 (repos/, excel/, pdf/, email/, faltas/, sanciones/, ...)
insevig_web/     app Reflex: pages/, states/, components/, registry.py
alembic/ + models  BD propia de la app (Postgres/SQLite): auth, auditoría, jobs
```

Tres fuentes de datos:
- **SQL Server 2008 R2** (`192.168.2.115`, BD `insevig`) — fuente de verdad,
  lectura; escritura solo lo mínimo (ver `docs/CONTRATOS.md`).
- **Supabase** — espejo de lectura + tablas de módulo. Dos proyectos:
  `buzcapcwmksasrtjofae` (empleados/nómina) y `syxzopyevfuwymmltbwn` (sanciones).
- **BD de la app** (Postgres local en el NAS) — auth, permisos, auditoría.

El selector de fuente cae solo a Supabase si SQL Server no responde
(`core/db/health.fuente_por_defecto`).

---

## 2. Cómo clonar todo

Todo vive bajo `~/Documentos/mis_proyecto/` como carpetas hermanas. El repo web
espera encontrar los proyectos-fuente **al lado**, no adentro.

```bash
mkdir -p ~/Documentos/mis_proyecto && cd ~/Documentos/mis_proyecto

# 1. El repo web (destino) — donde se trabaja
git clone https://github.com/Alcano3520/NOMINA_ROLES_SISTEMA_INSEVIG.git

# 2. Repos-fuente YA usados (referencia viva, NO se tocan). El repo web los
#    espera como carpetas hermanas con el nombre de la izquierda:
git clone https://github.com/Alcano3520/sistema_sanciones_RRHH.git                 sistema_sanciones_RRHH
git clone https://github.com/Alcano3520/liquidaciones-generator.git                LIQUIDACIONES_SISTEMA_INSEVIG
git clone https://github.com/Alcano3520/VACACIONES_SISTEMA_INSEVIG.git             VACACIONES_SISTEMA_INSEVIG
git clone https://github.com/Alcano3520/Agenda_Liquidacion_Haberes_INSEVIG.git     BITACORAS_AGENDA_EGRESOS_FORMATOS
git clone https://github.com/Alcano3520/GESTION_EMPLEADOS_INSEVIG.git              GESTION_EMPLEADOS_INSEVIG

# 3. Repos anidados dentro del repo web (ya vienen copiados; clonalos aparte solo
#    si vas a trabajar SU código directamente):
git clone https://github.com/Alcano3520/TOTAL_OBSERVACIONES_INSEVIG.git
git clone https://github.com/Alcano3520/PRESTAMOS_HISTORIAL_INSEVIG.git
```

Los módulos `empleados`, `roles`, `registrador`, `reportes` se portaron desde
carpetas Tkinter que ya viven **dentro** del repo web — no hay repo hermano que
clonar para esos.

Cuando toque anexar otra app de RRHH, se clona su repo como carpeta hermana y se
sigue el patrón de §6. **El inventario completo (usados + pendientes) está en §8.**

**NO clonar / NO tocar:** `rpa_bot_mrl`, `rpa-bot-mrl`, `ingresosMrl`
(automatización MRL, es otro asunto), ni los proyectos no-RRHH del directorio
(trading, inventario, facturación/SRI, GPS, etc. — ver §8).

---

## 3. Entorno de desarrollo

```bash
cd NOMINA_ROLES_SISTEMA_INSEVIG
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[web,dev]"

cp .env.example .env          # completar SUPABASE_* si vas a probar contra datos reales
                              # sin .env, los tests corren igual (usan fakes)

# comprobaciones antes de cada commit
ruff check core/ insevig_web/ tests/
mypy --config-file pyproject.toml core/
pytest                        # 306 tests, ~4s, sin red

# correr la app local
reflex run                    # http://localhost:3000  (login admin/admin tras seed)
python -m insevig_web.seed    # crea el usuario admin + permisos por defecto
```

`reflex export --backend-only --env prod` es la validación que hace el deploy:
compila todas las páginas. Si pasa, el deploy no va a romper por JSX.

---

## 4. Despliegue

**No despliega el que programa.** El NAS lo maneja una sesión aparte
(`NAS_SERVER`, Remote Control sobre el servidor Windows). El flujo:

1. `git push origin main`
2. Pedir a `NAS_SERVER`: `deploy/windows/deploy-nas.ps1 -SoloActualizar`
   (git pull + `pip install` + `alembic upgrade` + `seed` + restart + healthcheck).
3. **Un deploy por vez, esperar confirmación.** Deploys encimados dejaron un
   socket huérfano en el puerto 3000 (WinError 10048). NSSM AppThrottle está en
   10 s por eso.
4. El seed es incremental: al agregar un módulo, re-sembrar añade sus permisos
   para los roles existentes.

GitHub Actions solo dispara build si el push toca `core/**`, `insevig_web/**`,
`assets/**`, `alembic/**`, `scripts/**`, `pyproject.toml`, `rxconfig.py`.

---

## 5. Estado por módulo

| Módulo | Rutas | Estado | Origen (app vieja) |
|---|---|---|---|
| `empleados` | `/empleados/{buscar,avanzada,historial,carga-masiva}` | ✅ funcional | `empleados/SISTEMA_GESTION_EMPLEADOS_10.pyw` |
| `roles` | `/roles/{generar,lote}` + `/envio` | ✅ funcional | `roles/Roles_Principal.pyw`, `envio_roles/` |
| `registrador` | `/registrador` | ✅ funcional | `registrdor_vizulizador_egresosingresos/` |
| `reportes` | `/reportes/consolidado` (+ comparador en admin) | ✅ funcional | `reportes/reporte_nomina_GUI.pyw` |
| `prestamos` | `/prestamos/{historial,saldos}` | ✅ funcional | `prestamos/HISTORIAL_PRESTAMOS_10.pyw` |
| `observaciones` | `/observaciones` + carga masiva | ✅ funcional | `observaciones/TOTAL_OSERVACIONES_4_0.pyw` |
| `liquidaciones` | `/liquidaciones` + editor/guardadas/descuentos | ✅ funcional (motor con 1 bug abierto de totales) | `LIQUIDACIONES_*` |
| `bitacora` | `/bitacora` | ✅ funcional | agenda de cobro de liquidaciones |
| `vacaciones` | `/vacaciones` | ✅ funcional | `VACACIONES_SISTEMA_INSEVIG` |
| `admin` | `/admin/{usuarios,roles,auditoria,parametros,config}` | ✅ funcional | — |
| **`sanciones`** | `/sanciones/{bandeja,historial,buscar,novedades,estadisticas}` | 🟡 desplegado; **falta `SUPABASE_SANCIONES_SERVICE_KEY` en el `.env` del NAS** + verificación de paridad en uso real | `sistema_sanciones_RRHH/main.py` |
| **`faltas`** | `/faltas/{periodo,individual,masivo,restas}` | 🟡 desplegado y leyendo; falta verificación de paridad en uso real + revisión responsive | `sistema_sanciones_RRHH/gestion_faltas.py` |
| **`maniobras`** | → `/registrador` (ya cubre CLASE 110/203) | ✅ FASE -1 cerrada sin trabajo | `sistema_sanciones_RRHH/registro_maniobras.py` |
| **`carga_usuarios`** | `/carga-usuarios/{individual,listado,reset,masivo}` | 🟡 desplegado; **falta `SUPABASE_SANCIONES_SERVICE_KEY`** | `sistema_sanciones_RRHH/carga maciva usuarios6.0.py` |

Detalle de cada uno en `docs/modulos/<mod>.md`. Los cambios de contrato de la
migración de sanciones (C1–C6) están en `docs/modulos/CAMBIOS_CONTRATO_SANCIONES.md`.

### Pendientes conocidos (cualquiera puede tomarlos)

- **Rotar credenciales filtradas en git**: JWT `service_role` de Supabase de
  nómina, password `sa` del SQL Server, y las SERVICE keys del proyecto de
  sanciones (están hardcodeadas en `sistema_sanciones_RRHH/config.py`).
- ~~Corrección de dato de producción MATICUREMA~~ — **hecho 2026-09-12**:
  liquidación `b2d6698b-1260-4928-b05e-02d5376fc378` corregida de $3.50 a
  $184.25 vía `editar_valores_liquidacion` (recalcula con la fórmula ya
  arreglada; queda auditado en `liquidaciones_historial_estados`, usuario
  `correccion_maticurema_2026-09`).
- **Bug del motor de liquidaciones: totales negativos / "Grupo 2" — causa
  encontrada 2026-09-12, falta la regla de negocio para cerrarlo.**
  `DESCUENTOS_MULTI_MES` (`core/repos/liquidaciones.py:38`) suma TODAS las
  cuotas futuras programadas de `PRESTAMOS_COMPANIA` (hasta 36 meses) como un
  solo descuento — para préstamos con amortización larga (>1 año) esto cobra
  el saldo completo de golpe y da totales muy negativos. Casos reales:
  cédula `2100696455` (27 cuotas de $100 hasta oct-2028, liquidación
  `a3dbae72-ba84-4555-a3a9-f60c65d0173c`, real RRHH $809.93 vs motor
  -$1990.08) y cédula `0941345589` (13 cuotas de $100, liquidación
  `50e53e0b-03a4-4760-b7a0-f5780f7f42b7`, real $66.02 vs motor negativo). NO
  es la sección "todo incluido" la causa (coincidencia). Falta decidir la
  regla: ¿se cobra solo lo vencido a la fecha de salida? ¿se topa en $0 y el
  resto queda como cuenta por cobrar aparte? ¿se limita a N meses? — pendiente
  de decisión del usuario, preguntado el 2026-09-12.
- `_utilitarios/` — apps sueltas de RRHH por absorber (ver §6 + su README).

---

## 6. El patrón para anexar una app vieja como módulo

Cada app de escritorio de RRHH se vuelve una **rebanada vertical**
(exactamente estos archivos, ningún otro):

```
core/repos/<mod>.py                 lógica de datos (+ core/<dominio>/ propio)
core/excel/<mod>_*.py               builders/parsers con prefijo <mod>_
core/pdf/<mod>_*.py                 si genera PDFs
insevig_web/states/<mod>_state.py   todo el estado y event handlers
insevig_web/pages/<mod>/*.py        las páginas/rutas
tests/unit/test_<mod>_*.py
docs/modulos/<mod>.md               contrato + estado del módulo
```

Y **una línea** en `insevig_web/registry.py` (`ModuleSpec`). La shell
(sidebar, layout) NO se toca — se auto-arma desde el registry.

### Proceso

1. **FASE -1** (obligatoria): abrir el/los `core/repos/*` existentes que
   pudieran solaparse y decidir explícitamente extender / reemplazar / módulo
   aparte. Nunca "portar de cero" sin mirar.
2. Si hace falta tocar un archivo **congelado** (`docs/CONTRATOS.md` §"Archivos
   congelados": `registry.py`, `auth.py`, `core/config.py`, `models.py`,
   `components/*`, tokens de tema, `tests/test_arquitectura.py`), preparar el
   cambio como **un bloque único** y pedir OK al usuario antes de mergear.
   Alta de un módulo nuevo = tocar `registry.py` + `MODULOS` en
   `tests/test_arquitectura.py` + `auth._TODOS_MODULOS` + `PERMISOS_POR_DEFECTO`
   + una sección en `components/sidebar.py`.
3. **Trasplante, no reescritura**: copiar las queries/fórmulas/orden de pasos
   igual; adaptar solo el transporte (`requests` → `supabase-py`, Tkinter → Reflex).
4. Los **bugs del legado** se replican con nota `# LEGADO: <bug> — [replicado |
   corregido]: <por qué>`; los que son decisión de negocio se escalan al usuario.
5. Escrituras a SQL Server: `dry_run` / vista previa + `core.audit.audit_scope`.
   Superficie permitida: `RPEMPLEA`, `RPEMPOBSERV`, `RPINGDES`, `RPHORTOT`.
6. Cerrar: `ruff` + `mypy core` + `pytest` verdes, `reflex export` compila,
   actualizar `docs/modulos/<mod>.md` y la tabla de §5 de este archivo.

`_utilitarios/` guarda las apps sueltas todavía sin absorber (no se despliega,
es material de origen). Su `README.md` tiene la tabla de seguimiento.

---

## 7. Cómo NO pisarse (dos personas / dos sesiones)

- **Todo va a `main` en GitHub**, commiteado y pusheado apenas queda un cambio
  coherente. Nada se queda local. `git pull` antes de empezar, siempre.
- **`git log --oneline`** es la fuente de verdad de qué se hizo. Los mensajes de
  commit dicen qué archivos toca y por qué.
- **Un módulo por persona.** Los tests de `tests/test_arquitectura.py` fallan si
  dos módulos se importan entre sí o si el registry queda incoherente.
- Antes de tocar un archivo de `docs/CONTRATOS.md` §"Archivos congelados":
  avisar / coordinar. Ese cambio afecta a todos los módulos.
- Este archivo (`ESTADO_MIGRACION.md`) + `docs/modulos/<mod>.md` se actualizan
  **en el mismo commit** que el código. Si no está acá, no pasó.
- Sesiones de IA que participaron: la migración de `sistema_sanciones_RRHH` la
  coordinaron dos sesiones — una en el repo de staging (`sistema_sanciones_RRHH`,
  extrajo la lógica a `nucleo_modular/`) y otra en este repo (portó a
  `core/` + `insevig_web/`). El deploy lo hace una tercera sesión sobre el NAS.
  Nada de eso queda en git salvo lo que está en este archivo y en `docs/`.

---

## 8. Inventario de repos a anexar

Todos son de `github.com/Alcano3520/`. **La columna "destino" es la mejor
estimación por nombre/README — el usuario confirma cada una antes de arrancar.**
El proceso para cada uno: FASE -1 (§6) → propuesta de contrato si toca congelado
→ rebanada → tests → actualizar este archivo.

### 8a. Repos YA USADOS como fuente (los que ya se consumieron)

Estos ya se portaron a un módulo. Se clonan para **reproducir el set completo de
trabajo** (el repo web espera encontrarlos como carpetas hermanas). No se tocan —
son referencia viva.

| Repo (carpeta) | Clone URL | Produjo el módulo |
|---|---|---|
| `sistema_sanciones_RRHH` | `github.com/Alcano3520/sistema_sanciones_RRHH.git` | `sanciones` · `faltas` · `maniobras` · `carga_usuarios` |
| `LIQUIDACIONES_SISTEMA_INSEVIG` | `github.com/Alcano3520/liquidaciones-generator.git` | `liquidaciones` |
| `VACACIONES_SISTEMA_INSEVIG` | `github.com/Alcano3520/VACACIONES_SISTEMA_INSEVIG.git` | `vacaciones` |
| `BITACORAS_AGENDA_EGRESOS_FORMATOS` | `github.com/Alcano3520/Agenda_Liquidacion_Haberes_INSEVIG.git` | `bitacora` |
| `TOTAL_OSERVACIONES` (repo anidado) | `github.com/Alcano3520/TOTAL_OBSERVACIONES_INSEVIG.git` | `observaciones` |
| `HISTORIAL PRESTAMOS` (repo anidado) | `github.com/Alcano3520/PRESTAMOS_HISTORIAL_INSEVIG.git` | `prestamos` |
| `GESTION_EMPLEADOS_INSEVIG` | `github.com/Alcano3520/GESTION_EMPLEADOS_INSEVIG.git` | `empleados` (carga masiva, historial) — parcial |

Los módulos `empleados`, `roles`, `registrador`, `reportes` se portaron desde
carpetas Tkinter que ya viven **dentro** de este repo (`empleados/`, `roles/`,
`envio_roles/`, `registrdor_vizulizador_egresosingresos/`, `reportes/`,
`prestamos/`, `observaciones/`) — no hay repo hermano que clonar para esos.

### 8b. Repos candidatos, todavía sin portar

Todos de `github.com/Alcano3520/`. **La columna "destino" es estimación por
nombre/README — el usuario confirma cada una.** Proceso: FASE -1 (§6) →
contrato si toca congelado → rebanada → tests → actualizar este archivo.

| Repo | Clone | Módulo destino |
|---|---|---|
| `empleados_app` | `…/empleados_app.git` | `empleados` (FASE -1) |
| `EmpleadosSupabase` | `…/EmpleadosSupabase.git` ⚠️ el remote local trae un token `gho_…` — usar URL limpia y **rotar el token** | `empleados` (sync Supabase) |
| `NOMINA_SYSTEM_RRHH` | `…/NOMINA_SYSTEM_RRHH.git` | `empleados` / `roles` (variante) |
| `sai-nomina-tkinter` (SAI) | `…/sai-nomina-tkinter.git` | sistema RRHH paralelo completo — **decidir con el usuario** si aporta algo o se descarta |

### 8c. Nuevos (todavía sin módulo asignado)

| Repo | Clone | Destino probable |
|---|---|---|
| `gestion_rrhh_parametrizacion` | `…/gestion_rrhh_parametrizacion.git` | `admin` / parámetros (secciones de nómina) |
| `programa_cambios` | `…/programa_cambios.git` | `sanciones` (cambios de turno/puesto) o módulo nuevo |
| `sistema_reportes` | `…/sistema_reportes.git` | ⚠️ es **Flutter** (frontend) — probablemente fuera de alcance |
| `novedades_insevig` | `…/novedades_insevig.git` | ⚠️ **Flutter** — fuera de alcance (ya cubierto por `sanciones/novedades`) |
| `N04_AGENDA` (omni_task) | `…/N04_AGENDA.git` | ⚠️ **Flutter** — agenda; ¿fuera de alcance? |
| `sistema_sanciones_insevig` | `…/sistema_sanciones_insevig.git` | ⚠️ **Flutter** de sanciones (lado supervisor) — fuera de alcance por ahora |
| `generador_comprobantes` | `…/generador_comprobantes.git` | `vacaciones` / `liquidaciones` (comprobantes) |
| `NOMBRADOR_EXTDATOSCARGAS` | `…/NOMBRADOR_EXTDATOSCARGAS.git` | herramienta: certificados de cargas familiares (utilidades) |
| `Coincidencia_Difusa_Empleados` | `…/Coincidencia_Difusa_Empleados.git` | herramienta: match difuso de empleados |
| `LECTOR_CEDULAS` | `…/LECTOR_CEDULAS.git` | herramienta: lector de cédulas → alta de empleado |
| `IESS_SELENIUM` | `…/IESS_SELENIUM.git` | herramienta / job RPA IESS |
| `MEMOS` | `…/MEMOS.git` | herramienta: memos / oficios |
| `MENSAJES_WHAP` | `…/MENSAJES_WHAP.git` | herramienta: WhatsApp masivo |
| `CAMBIO_VALOR_TXT` | `…/CAMBIO_VALOR_TXT.git` | herramienta chica |
| `GestionGoogleSheets` | `…/GestionGoogleSheets.git` | herramienta: integración Google Sheets |
| `SISTEMAS-RRHH-INVESTIGACION` | `…/SISTEMAS-RRHH-INVESTIGACION.git` | (repo vacío local — pedir contexto al usuario) |

### Correo (varios → un módulo `correo` nuevo, o anexos de `roles/envio`)

| Repo | Clone |
|---|---|
| `ENVIO_CORREOS_SANCIONES` | `…/ENVIO_CORREOS_SANCIONES.git` |
| `ENVIO_CORREOS_ATEMPORALES` | `…/ENVIO_CORREOS_ATEMPORALES.git` |
| `correo_jefe` | `…/correo_jefe.git` |
| `Correos_server_empre` | (sin remote — falta pushear) |
| `outlook_gestor` | `…/outlook_gestor.git` |
| `RastreaGastos_mail` | `…/RastreaGastos_mail.git` (¿RRHH? confirmar) |

### Excluidos (NO son RRHH — no anexar)

`rpa_bot_mrl` · `ingresosMrl` (MRL, otro asunto) · trading (`binance-trader-master`,
`freqtrade-develop`, `MoneyPrinter-main`, `TradingBotPro`, `TradingBotPro-v2`,
`CRIPTO_NUEVA`, `INVESTIGACION_INVERCION`) · inventario/logística (`*inventario*`,
`Inventory-Management-System-main`) · facturación/SRI (`facturacion_electronica*`,
`ANALICIS_PDF_SRI`, `sri_extraccion_facturas`) · GPS (`gps_guardian`, `GPS_TRAKER`)
· `NAVEGADOR_PEREIRA` (navegador Chromium) · misc (`abc_android`, `ANALICIS_PC`,
`APP_CUENTAS_123`, `CMD_CLUDE`, `Descargar_DATOS_BACHILLER`, `facebook_lector`,
`kali`, `OLLAMA`, `PAGINA_PUBLICACIONES`, `EnterpriseAIWorkspace`, `inicio_1`,
`generador_comprobantes` si resulta no-RRHH, `GestionGoogleSheets` idem).

> Si una clasificación está mal, corregila en este archivo — el usuario es la
> autoridad sobre qué es RRHH.

---

## 9. Contactos / infra

- GitHub: usuario `Alcano3520`, email `daniel3520@gmail.com`.
- NAS: `192.168.2.181` (o Tailscale `100.98.34.99`), servicio NSSM `insevig-web`,
  puerto 3000. Shares `Sistemas_Dev$` (código) y `Apps_Empresa$`.
- SQL Server: `192.168.2.115`, BD `insevig`, filtro `CODEMP='10' AND CODSUC='10'`.
- Detalle de red/credenciales: `docs/INFRAESTRUCTURA_RRHH.txt`.
