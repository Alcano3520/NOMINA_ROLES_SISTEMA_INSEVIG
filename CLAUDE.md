# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Integrated HR/Payroll desktop system for INSEVIG (Ecuador). A Tkinter login+dashboard (`Sistema_INSEVIG.pyw`) launches independent GUI modules, each of which can also run standalone. There is no build step for development — every `.pyw`/`.py` file runs directly with `python3`.

Three data sources, used across almost every module:

1. **SQL Server 2008 R2** (`192.168.2.115`, database `insevig`) — source of truth. Tables `RPEMPLEA` (employees), `RPHISTOR` (closed historical payroll, ~2.5M rows), `RPINGDES` (current open-period payroll). **Always filter `WHERE CODEMP='10' AND CODSUC='10'`** — the server hosts multiple companies. Read-only by policy.
2. **Supabase** (project `buzcapcwmksasrtjofae`) — cloud mirror of the SQL Server tables plus module-specific tables (prefixes like `vac_*`, `tur_*`, `per_*`). Every write must also log to that module's `<prefix>_auditoria` table. Credentials in `config/supabase.yaml` (gitignored, never commit). Note: `config/supabase_credentials.txt` and a few `TABLA_SUPABASE_*` docs with the same secrets are currently tracked in git — do not add new credential files, and flag this to the user if it comes up.
3. **SQLite** — per-module local DB, normally on a network share (see Networking below), used for data that predates or falls outside the SQL Server system (e.g. old loan records).

Nearly every module offers a **selector between SQL Server and Supabase** as data source, with automatic fallback detection (`shared/detect_db.py`) when SQL Server is unreachable (e.g. missing ODBC driver on Linux — see `INSTALACION_LINUX.md`).

## Repository Structure

This is a monorepo of independent module folders, each launched from `Sistema_INSEVIG.pyw`'s sidebar. Two folders (`HISTORIAL PRESTAMOS/`, `TOTAL_OSERVACIONES/`) are **their own nested git repositories** (each has its own `.git`), vendored into this repo's working tree but not tracked as submodules — be careful running repo-wide git commands, and treat those directories' own CLAUDE.md/AGENTS.md (and `GEMINI.md`) as authoritative for their code.

There is also a stray tracked directory literally named `HISTORIAL\ PRESTAMOS/` (backslash-space in the name), containing only an outdated `CLAUDE.md`. It is cruft — ignore it; the real module is `HISTORIAL PRESTAMOS/`.

Every module directory has its own `CLAUDE.md` with module-specific details — read it before working inside that folder. Quick map:

| Directory | Entry point | Launched via |
|---|---|---|
| `roles/` | `Roles_Principal.pyw` | in-process (`importlib.machinery.SourceFileLoader`, class `RolesPrincipal`), embedded as `Toplevel` |
| `empleados/` | `SISTEMA_GESTION_EMPLEADOS_10.pyw` | in-process (same loader pattern), class `SistemaGestionEmpleados10`, embedded as `Toplevel` |
| `prestamos/` | `HISTORIAL_PRESTAMOS_10.pyw` | separate process (`subprocess.Popen`) |
| `observaciones/` | `TOTAL_OSERVACIONES_4_0.pyw` | separate process (`subprocess.Popen`) — see `TOTAL_OSERVACIONES/` (nested repo) for newer variants |
| `reportes/` | `reporte_nomina_GUI.pyw` (unifies SQL Server/Supabase/comparador variants) | separate process (`subprocess.Popen`) |
| `registrdor_vizulizador_egresosingresos/` | `REGISTRAR_PRESTAMOS_UNIFICADO.pyw` | separate process (`subprocess.Popen`), incomplete/experimental |
| `envio_roles/` | `ENVIO_ROLES_7.1.py` | standalone, not wired into the dashboard — duplicates part of `roles/`; see `PLAN_INTEGRACION.md` for the pending merge/discard decision |
| `shared/` | — | library code imported by other modules (see below), not a launchable app |
| `SACAR_SEC/` | `SACAR_TABLAS_SEC.pyw` | standalone utility, untracked/new |

