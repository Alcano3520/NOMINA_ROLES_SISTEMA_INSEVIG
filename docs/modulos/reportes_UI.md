# Reportes de nómina — especificación de la interfaz Tkinter

Fuente: `reportes/reporte_nomina_GUI.pyw` (~648 líneas) — unifica las variantes
SQL_SERVER / SUPABASE / COMPARADOR. Web: `insevig_web/pages/reportes/`.

Leyenda: ✅ hecho · 🟡 parcial · ❌ falta.

---

## Ventana única (sin pestañas)

| Control | Detalle | Web |
|---|---|---|
| **Fuente de datos** (radio) | SQL Server · Supabase | ✅ (selector global de fuente) |
| **Tipo de nómina** (radio) | Nómina Actual (RPINGDES) · Histórico (RPHISTOR) | ✅ |
| **Período (YYYY-MM)** | entry, ej. 2026-05 | ✅ |
| **Guardar en:** + "..." | carpeta destino del Excel | ✅ eliminado → `rx.download` / `/trabajos` |
| **▶ Generar Reporte** | ejecuta el consolidado | ✅ (Job) |
| **📂 Abrir Excel** | abre el archivo generado | ✅ (descarga) |
| Estado ("Listo" / progreso) | | ✅ (`job_progress`) |

## Reportes que produce  🟡
1. **Consolidado del período** (una fila por empleado, todos los conceptos) +
   hoja **"Por departamento"** con subtotales (empleados/ingresos/egresos/neto).
   Web: `core/repos/nomina` + `core/excel/nomina_builders.consolidado_xlsx` +
   `/reportes/consolidado`. ✅
2. **Histórico RPHISTOR (~2.5M filas)** — generador cursor + xlsxwriter en modo
   memoria constante, como Job. Web: ✅
3. **Comparador Supabase vs SQL Server** — lista de discrepancias fila a fila.
   Web: `/reportes/comparador`. ✅

## Lo que falta en la web
- (verificación) Que el consolidado web coincida con la salida del `.pyw` dentro
  de tolerancia de redondeo para un período real — pendiente de correr en el NAS
  (`scripts/validar_datos.py` cubre SQL vs Supabase; falta vs el `.pyw`).
- Prueba de integración `test_concepts_cubre_periodo_real` — ✅ agregada
  (`tests/integration/test_reportes_conceptos.py`, gated).
