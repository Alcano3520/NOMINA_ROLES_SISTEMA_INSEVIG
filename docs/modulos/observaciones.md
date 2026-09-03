# Módulo: observaciones

Estado: **consulta completa + alta de observaciones + reporte imprimible**.

## Origen legado
`observaciones/TOTAL_OSERVACIONES_4_0.pyw` (visor de obs/multas/faltas),
`empleados/agregar_observaciones_masivas.py`.

## Qué hace
- Buscar empleado y ver, en pestañas: **Observaciones** (refer1..7 unidos),
  **Multas** (RPHISTOR CLASE 203), **Faltas** (RPHORTOT actual + RPHORHIS histórico).
- **Añadir observación** (`observaciones.guardar_observacion`): la escribe en el
  primer slot refer libre del mes (advisory lock + auditoría); crea fila si los 7
  están llenos; evita duplicados exactos. Gated en `observaciones:crear`.
- **Reporte imprimible** (`observaciones.reporte_html`): HTML con obs+multas+faltas
  para imprimir (Ctrl+P), descargable.
- Edición inline de los 7 slots de un mes: en el editor de empleados
  (`observaciones.observaciones_mes / guardar_observaciones_mes`).

## Datos
Lectura SQL Server o Supabase; escritura solo SQL Server (RPEMPOBSERV).

## Pendiente
- Carga masiva de observaciones desde Excel (plantilla + Job), como
  `agregar_observaciones_masivas.py`.
