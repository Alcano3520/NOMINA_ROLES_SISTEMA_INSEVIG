# Plan de implementación — lo que falta y cómo añadir más módulos

Contexto y arquitectura: `~/.claude/plans/wise-soaring-turing.md` y `docs/CONTRATOS.md`.
Historial: `docs/BITACORA.md`.

---

## Parte A — Terminar los 8 módulos actuales

Todos tienen interfaz Reflex y lógica `core/`, pero **nada se ha probado contra el
SQL Server (`192.168.2.115`) ni el Supabase reales**. Orden sugerido:

### A0. Poner en marcha el entorno de pruebas (bloqueante)
- [ ] `.env` con credenciales reales: `SQLSERVER_*` (crear logins `insevig_ro`
      SELECT e `insevig_rw` con grants mínimos, **no `sa`**), `SUPABASE_URL/KEY`
      (rotar el JWT filtrado en git), `APP_DB_URL` (Postgres nuevo).
- [ ] **Spike TLS 1.0**: probar `.venv/bin/python -c "from core.db.health import
      sqlserver_disponible; print(sqlserver_disponible())"` desde una máquina con
      línea de vista al `192.168.2.115`. Si falla: parchear la BD (SP3+KB3144114)
      o reactivar SCHANNEL TLS 1.0 Client en Windows. Sin esto no se prueba nada
      contra SQL Server.
- [ ] `pip install -e ".[web,dev]"`, `python -m insevig_web.seed`, `reflex run`.
- [ ] alembic para la BD de la app: `reflex db init` + primera migración (hoy se
      crean tablas con `SQLModel.metadata.create_all`, sirve para dev, no para prod).

### A1. Validación por módulo (comparar con el legado)
Para 8–10 empleados y 1 período, cada salida debe coincidir con el `.pyw` actual:

| Módulo | Qué validar | Riesgo |
|---|---|---|
| Reportes | consolidado actual + histórico (RPHISTOR ~2.5M) + comparador | pool SQLAlchemy para el histórico; nombres de tabla Supabase (`rpingdesres`/`rphistor_temp`) |
| Préstamos | historial combinado (RPINGDES + RPHISTOR + migrado) + saldos + narrativa IA | dedupe de la vista combinada; cargar el SQLite con `python -m core.migrations_legacy.sqlite_to_appdb <ruta>` |
| Observaciones | obs / multas (CLASE 203) / faltas (RPHORTOT, RPHORHIS) | nombres de tablas `rphortot`/`rphorhis` en Supabase (verificar) |
| Empleados | buscar, editor (hoy ~32 de 68 campos de RPEMPLEA), CRUD auditado, carga masiva | **ampliar `GRUPOS` en `core/repos/empleados.py`** a los 68 campos si RRHH los usa; probar concurrencia optimista con 2 sesiones |
| Roles PDF | **paridad pixel** con los roles reales | comparar texto+posición con `pypdf` contra PDFs "golden" del legado; ajustar `core/pdf/rol_pago.py` |
| Envío | lote a buzones internos, intervalo, sin doble envío | registrar app en Entra ID (Graph) o cuenta SMTP; SPF/DKIM |
| Registrador | import BIESS + posteo a RPINGDES con dedupe; alta manual | **hoy acotado**: faltan las pestañas Egresos/Ingresos agrupados y Consulta/Edición del legado; añadirlas si se necesitan |
| Bitácora | CRUD contra Supabase `agenda_cobro_registros` | confirmar el nombre real de la tabla; importar `agenda_liquidacion.db` si tiene datos |

### A2. Profundidad pendiente conocida
- **Empleados**: editor de 68 campos completo; búsqueda avanzada multi-criterio;
  exportar catálogos DBTABLAS; imprimir ficha del empleado en PDF.
- **Registrador**: las 6 pestañas del legado (hoy solo BIESS + manual).
- **Roles**: preview del PDF embebido en la página (`<iframe>`); logo automático.
- **Reportes**: prueba de integración `test_concepts_cubre_periodo_real` (que el
  mapa CLASE→concepto cubra todas las CLASE de un período real).
- **Auditoría**: filtros por módulo/usuario/fecha en `/admin/auditoria`;
  `admin/roles` editable (hoy solo lectura de la matriz por defecto).

---

## Parte B — Cómo añadir un módulo nuevo (receta)

Cada módulo `<mod>` es una **rebanada vertical**. Un agente puede recibir "implementa
el módulo X" y tocar SOLO estos archivos:

```
core/repos/<mod>.py                 # queries + operaciones; NO importa otro repo
core/excel/<mod>_*.py               # builders/parsers propios (si aplica)
core/<dominio>/                      # pdf/, email/... propio (si aplica)
insevig_web/states/<mod>_state.py    # estado + event handlers
insevig_web/pages/<mod>/*.py         # páginas (@rx.page)
insevig_web/components/<mod>/*.py    # componentes solo de este módulo (si aplica)
tests/unit/test_<mod>.py             # + tests/integration/ si toca BD
docs/modulos/<mod>.md               # ficha (copiar de _PLANTILLA.md)
```

Y **registrar** una línea en `insevig_web/registry.py` (`ModuleSpec`) + añadir el
módulo a `auth.PERMISOS_POR_DEFECTO` (los 3 roles) + a `_TODOS_MODULOS` +
a `MODULOS` en `tests/test_arquitectura.py` + a `pages/__init__.py`.

