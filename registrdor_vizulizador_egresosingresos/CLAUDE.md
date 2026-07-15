# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

**Standalone, incomplete, NOT integrated into `Sistema_INSEVIG.pyw`.** Per `../PLAN_INTEGRACION.md` this module is "en espera" — possibly to be merged into `../HISTORIAL PRESTAMOS/` rather than integrated as-is. Confirm with the user before doing integration work here; don't assume it should be wired into the main dashboard.

## Running the app

```bash
python REGISTRAR_PRESTAMOS_UNIFICADO.pyw
```

Requires `pyodbc`, `pandas`, `pyperclip`, `openpyxl` (for `pd.read_excel`), and `msodbcsql17` (ODBC Driver 17 for SQL Server) installed on the system. No `requirements.txt` in this directory.

There is a hard, unresolved dependency on a missing module:

```python
try:
    from modulo_seguridad_prestamos import crear_respaldo_prestamo, log_operacion, CARPETA_RESPALDOS
    SEGURIDAD_DISPONIBLE = True
except ImportError:
    SEGURIDAD_DISPONIBLE = False
```

`modulo_seguridad_prestamos.py` does not exist anywhere in this repo. The app runs without it (header shows "● SIN SEGURIDAD" instead of "● SEGURIDAD ACTIVA"), but every edit/delete/insert path that calls `crear_respaldo_prestamo()` or `log_operacion()` is guarded by `if SEGURIDAD_DISPONIBLE` and silently skips backup/audit-logging when it's absent. Writes to production payroll data currently happen with **no backup and no audit trail**.

## Architecture

Single-class Tkinter app (`SistemaPrestamosUnificado`, ~5300 lines in `REGISTRAR_PRESTAMOS_UNIFICADO.pyw`) built around a `ttk.Notebook` with 6 tabs, each with its own `_build_*` method called from `_setup_ui()`:

| Tab | Builder method | Purpose |
|---|---|---|
| Préstamo Individual | `_build_tab_individual()` | Register one loan (CLASE 205), with installment planning |
| Carga Masiva Préstamos | `_build_tab_masiva()` | Bulk loan registration via a spreadsheet-like grid (`self.grid_data`) |
| Egresos / Ingresos | `_build_tab_todos_tipos()` | Register other movement types from `CLASES_SIMPLIFICADAS` (multas, anticipos, bonificaciones, etc.) |
| Registro Individual | `_build_tt_individual_tab()` | Single-row version of the Egresos/Ingresos tab |
| BIESS Quirografarios | `_build_biess_tab()` | Bulk-import BIESS loan deductions from an Excel file, matched to employees by cédula |
| Consulta / Edición | `_build_consulta_tab()` | Search, edit, and delete existing `RPINGDES` rows |

Unlike the read-only `../prestamos/` module, **this module writes** to SQL Server: `INSERT`, `UPDATE`, and `DELETE` on `RPINGDES`, plus counter updates on `RPCONTRL` (`ULT_EGR`/`ULT_ING`) to allocate the next movement number (`obtener_proximo_numero_egreso`, `obtener_proximo_numero_tipo`).

### Database

- **SQL Server** (`192.168.2.115` / database `insevig`, credentials hardcoded in `conectar_bd()`) — same schema as `../prestamos/`: `RPINGDES` (movements), `RPEMPLEA` (employee master), `RPCONTRL` (sequence counters). All queries fixed to `CODSUC=10, CODEMP=10`.
- No SQLite or Supabase access in this file (unlike sibling modules).
- Connection is established once in `SistemaPrestamosUnificado._conectar_bd()` (background thread, called via `master.after(100, ...)` after the UI is built) and stored as `self.conn` for the life of the app.

### Movement type registry

`CLASES_SIMPLIFICADAS` (top of file) maps CLASE code → `{concepto, codigo (EGR/ING), codsuc, codemp, tipo, aporta}` for the non-loan movement types handled by the "Egresos / Ingresos" and "Registro Individual" tabs. `CLASE_PRESTAMO = "205"` is handled separately by the loan-specific insert path (`insertar_prestamo`).

### Installment (cuota) calculation

Three strategies, chosen by tab/mode:
- `planificar_cuotas_inteligente()` — looks at `obtener_proyeccion_pagos_futuros_empleado()` to avoid overlapping an employee's existing scheduled deductions.
- `calcular_cuotas_tradicional()` — fixed number of equal installments from a start date.
- `calcular_cuotas_valor()` — solves for installment count given a fixed monthly value (VCM).

### BIESS import flow

`biess_procesar_excel()` reads an arbitrary Excel file (user picks header row and column letters for cédula/valor via the UI, converted with `biess_col_a_indice()`), consolidates duplicate cédulas by summing, then `biess_buscar_por_cedulas()` matches against `RPEMPLEA` (distinguishing `activo` vs `liquidado` by `ESTADO`). Only matched employees can be inserted.

### Threading

All SQL Server calls run in background `threading.Thread(daemon=True)` workers with results marshaled back to the UI via `self.master.after(0, callback)`. A shared `ThreadPoolExecutor(max_workers=4)` (`self.thread_pool`) also exists but most call sites use raw `threading.Thread` directly — treat `thread_pool` as legacy/partially-used rather than the sole concurrency mechanism. `self._running` is checked on close to avoid touching a destroyed UI from a still-running background thread.

## Critical quirks

- **`modulo_seguridad_prestamos` is missing** — see above. Any change that touches insert/update/delete paths should either restore this module or make the user aware that backups/audit logs are silently disabled.
- **Credentials hardcoded** in `conectar_bd()`: `sa / puntosoft123*`. Same credentials as other RRHH modules — do not commit elsewhere or expose.
- **CEDULA arrives as float from SQL** (e.g. `920116811.0`) — always normalize via `biess_limpiar_cedula()` or equivalent before comparing/displaying.
- **No TLS 1.0 / `openssl_legacy.cnf` workaround in this file** — unlike `../prestamos/HISTORIAL_PRESTAMOS_10.pyw`, this script does not set `OPENSSL_CONF` before importing `pyodbc`. If SQL Server connections fail with an SSL/TLS handshake error here, port that workaround over.
- **Icon loading** (`_set_icon`) expects `logo_insevig.ico`/`logo_insevig.png` next to the script; neither file exists in this directory (they live under `../HISTORIAL PRESTAMOS/src/`). Icon loading fails silently (caught and ignored) — cosmetic only.
- **Numbering is not transactional**: `obtener_proximo_numero_egreso()` reads `RPCONTRL.ULT_EGR` and `actualizar_ultimo_egreso()` writes it back in a separate statement — a race between two concurrent instances could allocate duplicate movement numbers.

## Reference documentation

Two large text files elsewhere in the repo apply to all RRHH modules (see `../prestamos/CLAUDE.md` for where they live and what they cover): `INFRAESTRUCTURA_RRHH.txt` (SQL Server creds, TLS workaround, Supabase config, PyInstaller packaging) and `INTERFAZ_GRAFICA_RRHH.txt` (Tkinter UI conventions, threading model, styles).

## Related modules

- `../prestamos/` — read-only loan history viewer (SQL Server + SQLite), likely integration target per `PLAN_INTEGRACION.md`.
- `../shared/obtener_datos.py` — cross-module employee/payroll data helpers; not currently used by this file, but has the canonical CLASE→concepto mapping that overlaps with `CLASES_SIMPLIFICADAS` here.
