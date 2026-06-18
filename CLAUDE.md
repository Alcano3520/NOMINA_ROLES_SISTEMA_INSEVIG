# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an integrated HR/Payroll system for INSEVIG with multiple desktop GUI applications for employee management, payroll processing, and reporting. The system integrates three data sources:

1. **SQL Server** (2008 R2) — source of truth for payroll data (RPEMPLEA, RPHISTOR, RPINGDES tables)
2. **Supabase** — cloud mirror + module-specific data
3. **SQLite** — local transactional database per module, with network backup on Roberto-PC

All applications are built with Tkinter/PyQt5 and compiled to Windows EXE via PyInstaller + GitHub Actions.

## Key Architecture

### Data Sources & Filtering

- **SQL Server**: All payroll queries require the filter `WHERE CODEMP='10' AND CODSUC='10'` (identifies INSEVIG within the shared ERP)
  - `RPEMPLEA` — employees (cedula, names, salary, hire date, etc.)
  - `RPHISTOR` — historical closed payroll (~2.5M rows)
  - `RPINGDES` — current open month payroll
  - **Read-only by policy** — ERP is the source of truth

- **Supabase** (project: buzcapcwmksasrtjofae):
  - Mirrors RPEMPLEA, RPHISTOR, RPINGDES
  - Module-specific tables with prefixes (vac_*, tur_*, per_*, etc.) 
  - Every change must log to `<prefix>_auditoria` table
  - Uses service_role key (in config/supabase.yaml, must be in .gitignore)

- **SQLite**: Local database per module at `/mnt/roberto-pc/ARCHIVOS ASISTENTE AOC/1.TURNOS/data/<module>.db` (or fallback to app directory)
  - Shared `empleados` cache table across modules
  - Module-specific tables (schemas defined in db.py)
  - Full CRUD support; write with `with get_connection(): conn.execute(...)`

### Networking

- **Roberto-PC** (192.168.2.80): Primary file server, SMB mount at `/mnt/roberto-pc`, guest access
  - EXE deployment path: `/mnt/roberto-pc/ARCHIVOS ASISTENTE AOC/1.TURNOS/`
  - SQLite database shared location
- **Denisse-PC** (192.168.2.118): Accounting/finance, SMB mount at `/mnt/denisse-pc`, username alcano/password 615013
- **SQL Server** (192.168.2.115): Requires TLS 1.0 legacy — loaded via `openssl_legacy.cnf` before importing pyodbc

### ODBC Driver Fallback

The system tries drivers in this priority order:
1. ODBC Driver 17 for SQL Server (preferred)
2. ODBC Driver 18 for SQL Server
3. ODBC Driver 13 for SQL Server
4. ODBC Driver 11 for SQL Server
5. SQL Server (Windows native fallback)

Function: `get_sql_conn()` in `sync_sqlserver.py`. Throws descriptive error if none connect.

## Current Modules

### SISTEMA_GESTION_EMPLEADOS_10.pyw (~2865 lines)
Main employee management GUI. Features:
- Employee search and CRUD from SQL Server
- Dark mode UI with INSEVIG color palette
- Threading for long operations
- Tooltips and keyboard shortcuts

### Roles_generador_VIZUALIZADOR_10.pyw (~1872 lines)
Payroll slip generator and visualizer:
- Generates PDF roles de pago with ReportLab
- Period/employee filtering
- Supports multiple name formats (cedula-nombre, etc.)
- Icon and workspace handling

### historial_empleado_GUI.pyw (~1323 lines)
Employee history viewer:
- Searches historical payroll data
- Date range filtering
- Summary statistics

### Reporting Tools
- **reporte_nomina_GUI.pyw** — unified report UI (SQL Server or Supabase)
- **reporte_nomina_SQL_SERVER.pyw** — direct SQL Server queries
- **reporte_nomina_SUPABASE.pyw** — direct Supabase queries
- **reporte_nomina_COMPARADOR_SUPABASE_vs_SQL.pyw** — data sync validation

## Development Workflow

### Running / Testing

All `.pyw` files run directly with `python3 <filename>.pyw`. No build step needed for development.

### Common Tasks

**Start development environment:**
```bash
cd /home/alcano/Documentos/mis_proyecto/NOMINA_ROLES_SISTEMA_INSEVIG
python3 SISTEMA_GESTION_EMPLEADOS_10.pyw
```

**Build Windows EXE (via GitHub Actions):**
- Push to GitHub master/main branch
- Workflow at `.github/workflows/build_windows.yml` triggers automatically
- Monitor: `gh run list --limit 5`
- Download: `gh run download <run_id> --dir dist_new/`

**Deploy EXE to Roberto-PC:**
1. Wait for build to complete
2. Download artifact from GitHub Actions
3. Close EXE on all Windows machines
4. `cp dist_new/<build>/<Name>.exe /mnt/roberto-pc/ARCHIVOS\ ASISTENTE\ AOC/1.TURNOS/`
5. If file locked: copy as `_NUEVO.exe` and rename from Windows Explorer

**Test SQL Server connection:**
```python
from sync_sqlserver import get_sql_conn, probar_conexion
probar_conexion()  # True/False
```

**Test Supabase connection:**
```python
from supabase_client import get_supabase_client
client = get_supabase_client()
client.table('rpemplea').select().limit(1).execute()
```

## Code Conventions

### Paths (PyInstaller Handling)

Never use `__file__` or relative paths directly. Always use `_paths.py`:

```python
from _paths import bundle_dir, app_dir
import os

# Read-only bundled files (templates, openssl_legacy.cnf, etc.)
ruta_template = os.path.join(bundle_dir(), 'template.html')

# Writable files (db, logs, config.json, generated docs)
ruta_db = os.path.join(app_dir(), 'modulo.db')
```

