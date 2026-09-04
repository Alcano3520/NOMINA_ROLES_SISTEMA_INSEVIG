# Módulo: registrador (Registrar egresos/ingresos)

Estado: **puerto completo de REGISTRAR_PRESTAMOS_UNIFICADO.pyw** (6 pestañas).

## Pestañas (`/registrador`)
1. **Préstamo individual** — CLASE 205. Elige empleado, valor total, y planifica por
   nº de cuotas (`cuotas_tradicional`) o por cuota mensual fija respetando lo ya
   programado (`cuotas_por_valor` + `proyeccion_pagos_futuros`). Al elegir el empleado
   se muestra el **panel "carga programada"** (deducciones ya agendadas por mes). La
   **vista previa de cuotas es editable** (valor y fecha por fila, con total en vivo)
   → registrar (una fila RPINGDES por cuota, nº desde RPCONTRL.ULT_EGR).
2. **Carga masiva de préstamos** — **grilla editable** (como el grid del legado):
   se pega desde Excel en el cuadro superior (acepta TSV / `;` / `|` / `,`), "Cargar
   en la tabla" vuelca a filas editables celda por celda, "Validar" resuelve el
   nombre por código/cédula y marca ✓ las filas listas, "Registrar todo" corre el
   Job (CSV de resultados). Modo nº-de-cuotas o cuota-mensual (`cuotas_tradicional`
   / `cuotas_por_valor`).
3. **Egresos / Ingresos** — registrar un movimiento de cualquier tipo de
   `CLASES_SIMPLIFICADAS` (multas 203, anticipos 202/217, pensión 206, hipotecario 207,
   IESS cónyuge 218, renta 219, surtidos 250, bonificación 102, maniobras 110,
   reembolsos 111, movilización 120) — `registrar_movimiento`. Incluye la misma
   **grilla editable + pegar de Excel** (`_bulk_egr_ing`, columnas código/clase/valor/
   fecha/observación) con Validar + Job + CSV.
4. (unificada con la 3 en la web)
5. **BIESS quirografarios** — Excel → CLASE 204, empareja por cédula, vista previa
   con dedupe, confirmar. `preparar_biess` / `postear`. (Falta: override manual de
   fila-encabezado/columnas cuando la autodetección falla.)
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
- BIESS: override manual de fila-encabezado / columnas cuando la autodetección falla.
- Respaldo por operación (`modulo_seguridad_prestamos` del legado — no existía nunca;
  su reemplazo real es `core.audit`).
