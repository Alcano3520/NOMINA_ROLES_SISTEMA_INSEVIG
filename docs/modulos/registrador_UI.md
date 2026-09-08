# Registrar egresos/ingresos — especificación de la interfaz Tkinter

Fuente: `registrdor_vizulizador_egresosingresos/REGISTRAR_PRESTAMOS_UNIFICADO.pyw`
(~5440 líneas). 6 pestañas. Web: `insevig_web/pages/registrador/index.py`.

Leyenda: ✅ hecho · 🟡 parcial · ❌ falta.

---

## Pestañas del `.pyw`

| # | Pestaña Tkinter | Web |
|---|---|---|
| 1 | **Préstamo Individual** — CLASE 205, elige empleado + valor total + planifica cuotas (por nº de cuotas o cuota mensual fija), panel "carga programada", vista previa editable, tipo de transacción, confirmación, exportar CSV | ✅ |
| 2 | **Carga Masiva Préstamos** — grilla editable / pegar de Excel / cargar archivo, Validar, resumen del lote, Registrar todo (Job + CSV) | ✅ |
| 3 | **Egresos / Ingresos** — registrar un movimiento de cualquier `CLASES_SIMPLIFICADAS` (multas 203, anticipos 202/217, pensión 206, hipotecario 207, IESS cónyuge 218, renta 219, surtidos 250, bonificación 102, maniobras 110, reembolsos 111, movilización 120), con grilla editable + pegar/cargar, **modo individual / agrupado** | ✅ (incl. modo agrupado, commit 05e3177) |
| 4 | **Registro Individual** (unificada con la 3 en la web) | ✅ |
| 5 | **BIESS Quirografarios** — CLASE 204/207, autodetección de fila/columnas + override manual, "Ver Excel", "Releer", empareja por cédula, marca activo/liquidado/no encontrado, posteo agrupado (21 columnas) + RPCONTRL | ✅ |
| 6 | **Consulta / Edición** — consultar movimientos ya registrados (RPINGDES no asentados), editar valor / eliminar fila | ✅ (`consultar_filas` / `editar_valor_fila` / `eliminar_fila` + página) |

---

## Panel "Historial de Registros" (lado derecho de la pestaña 3)  ✅
Al elegir empleado muestra sus movimientos no asentados (mismo panel
`historial_movimientos(..., empleado=...)`).

## Lo que falta en la web
- **Modo "agrupado" del legado en Egresos/Ingresos masivo** con un solo número de
  egreso y observación común — ✅ hecho (commit 05e3177).
- Respaldo por operación (`modulo_seguridad_prestamos` — nunca existió; su
  reemplazo es `core.audit`).
- (bajo) Réplica exacta de la autodetección de columnas BIESS "Ver Excel"
  (diagnóstico visual del archivo) — la web tiene el override manual editable.