- `bundle_dir()` → `sys._MEIPASS` in frozen EXE, script directory in dev
- `app_dir()` → EXE directory in frozen, script directory in dev

### SQL Queries

**Always use parameters — never concatenate strings:**

```python
conn = get_sql_conn()
try:
    c = conn.cursor()
    c.execute("UPDATE tabla SET campo=? WHERE id=?", (valor, id))
    conn.commit()
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
```

### Supabase Client

Use the singleton thread-safe client from `supabase_client.py`:

```python
from supabase_client import get_supabase_client

client = get_supabase_client()

# INSERT
client.table('tabla').insert({'col': val}).execute()

# UPDATE
client.table('tabla').update({'col': val}).eq('id', id).execute()

# DELETE
client.table('tabla').delete().eq('id', id).execute()

# SELECT with filtering
data = client.table('rpemplea').select('*').ilike('nombres', '%query%').execute()
```

**Quirks to handle:**
- `rpemplea.cedula` arrives as float (920116811.0) → normalize: `str(int(cedula)).zfill(10)`
- `rpemplea.empleado` is string ('1035') → use directly for filtering
- No `.or_()` operator → chain separate `.ilike()` queries and merge in Python
- Select only common columns for historical queries: `empleado, clase, valor, fecha_ven`

### SQLite CRUD

Use context manager for automatic commit:

```python
from db import get_connection

with get_connection() as conn:
    conn.execute("INSERT INTO tabla (...) VALUES (?,?,?)", (v1, v2, v3))
    # Auto-commits on exit
```

For reads without writes:
```python
with get_connection() as conn:
    rows = conn.execute("SELECT * FROM tabla WHERE id=?", (id,)).fetchall()
```

### Tkinter Threading

Never touch widgets from secondary threads. Use `self.after()` to queue UI updates:

```python
def _do_long_op():
    result = expensive_operation()
    root.after(0, lambda: update_widget(result))

thread = threading.Thread(target=_do_long_op, daemon=True)
thread.start()
```

### PDF Operations

**Previewview (doesn't lock file):**
```python
import webbrowser
from pathlib import Path
webbrowser.open(Path(ruta_pdf).as_uri())
```

**Save a copy (safe for concurrent Adobe readers):**
```python
import shutil
shutil.copy2(src, dst)  # Never use shutil.move() if Adobe might have it open
```

### Logging

Use the rotating logger from `log_setup.py`:

```python
import logging
from log_setup import setup_logging

LOG = setup_logging('myapp', 'myapp.log')
LOG.info("Message")
LOG.error("Error", exc_info=True)
```

Rotates at 5 MB with 5 backups kept.

### UI Color Palette (Dark Mode)

Defined in main app files:
```python
COL_BG       = '#1E1E1E'      # Main background
COL_HEADER   = '#0D1B2A'      # Header/section bg
COL_ACCENT   = '#4A9EFF'      # Highlight blue
COL_PEND     = '#FF9F43'      # Orange for pending
COL_OK       = '#2ED573'      # Green for success
COL_DANGER   = '#FF6B6B'      # Red for error
COL_WHITE    = '#FFFFFF'      # White text
COL_GRAY     = '#A0A0A0'      # Gray text
COL_ENTRY_BG = '#2D2D2D'      # Input field bg
COL_CARD     = '#2D2D2D'      # Card bg
COL_TEXT     = '#E0E0E0'      # Standard text
COL_BORDER   = '#404040'      # Border

FONT_DEFAULT = ('Segoe UI', 10)
FONT_SMALL   = ('Segoe UI', 9)
FONT_LABEL   = ('Segoe UI', 10, 'bold')
FONT_HEAD    = ('Segoe UI', 11, 'bold')
FONT_TITLE   = ('Segoe UI', 14, 'bold')
```

## Infrastructure & Deployment

See `INFRAESTRUCTURA_RRHH.txt` for comprehensive details on:
- Network topology and SMB mounts
- SQL Server credentials and table schemas
- Supabase project configuration and table prefixes
- PyInstaller bundling (.spec files)
- GitHub Actions CI/CD workflow
- Deployment to production on Roberto-PC
- Module naming conventions for future expansion

## Module Reusable Templates

The following files can be copied to new RRHH modules with minimal changes:

| File | Purpose | How to Adapt |
|------|---------|-------------|
| `_paths.py` | Path resolution (bundle vs. dev) | Copy as-is |
| `log_setup.py` | Rotating log handler | Copy as-is; change log filename |
| `openssl_legacy.cnf` | TLS 1.0 for SQL Server 2008 R2 | Copy as-is to all projects |
| `sync_sqlserver.py` | SQL Server connection + fallback drivers | Keep get_sql_conn(); add module-specific queries |
| `supabase_client.py` | Singleton Supabase client (thread-safe) | Adjust table names and functions |
| `app_config.py` | Load/save config.json next to EXE | Change _DEFAULTS for new module |
| `db.py` | SQLite schema + connection | Adapt _DB_RED_WIN/_DB_RED_LINUX paths; rewrite schema |
| `model.py` | CRUD template | Rewrite with module entities |
| `auditoria.py` | Audit logging to Supabase + SQLite | Change audit table name/prefix |

## External Documentation

- **GitHub**: Username Alcano3520, email daniel3520@gmail.com, use `gh` CLI for auth/deployments
- **Authentication**: `gh auth login` (browser-based) or `gh auth refresh -s workflow` if workflow permissions needed
- **Credentials**: SQL Server, Supabase key in `config/supabase.yaml` (must be .gitignore'd — never commit)