The two launch patterns matter: `roles/` and `empleados/` are loaded in-process into a `Toplevel` window (share the dashboard's Python interpreter and `sys.path`), while the rest are spawned as separate `python <script>` processes via `subprocess.Popen`. When editing `roles/` or `empleados/`, a module-load error surfaces as a `messagebox.showerror` from `Sistema_INSEVIG.pyw`, not a traceback in the terminal.

`PLAN_INTEGRACION.md` describes the original integration roadmap — most of it is now done (all modules above are wired into the sidebar in `Sistema_INSEVIG.pyw`); treat it as historical context on *why* the structure looks this way, not as a current TODO list.

## Shared Code (`shared/`)

`shared/obtener_datos.py` (class `ObtenerDatos`) is the critical, most-reused piece of code — nearly every module depends on it for querying and consolidating payroll data:

- `obtener_datos_empleado_rapido(periodo, cedula_o_nombre)` — fast lookup from SQL Server, returns a `pandas.Series`.
- `obtener_datos_empleado_supabase(periodo, cedula_o_nombre)` — equivalent lookup from Supabase (searches by employee code → nombres → apellidos → cédula), returns a `pandas.Series` with the same shape as the SQL Server version.

Do not change the payroll concept mapping (`CLASE` code → name) in this file without checking every module that consumes it — it's explicitly marked "NO CAMBIAR" in `shared/CLAUDE.md`. Key codes: `100=SUELDO`, `102=BONIFICACION`, `104=FONDO_RESERVA`, `107=DECIMO_TERCERA`, `108=DECIMO_CUARTA`, `200=APORT_IESS`, `202=ANTICIPO_SUELDO`, `203=MULTAS`, `205=PRESTAMOS_COMPANIA`.

`shared/detect_db.py` provides `obtener_fuente_recomendada()` — tries SQL Server first (across the driver fallback list), then Supabase, used by the dashboard to auto-select a data source when opening.

Reusable per-module templates referenced by several module CLAUDE.md files (`_paths.py`, `log_setup.py`, `sync_sqlserver.py`, `supabase_client.py`, `app_config.py`, `db.py`, `model.py`, `auditoria.py`) live inside individual module folders (e.g. `HISTORIAL PRESTAMOS/`), not in `shared/` itself — check the target module before assuming a name is present at the repo root.

## Running Modules

```bash
cd /home/alcano/Documentos/mis_proyecto/NOMINA_ROLES_SISTEMA_INSEVIG

# Full dashboard (login: admin/admin)
python3 Sistema_INSEVIG.pyw

# Individual module, standalone
python3 roles/Roles_Principal.pyw
python3 empleados/SISTEMA_GESTION_EMPLEADOS_10.pyw
python3 "prestamos/HISTORIAL_PRESTAMOS_10.pyw"
python3 reportes/reporte_nomina_GUI.pyw
```

There is no repo-wide `requirements.txt`; dependencies are typically `tkinter`, `pandas`, `pyodbc`, `supabase`, `reportlab`, `PyMuPDF` (`fitz`), `openpyxl`. Some nested module repos (e.g. `HISTORIAL PRESTAMOS/`) ship their own `requirements.txt` — use that when working inside them.

### Checking changes

There is no test suite and no linter config. The de-facto smoke check after editing a module is a syntax compile plus a short timed launch:

```bash
python3 -m py_compile empleados/SISTEMA_GESTION_EMPLEADOS_10.pyw   # syntax only
timeout 10 python3 empleados/SISTEMA_GESTION_EMPLEADOS_10.pyw       # launches the GUI; times out cleanly if it opened OK
```

### SQL Server on Linux

Requires `msodbcsql17`/`msodbcsql18` (see `INSTALACION_LINUX.md` for install steps per distro). SQL Server 2008 R2 requires TLS 1.0 — `config/openssl_legacy.cnf` must be loaded via `OPENSSL_CONF` env var **before** `import pyodbc`. If the ODBC driver isn't installed, switch the module's data-source selector to Supabase instead of trying to fix connectivity.

### ODBC driver fallback order

`ODBC Driver 17` → `18` → `13` → `11` → native `SQL Server` driver. Implemented per-module (e.g. `get_sql_conn()` in each module's `sync_sqlserver.py`); throws a descriptive error if none connect.

## Conventions That Apply Repo-Wide

- **Cédula normalization**: SQL Server/Supabase return `cedula` as a float (e.g. `920116811.0`). Always normalize with `str(int(cedula)).zfill(10)` before display or comparison.
- **SQL queries**: always parameterized (`c.execute("... WHERE id=?", (id,))`), never string-concatenated.
- **Tkinter threading**: long operations (DB queries, PDF generation) run in a `threading.Thread`; UI updates from that thread must go through `root.after(0, ...)` — never touch widgets directly from a background thread.
- **PDF handling**: preview via `webbrowser.open(Path(pdf).as_uri())` (doesn't lock the file); copy with `shutil.copy2`, never `shutil.move`, since a PDF viewer may have the file open.
- **Dark-mode palette** used by `empleados/` and other newer modules: `COL_BG #1E1E1E`, `COL_HEADER #0D1B2A`, `COL_ACCENT #4A9EFF`, `COL_OK #2ED573`, `COL_DANGER #FF6B6B`, font family `Segoe UI`. The dashboard/login (`Sistema_INSEVIG.pyw`) instead uses a light corporate palette (`COLOR_PRIMARY #1a4d8f`, `COLOR_SECONDARY #ffd700`) — don't assume one palette applies everywhere.

## Networking (relevant when a module can't reach its data)

- **Roberto-PC** (`192.168.2.80`) — primary file server; SMB mount at `/mnt/roberto-pc` (guest access); EXE deployment target and shared SQLite location for several modules.
- **Denisse-PC** (`192.168.2.118`) — accounting/finance share, SMB mount at `/mnt/denisse-pc`.
- **SQL Server** (`192.168.2.115`) — see TLS note above.

`docs/INFRAESTRUCTURA_RRHH.txt` has the full inventory (credentials, SMB paths, table schemas, PyInstaller/CI details) — check it before assuming a path or credential from a module's CLAUDE.md is still current, since infra details occasionally drift between module docs.

## Windows Deployment

Modules are packaged to Windows `.exe` via PyInstaller (`.spec` files inside each module folder) and, for at least the `HISTORIAL PRESTAMOS/` nested repo, built via a GitHub Actions workflow (`HISTORIAL PRESTAMOS/.github/workflows/build_windows.yml`) — there is no such workflow at the top-level repo. Deployed EXEs are copied to `\\roberto-pc\...\1.TURNOS\` (or the module's documented equivalent); if the EXE is locked by a running instance on Windows, copy as `_NUEVO.exe` and rename from Explorer rather than overwriting directly.
