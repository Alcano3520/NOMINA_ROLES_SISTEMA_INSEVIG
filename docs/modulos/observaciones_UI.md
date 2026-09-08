# Observaciones — especificación de la interfaz Tkinter

Fuente: `observaciones/TOTAL_OSERVACIONES_4_0.pyw` (~1823 líneas). 3 pestañas:
**📋 Observaciones** · **💰 Multas** · **⚠️ Faltas**.
Web: `insevig_web/pages/observaciones/`.

Leyenda: ✅ hecho · 🟡 parcial · ❌ falta.

---

## Estructura común
- Selector de empleado arriba (buscar por cédula/nombre, con indicador de carga).
- Diálogo de configuración inicial ("Guardar y Conectar" — `config.ini` → en la web va por `core.config`).

## Pestaña "📋 Observaciones"  ✅
- Los **7 slots** `refer1..refer7` de RPEMPOBSERV para un período (mes).
- Editar cada slot inline + guardar (con advisory lock por empleado + auditoría).
- Ver historial completo de observaciones del empleado.
- Carga masiva desde Excel (columnas EMPLEADO / PERIODO / TEXTO) → Job + reporte.
- Historial descargable como HTML imprimible.

Web: `core.repos.observaciones` (`observaciones_mes` / `guardar_observaciones_mes` /
`historial_observaciones` / `historial_observaciones_html` / `job_carga_masiva_observaciones`)
+ `/observaciones/index` + `/observaciones/carga-masiva`.

## Pestaña "💰 Multas"  ✅ (visor)
- Multas del empleado (CLASE 203 de RPINGDES/RPHISTOR) — solo lectura.
Web: viewer en `core.repos.observaciones`.

## Pestaña "⚠️ Faltas"  ✅ (visor)
- Faltas / atrasos del empleado (RPHORTOT, RPHORHIS) — solo lectura.
Web: viewer en `core.repos.observaciones` (confirmar nombres de tabla en Supabase: `rphortot`/`rphorhis`).

---

## Lo que falta en la web
- (menor) Confirmar que los 3 visores (obs / multas / faltas) están todos
  expuestos como pestañas en `/observaciones` con el mismo detalle que el `.pyw`.
- Validar nombres de tabla `rphortot` / `rphorhis` en Supabase.
