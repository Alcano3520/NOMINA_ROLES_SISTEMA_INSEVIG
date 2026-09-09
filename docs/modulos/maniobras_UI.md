# Registro de Maniobras / Multas — especificación de la interfaz Tkinter

Fuente: `registro_maniobras.py` (~2100 líneas). Ventana `Toplevel` de **una sola
pantalla** (sin pestañas) + 2 ventanas auxiliares (Resumen, Búsqueda).
Web: **no se crea página nueva** — equivale a `/registrador` pestaña
"Egresos / Ingresos" del repo Reflex, con CLASE 110/203. Este documento es
referencia por si hay que verificar paridad.

Leyenda: ✅ (ya en `registrador`) · 🟡 · ❌.

---

## Pantalla principal (`crear_interfaz`)

```
┌──────────────────────────────────────────────────────────────────┐
│  [ Barra de progreso ▓▓▓░░░  0% ]              [❌ Cancelar]      │
├──────────────────────────────────────────────────────────────────┤
│ ⚙️ Configuración                                                  │
│   Tipo: [110 - MANIOBRAS ▾]        📊 Datos:0 | Cache:0/3000 |    │
│                                       Filas: 1-20 de 2500         │
├──────────────────────────────────────────────────────────────────┤
│ 📋 Grid Masivo (2500 empleados)                                   │
│   🔥 PEGADO MASIVO: clic celda → Ctrl+V | Código|Fecha|Valor|Obs  │
│   [🔥 PEGAR MASIVO] [🔍 Validar] [🧹 Limpiar] [📊 Resumen] [📁 Cargar]│
│   ┌──────────────────────────────────────────────────────────┐    │
│   │ # │ Código │ Nombre │ Fecha │ Valor │ Observación         │    │
│   │ 1 │  1234  │ (auto) │ 05/09 │ 12.50 │ …                   │    │
│   │ …  (scroll vertical + horizontal, 20 filas visibles)     │    │
│   └──────────────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────────────┤
│ 🧭 Navegación                                                     │
│   [⏪ -100] [◀️ -20] [▶️ +20] [⏩ +100] │ [⏫ INICIO] [⏬ FINAL]     │
│   Ir a: [____] [IR]                                               │
├──────────────────────────────────────────────────────────────────┤
│ ⚙️ Procesamiento                                                  │
│   [💾 Procesar BD] [📋 Reporte] [📊 Excel]        [⬅️ Regresar]    │
├──────────────────────────────────────────────────────────────────┤
│ 📝 Log (consola, 6 líneas)                                        │
└──────────────────────────────────────────────────────────────────┘
```

### Componentes

| ID | Tipo | Props | Evento → Acción | Web |
|----|------|-------|-----------------|-----|
| progress | Progressbar + Label + Cancelar | 0–100 | operaciones largas | `job_progress` ✅ |
| tipo | Combobox readonly | `110 - MANIOBRAS`, `203 - MULTAS` | fija la CLASE del lote | selector de CLASE ✅ |
| stats_label | Label | "Datos:N \| Cache:x/3000 \| Filas: a-b de 2500" | info de la ventana virtualizada del grid | (no aplica en web) |
| btn_pegar | Button naranja `#FF4500` | | Ctrl+V → `parsear_linea_pegado` → llena grid desde celda activa | pegar TSV ✅ |
| btn_validar | Button | | resuelve nombre por código (`buscar_empleados_batch`), marca filas OK | Validar ✅ |
| btn_limpiar | Button | | vacía el grid | Limpiar ✅ |
| btn_resumen | Button | | abre ventana "📈 Resumen Estadístico" (`calcular_resumen_grid`) | resumen del lote ✅ |
| btn_cargar | Button | | `filedialog` → `.xlsx/.csv` → `importar_fila_desde_dataframe_row` | cargar archivo ✅ |
| grid | Canvas virtualizado | 2500 filas lógicas, ~20 visibles; columnas responsive (4/5/6 según pantalla) | edición inline por celda; navegación por ventana | grid editable (sin virtualización) ✅ |
| nav_* | Buttons | -100/-20/+20/+100, INICIO, FINAL, "Ir a fila" | mueve la ventana visible del grid | paginación de tabla |
| btn_procesar | Button "💾 Procesar BD" | | `validar_filas_para_procesar` → confirmación → Job: por fila `insertar_movimiento_rapido(ejecutar=True)` (INSERT RPINGDES + UPDATE RPCONTRL) | `registrar_movimiento` + Job ✅ |
| btn_reporte | Button "📋 Reporte" | | `generar_contenido_reporte` → `.txt` (`filedialog`) | descarga TXT/CSV |
| btn_excel | Button "📊 Excel" | | `armar_datos_exportacion_grid` → `.xlsx` | descarga XLSX ✅ (CSV) |
| btn_regresar | Button | solo si viene de `main.py` | cierra la `Toplevel` | — |
| log_text | Text readonly (Consolas 8) | | append por operación | consola de Job |

### Estados de pantalla

| Estado | UI | Trigger |
|--------|-----|---------|
| vacío | grid en blanco, "Sistema masivo inicializado: 2500 empleados" | al abrir |
| pegado | filas llenas sin validar | tras Ctrl+V / Cargar |
| validando | progress activo, Cancelar habilitado | Validar / Procesar |
| validado | filas marcadas ✓ / ✗, stats | fin de Validar |
| procesando | progress %, log por fila | Procesar BD |
| error conexión | messagebox + log | fallo pyodbc |

---

## Ventana auxiliar — "📈 Resumen Estadístico" (`mostrar_resumen`)

`ttk.LabelFrame` "Resumen Estadístico" (totales: filas con datos, válidas, suma
de valores, promedio) + `ttk.LabelFrame` "Detalle de Registros Procesados"
(Treeview con las primeras N filas). Web = panel "resumen del lote" ✅.

## Ventana auxiliar — "Búsqueda" (`abrir_buscador_empleados`, F3)

`ttk.LabelFrame` "Criterios de Búsqueda" (Entry de texto) + "Resultados de
Búsqueda" (Treeview código/cédula/nombre/depto). `buscar_empleados_por_texto`.
Doble clic = usa ese código en la fila activa. Web = autocompletar de empleado
en la celda de código.

---

## Reglas de validación (`maniobras_calculo`)

- Código numérico existente en `RPEMPLEA` (`buscar_empleados_batch`).
- Valor numérico > 0.
- Fecha: acepta varios formatos (`resolver_fecha_movimiento`), default = hoy si
  vacía.
- Columna "Nombre" es derivada (readonly); si el pegado empieza en esa columna
  el valor se descarta en silencio (bug del legado).

## Paleta

| Token | Valor | Uso |
|-------|-------|-----|
| accion_pegar | `#FF4500` | botón PEGAR MASIVO |
| header grid | `navy` / `white` | encabezado de columnas |
| título | `darkblue` | título de ventana |
| stats ok | `darkgreen` | etiqueta de estadísticas |

## Checklist paridad (contra `/registrador`)

- [ ] Registrar CLASE 110 masivo: pegar → validar → procesar → CSV
- [ ] Registrar CLASE 203 masivo: idem
- [ ] Numeración correlativa desde RPCONTRL sin colisión (ya resuelto mejor en `registrador`)
- [ ] Resumen del lote (totales + promedio)
- [ ] Cargar archivo `.xlsx/.csv`
- [ ] Autocompletar/buscar empleado por texto