Reglas (`docs/CONTRATOS.md`): reutilizar `core.datos.service`, `core.concepts`,
`core.db.*`, `core.audit`, `core.jobs`, `core.storage`, `components/ui/*`,
`components/layout.pagina`, `AuthState`, `DataSourceState`. Escrituras a SQL Server
solo por `core.audit.audit_scope`. Toda operación > 300 ms → Job.

**Checklist de "hecho"** para un módulo:
- [ ] `pytest` (unit) verde para el módulo
- [ ] `ruff check` + `mypy core` limpios
- [ ] `tests/test_arquitectura.py` pasa (la página compila, no cruza repos)
- [ ] paridad con el legado para una muestra
- [ ] revisado a 360 / 768 / 1280 px

---

## Parte C — Módulos candidatos (otros proyectos INSEVIG)

Proyectos hermanos en `~/Documentos/mis_proyecto/` que son de RRHH y podrían
integrarse. **Prioridad = decidirla con RRHH.** Requieren el mismo análisis previo
que se hizo para los 8 primeros (leer su `CLAUDE.md`, mapear queries, decidir
fuente de datos).

| Proyecto | Qué es | Stack actual | Notas para migrar |
|---|---|---|---|
| `LIQUIDACIONES_SISTEMA_INSEVIG` | Genera liquidaciones/finiquitos (PDF + QR) | Tkinter → ya migrado a Supabase | Encaja bien; comparte empleados; genera PDF (como Roles) |
| `VACACIONES_SISTEMA_INSEVIG` | Solicitudes y saldos de vacaciones | Tkinter + pyodbc + Supabase | CRUD + cálculo de saldo; escribe a RPINGDES o tabla propia |
| `sistema_sanciones_RRHH` | Flujo de sanciones (supervisor → RRHH) con estados | Tkinter | Workflow con estados (como bitacora); `admin_panel.py` |
| `sistema_sanciones_insevig` / `novedades_insevig` | Sanciones / novedades operativas | **Flutter** (móvil + web) | Ya son web/móvil; decidir si se absorben o se dejan aparte |
| `cargador_faltas` | Carga masiva de faltas/permisos/suspensiones | Tkinter | Similar a carga masiva de empleados; escribe RPHORTOT/faltas |
| `gestion_rrhh_parametrizacion` | Maestros: clientes, puestos, cálculo de horas extra | Tkinter + `api.py` (FastAPI) | Parametrización → tablas propias; ya tiene una API |
| `Coincidencia_Difusa_Empleados` | Emparejado difuso de nombres de empleados | Tkinter | Utilidad; podría ser un helper de `core/` reutilizable |
| `ENVIO_CORREOS_SANCIONES` / `ENVIO_CORREOS_ATEMPORALES` | Envío de correos de sanciones/otros | Python | Reutilizan `core/email` — casi solo UI y plantillas |
| `MEMOS` | Gestión de memorandos | Python + DB | CRUD + PDF |
| `sistema_reportes` | Sistema de reportes | ? | Revisar solapamiento con el módulo Reportes actual |
| `NOMINA_SYSTEM_RRHH` / `sai-nomina-tkinter` | Sistema de nómina SAI (Tkinter) | Tkinter | Grande; revisar si sustituye o complementa lo actual |

**Orden recomendado** (por afinidad con lo ya hecho y valor):
1. `LIQUIDACIONES_SISTEMA_INSEVIG` — reutiliza empleados + generación PDF.
2. `VACACIONES_SISTEMA_INSEVIG` — CRUD + saldo, patrón conocido.
3. `sistema_sanciones_RRHH` + `ENVIO_CORREOS_SANCIONES` — workflow + `core/email`.
4. `cargador_faltas` — encaja con Observaciones/Faltas.
5. `gestion_rrhh_parametrizacion` — maestros; base para cálculos de otros módulos.
6. `MEMOS`, `sistema_reportes`, resto — según necesidad de RRHH.

Para cada uno: crear `docs/modulos/<mod>.md` con la plantilla y seguir la receta
de la Parte B.

---

## Parte D — Despliegue y cutover (Fase 6)

1. **Windows Server**: Python 3.12 + venv, Node LTS, ODBC Driver 17, PostgreSQL 16
   local, Caddy (reverse proxy HTTPS) o IIS+ARR, servicio Windows vía NSSM.
   `reflex export` (frontend estático) + `reflex run --env prod --backend-only`
   (1 proceso). `.env` con ACL restringida.
2. **Backups**: `pg_dump insevig_app` diario + copia de `STORAGE_DIR`.
3. **Piloto en paralelo**: 1–2 ciclos de nómina con la web y el Tkinter a la vez;
   reconciliar; cero diferencias inexplicadas.
4. **Cutover**: congelar los `.pyw`, retirar PyInstaller, archivar repos anidados.
5. **Seguridad**: rotar JWT Supabase y password `sa`; `git rm --cached
   config/supabase_credentials.txt` + reescribir historia si hace falta.

---

## Parte E — Fase 7 (posterior) — Supabase-nube + offline-first

Migrar el esquema y los datos a un modelo propio en Supabase; Postgres local como
BD operativa; worker `core/sync/` (pull de Supabase + push de un *outbox*); cola
de conflictos; retirar SQL Server. La app apunta sus `core/repos/*` a la fuente
`"local"`. Se planifica aparte cuando v1 esté estable.
