# Módulo: prestamos

Estado: **Consulta (solo lectura)**. Porta `prestamos/HISTORIAL_PRESTAMOS_10.pyw`
(3158 líneas). No escribe nada (los préstamos se registran desde el módulo
`registrador`).

## Origen legado
`prestamos/HISTORIAL_PRESTAMOS_10.pyw`

## Rebanada
`core/repos/prestamos.py` · `core/excel/prestamos_builders.py` ·
`insevig_web/states/prestamos_state.py` · `insevig_web/pages/prestamos/*.py` ·
`tests/unit/test_fase2.py` (parte de préstamos) · este documento.

## Fuentes de datos (CLASE 205)
Historial de un empleado = unión de tres orígenes, ordenada por fecha:
- **RPINGDES** (vivo) — SQL Server o Supabase `rpingdesres`.
- **RPHISTOR** (nómina cerrada, ~2.5M filas) — SQL Server o Supabase `rphistor_temp`.
  Se excluyen los `NUMERO` de `_NUMEROS_MIGRADOS` (ya estaban en el SQLite viejo).
- **`LoanHistoryMigrated`** (Postgres de la app) — lo que vivía en el SQLite sobre
  SMB, cargado una vez con `core.migrations_legacy.sqlite_to_appdb`. Cero SMB/SQLite
  en runtime.

Lectura SQL Server o Supabase según el selector; nunca escribe.

## Pantallas
- `/prestamos/historial` — buscar empleado → movimientos + saldo + "Resumen por
  préstamo" (agrupado por `NUMERO`: prestado/abonado/saldo, nº cuotas, cuota
  promedio, meses de brecha sin descuento, estimación de meses para cancelar,
  estado legible). "Ver" abre el detalle fila por fila de un préstamo.
  - **Filtros** (client-side, sobre lo ya cargado; paridad con `aplicar_filtros`
    del `.pyw`): tipo (ingreso/egreso), origen (RPINGDES/RPHISTOR/MIGRADO), N°
    (substring), concepto (substring), rango de fechas, monto min/max sobre el
    valor absoluto. Contador "Mostrando N de M (filtrado)". `core.repos.prestamos.
    filtrar_movimientos`.
  - **Exportar a Excel** (Job) — respeta los filtros activos.
    `core/excel/prestamos_builders.historial_xlsx` (hoja Historial + hoja Resumen,
    banner, bordes, fila TOTAL).
  - **Analizar con IA** (Job) — narrativa del comportamiento de pago
    (`core.narrativa`); "Leer en voz alta" usa la Web Speech API del navegador.
- `/prestamos/saldos` — Job que genera el Excel de saldos de todos los empleados
  con saldo ≠ 0 (`prestamos.saldos`).

## Contratos que consume
Ver `docs/CONTRATOS.md`. Reutiliza `core.db.*`, `core.jobs`, `core.storage`,
`core.narrativa`, `components/ui/*`, `AuthState`, `DataSourceState`. No edita el
núcleo congelado.

## Migración del histórico (una vez, en el NAS)
`python -m core.migrations_legacy.sqlite_to_appdb <ruta>\Saldo_prestamos_driver.db`
carga `historial_prestamos` en `LoanHistoryMigrated`. Es **idempotente**: correrlo
otra vez no duplica (salta las filas ya presentes por
empleado+fecha+numero_fila+ingreso+egreso); una fila nueva en el SQLite sí entra.
`--reemplazar` borra lo migrado antes de cargar.

## Pendiente
- Dedupe fino de la vista combinada validado contra datos reales (RPINGDES vs
  RPHISTOR para un préstamo que se cerró a mitad de período).
- Ejecutar la migración del histórico en el NAS con el `.db` real.
- Validar saldos e historial contra el `.pyw` para una muestra de empleados.
