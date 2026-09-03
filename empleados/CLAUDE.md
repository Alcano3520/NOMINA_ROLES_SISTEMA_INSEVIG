# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Módulo: GESTIÓN DE EMPLEADOS

Two **independent, standalone** Tkinter apps that do not import or launch each other — each has its own hardcoded DB credentials and its own `if __name__ == "__main__"` entry point:

| File | Purpose | Data source(s) |
|---|---|---|
| `SISTEMA_GESTION_EMPLEADOS_10.pyw` (class `SistemaGestionEmpleados10`, ~2900 lines) | CRUD editor for employees | SQL Server only — no Supabase code at all in this file |
| `historial_empleado_GUI.pyw` (class `App`) | Read-mostly payroll-history viewer | SQL Server **or** Supabase, selectable at runtime via a header combobox (default `'Supabase'`) |

When `Sistema_INSEVIG.pyw` embeds this module (per the top-level CLAUDE.md), it's `SISTEMA_GESTION_EMPLEADOS_10.pyw`'s `SistemaGestionEmpleados10` that gets loaded in-process as a `Toplevel`; `historial_empleado_GUI.pyw` is a separate, secondary tool for viewing one employee's history.

Neither file imports from the repo-level `shared/` directory — both duplicate their own SQL connection helpers (`_get_sql_conn` / `_sql_conn_str`) rather than reusing `shared/obtener_datos.py` or `shared/detect_db.py`.

## Running

```bash
python3 SISTEMA_GESTION_EMPLEADOS_10.pyw   # no args; always connects to hardcoded SQL Server
python3 historial_empleado_GUI.pyw         # no args; data source picked at runtime in the UI
```

## `SISTEMA_GESTION_EMPLEADOS_10.pyw` — SQL Server only

- `SistemaGestionEmpleados10.__init__(self, root)` — **no `fuente` parameter.** Always connects to the SQL Server instance hardcoded in `SQL_CFG` (line ~61).
- `SQL_FILTER = "CODEMP='10' AND CODSUC='10'"` — appended to almost every query/write; this is the tenant filter from the top-level CLAUDE.md.
- `_conectar_bd()` → threaded call to `_get_sql_conn()`, which tries ODBC drivers in order 17 → 18 → 13 → 11 → native `SQL Server` driver.
- `_cargar_catalogos()` loads 8 catalog types from SQL Server table `DBTABLAS` (`WHERE TIPO = ?`): `CAR`=cargos, `SEC`=secciones, `DPT`=departamentos, `SEX`=sexos, `ECS`=estados civiles, `TTR`=tipos de trabajo, `FPA`=formas de pago, `BCO`=bancos. There is **no** `_cargar_catalogos_supabase()` in this file (that belongs to `historial_empleado_GUI.pyw`).
- `_cargar_lista()` loads the employee grid, called from `_conectar_bd`, the "Actualizar" button, and catalog/sección filter changes.
- CRUD, all via raw `pyodbc` against `RPEMPLEA`/`RPEMPOBSERV`:
  - `_guardar_cambios()` → `UPDATE RPEMPLEA ... WHERE EMPLEADO=? AND {SQL_FILTER}` for existing employees, `INSERT INTO RPEMPLEA (...)` for new ones.
  - `_eliminar_empleado()` → triple-confirmation UX (2× `askyesno` + retype-the-employee-code `simpledialog.askstring`) before `DELETE FROM RPEMPLEA WHERE EMPLEADO=? AND {SQL_FILTER}`.
  - `_guardar_obs()` → writes to `RPEMPOBSERV`.
  - No dedicated audit-log table: "auditoría" here just means read/display of `RPEMPLEA`'s own `creado_por`/`fecha_crea`/`mod_por`/`fecha_mod` columns via `_actualizar_label_auditoria()`.
- Bulk operations via Excel template (`EdicionMasivaFrame`, `ObservacionesMasivasFrame`, plus a third similar block): generate a `PLANTILLA_EMPLEADOS_*.xlsx` / `PLANTILLA_OBSERVACIONES_*.xlsx` with `openpyxl`, let the user edit it externally, then re-import with `openpyxl.load_workbook` and apply row-by-row `UPDATE RPEMPLEA SET {sets} WHERE EMPLEADO=? AND {SQL_FILTER}`. `openpyxl` is imported lazily inside these functions (not at module load), with a `messagebox.showerror(...)` fallback telling the user to `pip install openpyxl` if missing — treat it as an optional dependency.
- Dark mode palette (`_configurar_estilo()`, set up in `__init__`): `COL_BG #1E1E1E`, `COL_HEADER #0D1B2A`, `COL_ACCENT #4A9EFF`, `COL_PEND #FF9F43`, `COL_OK #2ED573`, `COL_DANGER #FF6B6B`, `COL_WHITE #FFFFFF`, `COL_GRAY #A0A0A0`, `COL_ENTRY_BG #2D2D2D`, `COL_CARD #2D2D2D`, `COL_TEXT #E0E0E0`, `COL_BORDER #404040`; font family `Segoe UI` at several weights (`FONT_DEFAULT`, `FONT_SMALL`, `FONT_LABEL`, `FONT_HEAD`, `FONT_TITLE`).
- No cédula `.zfill(10)` normalization present in this file — don't assume it's applied here even though it's a repo-wide convention elsewhere.

## `historial_empleado_GUI.pyw` — dual source (SQL Server / Supabase)

- `App.__init__(self)` sets `self._fuente = tk.StringVar(value='Supabase')`, driven by a header `ttk.Combobox` with values `['Supabase', 'SQL Server']`. This is the *only* file in this module where a real "fuente" selector exists.
- `DetalleWindow.__init__(self, parent, emp_sel, periodo, es_actual, fuente, df_catalogo)` — per-employee detail popup, receives the selected source explicitly.
- Supabase access is read-only (`.select(...)` via `supabase-py`, e.g. `.table('rpemplea')`, `.table('dbtablas').eq('codemp','10')`) — lowercase table names, distinct from this file's own SQL Server path which uses uppercase `RPEMPLEA`/`DBTABLAS`.
- Catalog lookups here use a `'FNC'` type code for Cargo in some places — inconsistent with `SISTEMA_GESTION_EMPLEADOS_10.pyw`'s `'CAR'`; don't assume catalog type codes are shared 1:1 between the two files.
- Uses a **light** color palette (`BG '#f0f2f5'`, `PANEL '#ffffff'`, `AZUL '#1a73e8'`, `GRIS '#5f6368'`) — not the dark-mode `COL_*` palette from the other file.
- Excel export here (`pd.ExcelWriter`/`to_excel`, opened afterward via `subprocess.call(['xdg-open'|'open'], ruta)`) is a plain data export, unrelated to the `PLANTILLA_*` bulk-edit-template feature in the other file.

## Security note

Both files have plaintext credentials hardcoded in source (not in `config/supabase.yaml` or any gitignored config, contrary to the top-level CLAUDE.md's general convention): `SISTEMA_GESTION_EMPLEADOS_10.pyw` hardcodes the SQL Server `sa` password in `SQL_CFG`; `historial_empleado_GUI.pyw` hardcodes both a SQL Server connection string and a Supabase **service_role** JWT (full admin access, bypasses RLS). Keep this in mind before this folder is published anywhere outside the current private repo.
