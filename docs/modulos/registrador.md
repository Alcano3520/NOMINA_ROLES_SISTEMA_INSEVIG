# Módulo: registrador (Registrar egresos/ingresos)

Estado: **puerto completo de REGISTRAR_PRESTAMOS_UNIFICADO.pyw** (6 pestañas).

## Pestañas (`/registrador`)
1. **Préstamo individual** — CLASE 205. Elige empleado, valor total, y planifica por
   nº de cuotas (`cuotas_tradicional`) o por cuota mensual fija respetando lo ya
   programado (`cuotas_por_valor` + `proyeccion_pagos_futuros`). Vista previa de la
   tabla de cuotas → registrar (una fila RPINGDES por cuota, nº desde RPCONTRL.ULT_EGR).
2. **Carga masiva de préstamos** — pegar "cédula, valor, nº cuotas, fecha" por línea
   → previsualizar (resuelve empleado) → aplicar como Job, CSV de resultados.
3. **Egresos / Ingresos** (`_tab_individual` en la web) — registrar un movimiento de
   cualquier tipo de `CLASES_SIMPLIFICADAS` (multas 203, anticipos 202/217, pensión
   206, hipotecario 207, IESS cónyuge 218, renta 219, surtidos 250, bonificación 102,
   maniobras 110, reembolsos 111, movilización 120). `registrar_movimiento`.
4. (unificada con la 3 en la web)
5. **BIESS quirografarios** — Excel → CLASE 204, empareja por cédula, vista previa
   con dedupe, confirmar. `preparar_biess` / `postear`.
6. **Consulta / edición** — lista de movimientos RPINGDES (ASENTADO=0) agrupados por
   NUMERO (`historial_movimientos`), ver cuotas de un préstamo (`cuotas_prestamo`),
   borrar un movimiento no asentado (`eliminar_movimiento`), editar valor/fecha de
   una cuota (`editar_cuota`).

## Datos
Lectura: SQL Server o Supabase (rpingdesres). Escritura: SOLO SQL Server, con
`audit_scope` + vista previa (`dry_run`). Números desde RPCONTRL (no transaccional,
igual que el legado — riesgo de colisión con instancias concurrentes: aceptable v1).

## Pendiente
- "Mover todas las cuotas pendientes a partir de una fecha" (diálogo del legado).
- Respaldo por operación (`modulo_seguridad_prestamos` del legado — no existía).
