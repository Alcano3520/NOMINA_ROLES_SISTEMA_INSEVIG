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

## ⚠️ Divergencia de modelo con el legado (hallada 2026-09-06, sin resolver)

La validación en el NAS (`scripts/validar_datos`, 10/25 empleados con saldo de
préstamos distinto entre SQL Server y Supabase, **siempre SQL > Supabase**)
destapó dos cosas:

1. **[corregido, commit siguiente]** `_NUMEROS_MIGRADOS` no se excluía en la
   ruta SQL Server: `NUMERO` es float en las tablas → `str()` daba `'35923.0'`
   → nunca casaba el frozenset (que tiene `'35923'`). El legado lo hace en SQL
   (`NUMERO NOT IN (...)`, conversión implícita). Fix: `_num_norm()`.

2. **[SIN resolver — necesita rework deliberado]** el modelo de préstamo de
   `core/repos/prestamos` NO coincide con el `.pyw`:
   - Legado: los movimientos de **RPHISTOR** CLASE 205 son **egresos (pagos)**;
     el **saldo de un préstamo = suma de `RPINGDES.VALOR` de ese `NUMERO`**
     (`obtener_datos_rpingdes_combinados` → `saldos_por_numero`). El "ingreso"
     (monto prestado) es **sintético**: `total_pagado (RPHISTOR) + saldo_pendiente
     (RPINGDES)`.
   - `core/`: `historial_empleado` mete RPINGDES + RPHISTOR como movimientos con
     `valor` positivo, y `agrupar_por_numero` los cuenta todos como "prestado".
     `saldo_total` suma todo → número sin sentido.
   - `prestamos.saldos()` (masivo, `SUM(RPINGDES.VALOR)`) **sí** coincide con el
     legado; el problema es la vista por empleado (`historial_empleado`,
     `agrupar_por_numero`, `saldo_total`, `_historial_supabase`, y la página
     `/prestamos/historial`).
   - Rehacer `core/repos/prestamos` para el modelo del legado: RPHISTOR/SQLite =
     egresos; RPINGDES = saldo pendiente por número; ingreso sintético. Tocar
     también `core/excel/prestamos_builders.historial_xlsx` y el state/página.

## Pendiente
- **Rework del modelo de préstamo (punto 2 de arriba).**
- Dedupe RPINGDES vs RPHISTOR cuando el mismo `NUMERO` aparece en ambas (visto
  en el empleado 9091: NUMERO 46141 en RPINGDES 24/06 y RPHISTOR 30/06).
- Ejecutar la migración del histórico en el NAS con el `.db` real.
- Validar contra el `.pyw` para una muestra tras el rework.
