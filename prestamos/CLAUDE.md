# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
pip install -r requirements.txt
python HISTORIAL_PRESTAMOS_10.pyw
```

The `requirements.txt` file contains all necessary dependencies. `HISTORIAL_PRESTAMOS_9.pyw` is the previous version kept for reference; `_10.pyw` is the active file.

## Architecture

Single-class Tkinter app (`ConsultorPrestamos`, ~1913 lines) with two read-only data sources:

- **SQL Server 2008 R2** (`192.168.2.115` / database `insevig`) — tables `RPINGDES` (current payroll, CLASE=205 = loan balance), `RPHISTOR` (closed historical payroll), `RPEMPLEA` (employee master). Always filter `WHERE CODEMP='10' AND CODSUC='10'`.
- **SQLite** (`\\server\Respaldo 2017\Base\Saldo_prestamos_driver.db`) — table `historial_prestamos`, stores older loan records not in SQL Server.

Neither database is written to by this module.

### Data flow for a loan search

`buscar_prestamos()` → `obtener_movimientos_completos()` merges two sources:
1. `obtener_movimientos_sistema_filtrados()` → queries RPINGDES (filtered by employee and excluded loan numbers)
2. `obtener_historial_sqlite()` → queries SQLite `historial_prestamos`

Result is displayed in a `ttk.Treeview`. Rows marked `ES_CUADRE=True` are synthetic balance-adjustment entries.

### SQLite path resolution (`_resolver_ruta_sqlite`)

Three-step fallback:
1. Windows: UNC path `\\server\Respaldo 2017\Base\Saldo_prestamos_driver.db` directly
2. Linux: `/mnt/server/Base/Saldo_prestamos_driver.db` (mount `//192.168.2.115/Respaldo 2017`)
3. Linux fallback: `smbclient` download to `/tmp/Saldo_prestamos_driver_cache.db` (1-hour TTL)

## Critical quirks

- **TLS 1.0 workaround**: SQL Server 2008 R2 requires TLS 1.0. `openssl_legacy.cnf` is loaded via `OPENSSL_CONF` before `import pyodbc` (first two lines of the file). This file must be alongside the script or bundled in the PyInstaller EXE.
- **No threading**: All SQL Server and SQLite queries block the main thread. The UI freezes during queries — this is intentional/known.
- **ODBC driver**: Hardcoded to `ODBC Driver 17 for SQL Server`. Install it on Linux: `msodbcsql17`.
- **CEDULA formatting**: Arrives from SQL as a float (e.g. `920116811.0`). Always convert with `formatear_cedula()` → zero-padded 10-digit string.
- **Credentials hardcoded**: `sa / puntosoft123*`. Do not commit to public repos.
- **Locale**: `es_ES.UTF-8` for currency display; silently ignored if unavailable.

## Key methods

| Method | Purpose |
|---|---|
| `buscar_prestamos()` | Main search — reads both DBs, populates treeview |
| `obtener_movimientos_completos()` | Merges SQL Server + SQLite loan records |
| `buscar_empleados_por_nombre()` | Searches RPEMPLEA by apellidos/nombres |
| `exportar_excel()` | Exports current employee loan history to .xlsx |
| `exportar_saldos_prestamos_excel()` | Exports CLASE=205 balances for all employees |
| `cargar_panel_saldos()` / `mostrar_panel_saldos()` | Left sidebar with employee list + balances |
| `aplicar_filtros()` | Real-time filter on displayed rows |
| `setup_gui()` | Builds entire UI (called from `__init__`) |

## UI keyboard shortcuts

- `F5` / `Ctrl+F` → open name search dialog
- `Enter` (on employee code field) → run loan search
- `Double-click` on treeview row → detail popup window

## Reference documentation

Two large text files in the repo apply to all RRHH modules:

- **`INFRAESTRUCTURA_RRHH.txt`** — SQL Server creds, TLS workaround, SMB mounts, Supabase config, PyInstaller packaging, network paths
- **`INTERFAZ_GRAFICA_RRHH.txt`** — Tkinter UI patterns: threading model, layout conventions, styles, lazy refresh, icon setup

## Deployment

PyInstaller EXE for Windows, placed at `\\roberto-pc\rrhh2021\ARCHIVOS ASISTENTE AOC\1.TURNOS\`. The `openssl_legacy.cnf` file must be included in the PyInstaller `.spec` `datas` section.

Linux SMB mount for the SQLite database (add to `/etc/fstab`):
```
//192.168.2.115/Respaldo\ 2017 /mnt/server cifs username=guest,password=,vers=2.0,noperm,_netdev,x-systemd.automount 0 0
```
