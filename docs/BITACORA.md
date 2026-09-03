# Bitácora de la migración a Reflex

Registro cronológico del trabajo. El plan de fondo está en
`~/.claude/plans/wise-soaring-turing.md`; el detalle por módulo en `docs/modulos/`;
las reglas intocables en `docs/CONTRATOS.md`.

## Sesión 2026-09-03

### Decisiones tomadas con el usuario
1. **Auth**: tabla de usuarios propia + roles `admin` / `editor` / `consulta`.
2. **v1**: se mantiene el selector dual SQL Server + Supabase para lecturas;
   las escrituras van solo a SQL Server, y lo mínimo (SQL Server 2008 R2 es
   obsoleto). Superficie de escritura: `RPEMPLEA`, `RPEMPOBSERV`, `RPINGDES`.
3. **Futuro (Fase 7)**: la fuente de verdad pasará a **Supabase en la nube**, con
   **Postgres local + sincronización** (offline-first) porque el servidor tiene
   Internet intermitente. No se construye en v1, pero el diseño no cierra esa puerta.
4. **Alcance**: los 8 módulos migrados antes del cutover.
5. **Hosting**: Windows Server interno, ~10 usuarios, funciona en LAN sin Internet.
   **Vercel/cloud descartado** (Reflex necesita backend persistente + no ve la red
   privada 192.168.2.115).
6. **Modularidad para agentes**: cada módulo = rebanada vertical de archivos;
   contratos congelados; `tests/test_arquitectura.py` verifica los límites.
7. **UI responsive**: sidebar fijo en escritorio / drawer en móvil, sistema de
   diseño único en `components/ui/`, nada > 300 ms bloquea la UI (va a Job).

### Repos respaldados en GitHub
- `NOMINA_ROLES_SISTEMA_INSEVIG` (principal) — rebase sobre 11 commits del remoto
  que no estaban locales; conflictos resueltos (`.gitignore`, `biess_limpiar_cedula`).
- `HISTORIAL PRESTAMOS` → `Alcano3520/PRESTAMOS_HISTORIAL_INSEVIG` (commit `fd5abe2`).
- `TOTAL_OSERVACIONES` → **repo nuevo privado** `Alcano3520/TOTAL_OBSERVACIONES_INSEVIG`
  (con `.gitignore`; se sacaron del índice binarios de PyInstaller y `.db`).

### Commits de la migración (rama `main`)
| Commit | Contenido |
|---|---|
| `c58c205` | Esqueleto Reflex + andamiaje de modularidad (registry, ui/, CONTRATOS) |
| `cea9ef3` | `core/audit`, `core/jobs` (JobRunner), `core/storage`, pool SQL Server |
| `de3d442` | La app Reflex arranca (login, auth, dashboard, rutas) |
| `3f083a6` | Forzar modo claro en Radix (`custom_attrs data-appearance`) |
| `e9366dd` | **Fase 1** — Reportes (consolidado + comparador SQL vs Supabase) |
| `918b568` / `f773b14` | Fix: página no cargaba (`setvar`), job de reportes, panel de progreso |
| `ae9db3f` | **Fase 2** — Préstamos, Observaciones, Historial de empleado (lectura) |
| `dff92ae` | **Fase 3** — Empleados CRUD + carga masiva + escritura de observaciones (auditadas) |
| `5fb0837` | **Fase 4** — Roles de pago en PDF (individual + lote ZIP) |
| `8672176` | **Fase 5** — Envío de roles (SMTP/Graph) + Registrador BIESS + módulo Admin |
| `ee40118` | **Módulo 8** — bitacora (Agenda de cobro de liquidación de haberes) |
| `f5063ee` | Fix: observaciones no compilaba + test que valida las 21 páginas |

### Estado al cierre de la sesión
- `core/` completo para los 8 módulos: config, concepts, datos (de-duplicado),
  db, audit, jobs, storage, repos (nomina, prestamos, observaciones, empleados,
  registrador, bitacora), excel, pdf, email, narrativa, migración SQLite→Postgres.
- `insevig_web/`: 8 módulos, **21 páginas que compilan**, shell responsive,
  auth local + roles + permisos.
- **71 tests unitarios verdes** (con fakes, sin BD real). `ruff` + `mypy core` limpios.
- **NO probado contra SQL Server (192.168.2.115) ni Supabase reales** — el entorno
  no los alcanza.

### Problemas técnicos encontrados
- Reflex 0.9.10: `reflex export --backend-only` **NO valida el JSX de las páginas**.
  Validación real = `tests/test_arquitectura.test_todas_las_paginas_compilan`.
- `rx.State` 0.9.10 no genera setters automáticos → hay que declarar
  `@rx.event def set_x`.
- El `fn` de un Job no puede leer el `self` de Reflex desde el hilo del pool →
  capturar todo como locales.
- SQLite + JobRunner (hilos) → `poolclass=NullPool` en `core/db/appdb`.
- `reflex-components-radix 0.9.8` descarta el prop `appearance` → modo claro
  forzado con `custom_attrs={"data-appearance": "light"}`.
- Warnings de dev-mode (`Frontend version 0.9.8 vs 0.9.10`, `dispatch[substate]`):
  ruido, no rompen las páginas.
