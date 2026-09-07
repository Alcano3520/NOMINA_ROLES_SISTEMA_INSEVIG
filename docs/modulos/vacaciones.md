# Módulo: vacaciones — Vacaciones gozadas y pagadas (Art. 69/71/76 CT Ecuador)

Origen: `~/Documentos/mis_proyecto/VACACIONES_SISTEMA_INSEVIG/` (app de escritorio
Tkinter, panel de búsqueda + 5 pestañas: Historial, Datos, Gozadas, Pagadas,
Cálculo). **El `.pyw` original NO se modificó** — sigue siendo la referencia de
comportamiento; esto es la migración a `core/`, no un fork ni una reescritura.

## Qué hace
Registra y consulta vacaciones GOCE (descanso tomado) y PAGO (liquidación
económica del período) por empleado, según Art. 69/71/76 CT Ecuador: 15 días
base + 1 día adicional por cada año de servicio sobre 5, calculado por año
calendario del período (no por resta de días exacta — ver docstring de
`calcular_dias_adicionales`).

- **Buscar** — empleado por cédula o nombre (`rpemplea`).
- **Resumen** — días gozados históricos, total pagado, pendientes; panel de
  alertas (períodos con días pendientes, gozadas sin firmar/confirmar).
- **Gozadas** — alta con auto-cálculo de "hasta" (desde + días − 1), firmar/
  confirmar, eliminar.
- **Pagadas** — alta calculada (pestaña "Cálculo": trae 12 meses de nómina,
  aplica la fórmula real, arma el pago) o alta manual con valores directos
  (`crear_pagada_manual`, para casos que no pasan por el cálculo automático).
- **Reportes** — Reporte Completo (Pagos + Goces) con filtros período/depto/
  estado, exportación a Excel.

## Particularidad
**Escribe a Supabase, no a SQL Server** — igual que `bitacora` (ver su nota en
`docs/modulos/bitacora.md`), vacaciones no tiene tabla equivalente en
`RPEMPLEA`/`RPEMPOBSERV`/`RPINGDES`: es 100% propia (`vac_registros`,
`vac_calculo`, `vac_config`, `vac_codigos_nomina`). `docs/CONTRATOS.md` dice
"Escrituras: siempre SQL Server (en v1)" — esa regla no aplica a este módulo
por la misma razón que no aplica a bitácora; pendiente de aclarar ahí
explícitamente (reportado, no corregido unilateralmente).

**`vac_registros` es consumida por `liquidaciones`** (lee `periodo`,
`estado_doc`, `valor_vacaciones`, `dias_tomados` para no volver a pagar un
período ya gozado/pagado — confirmado con esa sesión). No renombrar columnas
ni cambiar la semántica de `estado_doc='completado'` sin avisar y ajustar
liquidaciones en el mismo cambio.

**Diferencia de comportamiento detectada** (reportada, no corregida en
silencio): `calculos.calcular_vacaciones_pagadas()` del `.pyw` es código
MUERTO (solo lo usa `test_sistema.py`) con una fórmula distinta e
incompatible con la que de verdad usa producción
(`app.py::_recalcular_totales`/`_registrar_pagada`). Ver docstring de
`core/repos/vacaciones.py` y de `calcular_pago()` para el detalle exacto. Este
módulo porta la fórmula de PRODUCCIÓN.

## Rebanada
- `core/repos/vacaciones.py` — períodos (Art. 69), acceso a `rpemplea`/
  `rphistor_temp`/`rpingdesres` (propio, no importa `core.repos.empleados`),
  fórmula de pago (`calcular_pago`), CRUD `vac_registros` (`crear_gozada`,
  `crear_pagada`, `crear_pagada_manual`, `actualizar`, `eliminar`,
  `registrar_pago`, `marcar_firmada`), `vac_calculo` (`get_calculo_detalle`,
  `guardar_calculo_detalle`), alertas, reportes (`reporte_completo`,
  `reporte_nomina_pagos`, `reporte_nomina_gozadas`, `resumen_periodos`,
  `reporte_pendientes_global`, `dashboard_stats`, `sin_firmar_activos`).
- `core/excel/vacaciones_builders.py` — `reporte_completo_xlsx`.
- `insevig_web/states/vacaciones_state.py`, `insevig_web/pages/vacaciones/index.py`.

## Permisos
`vacaciones:ver` (consulta), `vacaciones:crear`/`editar` (editor), `eliminar`
solo `admin` (vía `ACCIONES` completo).

## Pendiente / no portado (deliberado)
- **PDF individual con QR** (comprobante GOCE/PAGO, `src/pdf_generator.py` +
  `src/data_extractor.py` del `.pyw`) — no tiene builder equivalente aquí
  todavía (reportlab + QR). El flujo web hoy solo exporta el reporte a Excel.
- **Envío a carpeta de financiero** (`_generar_y_exportar_pdf` copia el PDF a
  una ruta de red) — depende del PDF individual de arriba.
- Reportes secundarios del `.pyw` no expuestos aún en la página web:
  `reporte_pendientes` (por tipo, distinto del completo), `reporte_dias_empleado`,
  `reporte_pendientes_global` (sí portado en `core/repos/vacaciones.py`, falta
  su pantalla), `dashboard_stats`/`sin_firmar_activos` (sí portados, sin UI).
- `renombrador_qr.py` (diálogo standalone para renombrar archivos escaneados
  por su QR) — herramienta de escritorio aparte, no aplica a la app web.
- Confirmación interactiva de "período anterior pendiente" antes de guardar
  (`_confirmar_periodo_prioritario` del `.pyw`) — los datos ya están
  disponibles vía `get_alertas()`; falta el diálogo de confirmación en la UI
  (hoy la página solo muestra el aviso, no bloquea el guardado).
