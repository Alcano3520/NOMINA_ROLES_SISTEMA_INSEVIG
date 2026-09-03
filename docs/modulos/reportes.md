# Módulo: reportes

Primer módulo real (Fase 1). Sirve de prueba del stack: solo lectura, salida =
Excel descargable, ambas fuentes, un Job largo.

## Qué hace (para el usuario)
- Reporte **consolidado de nómina** de un período (`YYYY-MM`): una fila por empleado,
  columnas por concepto + `TOTAL_INGRESOS/EGRESOS/RECIBIR`, `SUELDO_BASE`.
- Alcance: **Nómina actual** (`RPINGDES` / `rpingdesres`) o **Histórico**
  (`RPHISTOR` ~2.5M filas / `rphistor_temp`).
- **Comparador** SQL Server vs Supabase: reconstruye el mismo reporte desde ambas
  fuentes y lista diferencias (conteo de filas, columnas, sumas de totales > $1).

## Origen (código legado a portar)
| Legado | Se reutiliza | Se reescribe |
|---|---|---|
| `reportes/reporte_nomina_GUI.pyw` | `leer_movimientos_sql/_supabase`, `procesar`, `exportar_excel`, `MAPEO_CONCEPTOS`→`core.concepts` | `class App(tk.Tk)`, `filedialog.askdirectory`, radios |
| `reportes/reporte_nomina_SQL_SERVER.pyw` / `_SUPABASE.pyw` | motores de consulta + paginación cursor | — |
| `reportes/reporte_nomina_COMPARADOR_SUPABASE_vs_SQL.pyw` | `comparar_dataframes()` | `input()` CLI → Job |

## Rebanada
- `core/repos/nomina.py` — `leer_movimientos(periodo, historico, fuente)` **generador**
  cursor-based; `consolidar(movs, catalogo)`; `comparar(sql_df, sup_df)`.
- `core/excel/nomina_builders.py` — `consolidado_xlsx(filas) -> bytes`
  (`xlsxwriter`, `constant_memory=True`); `comparador_xlsx(dif) -> bytes`.
- `insevig_web/states/reportes_state.py`
- `insevig_web/pages/reportes/consolidado.py`, `insevig_web/pages/reportes/comparador.py`
- `tests/unit/test_reportes_*.py`, `tests/integration/test_reportes_*.py`

## Contratos que consume
`core.concepts`, `core.db.sqlserver` / `core.db.supabase_client`, `core.db.appdb`
(Job), `core.jobs`, `core.storage`, `insevig_web.components.layout.pagina`,
`components/ui/*`, `DataSourceState`, `AuthState`.

## Rutas y permisos
| Ruta | Acción |
|---|---|
| `/reportes/consolidado` | `reportes:ver` (generar) · `reportes:exportar` (descargar) |
| `/reportes/comparador` | `reportes:exportar` |

## Datos
- Solo lectura. Fuente por el selector (`DataSourceState.fuente_de("reportes")`).
- SQL Server: `RPINGDES`, `RPHISTOR`, `RPEMPLEA`, `DBTABLAS`. Supabase: idem en minúscula.

## Jobs
- Consolidado histórico (~2.5M) y comparador → `core.jobs` con progreso por lotes;
  resultado en `core.storage` + `rx.download`.

## Criterio de "hecho"
- [ ] Consolidado del período actual == salida legada (tolerancia de redondeo) para 1 período.
- [ ] Histórico RPHISTOR termina como Job con progreso y xlsx descargable.
- [ ] Comparador reproduce la lista de discrepancias del módulo legado.
- [ ] `pytest`, `ruff`, `mypy core` limpios; página en `test_arquitectura`.
- [ ] Revisado a 360 / 768 / 1280 px.
