# Módulo: registrador (Registrar egresos/ingresos)

Estado: **puerto completo de REGISTRAR_PRESTAMOS_UNIFICADO.pyw** (6 pestañas).

## Pestañas (`/registrador`)
0. **Movimientos vigentes del empleado** — al elegir empleado (en Préstamo y en
   Egresos/Ingresos) se muestra su historial de registros no asentados (mismo panel
   "Historial de Registros" del legado; `historial_movimientos(..., empleado=...)`).
1. **Préstamo individual** — CLASE 205. Elige empleado, valor total, y planifica por
   nº de cuotas (`cuotas_tradicional`) o por cuota mensual fija respetando lo ya
   programado (`cuotas_por_valor` + `proyeccion_pagos_futuros`). Al elegir el empleado
   se muestra el **panel "carga programada"** (deducciones ya agendadas por mes). La
   **vista previa de cuotas es editable** (valor y fecha por fila, con total en vivo).
   **Tipo de transacción** (combo, se antepone a la observación, `TIPOS_TRANSACCION`).
   "Registrar préstamo" pide **confirmación** (`rx.alert_dialog`) con el resumen
   (empleado, cuotas, total) antes de escribir. "Exportar" descarga las cuotas
   calculadas en CSV; "Limpiar" resetea el formulario.
2. **Carga masiva de préstamos** — **grilla editable** (como el grid del legado):
   se pega desde Excel en el cuadro superior (acepta TSV / `;` / `|` / `,`) o se
   **carga un archivo .xlsx/.csv directo** (`pm_subir_archivo`, como "Cargar Archivo"
   del legado), "Validar" resuelve el nombre por código/cédula y marca ✓ las filas
   listas (con **resumen del lote**: filas/listas/total/promedio), "Registrar todo"
   pide confirmación y corre el Job (CSV de resultados). Modo nº-de-cuotas o
   cuota-mensual (`cuotas_tradicional` / `cuotas_por_valor`).
3. **Egresos / Ingresos** — registrar un movimiento de cualquier tipo de
   `CLASES_SIMPLIFICADAS` (multas 203, anticipos 202/217, pensión 206, hipotecario 207,
   IESS cónyuge 218, renta 219, surtidos 250, bonificación 102, maniobras 110,
   reembolsos 111, movilización 120) — `registrar_movimiento`, con confirmación antes
   de escribir y "Limpiar". Incluye la misma **grilla editable + pegar de Excel o
   cargar archivo** (`_bulk_egr_ing`, columnas código/clase/valor/fecha/observación)
   con Validar + resumen + confirmación + Job + CSV.
4. (unificada con la 3 en la web)
5. **BIESS quirografarios / hipotecarios** — CLASE 204 o 207, autodetección de
   fila/columnas con override manual editable + "Ver Excel" (diagnóstico) +
   "Releer" (`biess_autodetectar` / `parse_biess_manual`). Empareja por cédula en
   lote, marca activo/liquidado/no encontrado (solo activos se registran).
   `postear_biess`: INSERT completo (21 columnas) con el MISMO número de egreso
   para todo el lote (modo agrupado, igual que `_biess_subir`), RPCONTRL
   actualizado una vez. Observación autogenerada, editable. Confirmación antes de
   registrar. Exporta CSV.
6. **Consulta / edición** — dos vistas:
   - *Agrupada por NUMERO* (`historial_movimientos`): ver cuotas de un préstamo
     (`cuotas_prestamo`), borrar un movimiento no asentado (`eliminar_movimiento`),
     mover cuotas pendientes (`mover_cuotas_pendientes`).
   - *Detallada fila por fila* (`consultar_filas`): filtros por empleado / clase /
     rango de FECHA_VEN / nº / solo no procesados; **editar el VALOR** de una fila no
     asentada (`editar_valor_fila`), **eliminar una fila** (`eliminar_fila`),
     **exportar a CSV**.

## Datos
Lectura: SQL Server o Supabase (rpingdesres). Escritura: SOLO SQL Server, con
`audit_scope` + vista previa (`dry_run`). Números desde RPCONTRL (no transaccional,
igual que el legado — riesgo de colisión con instancias concurrentes: aceptable v1).

## Pendiente
- Egresos/Ingresos masivo: modo "agrupado" del legado (un solo número de egreso
  para todo el lote, con observación común) — hoy cada fila puede tener su propia
  clase y siempre se numera individualmente; funcionalmente cubre el caso de uso
  pero no replica ese modo exacto. BIESS sí implementa el agrupado.
- Respaldo por operación (`modulo_seguridad_prestamos` del legado — no existía nunca;
  su reemplazo real es `core.audit`).
