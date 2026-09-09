# Procesamiento de Sanciones — especificación de la interfaz Tkinter

Fuente: `main.py` (~5400 líneas, clases `MainApplication` / `SidebarNavigator` /
`ContentArea` / `MainWindow`), `modern_viewer.py` (ficha de detalle),
`admin_panel.py` (usuarios). **Documento de referencia** — por la regla #7
**no se construye UI Reflex** para sanciones (frontend = app Flutter). Sirve
para el eventual worker de sync y para no perder el detalle del flujo.

Leyenda: n/a = no se porta a Reflex (Flutter lo cubre).

---

## Layout general

```
┌────────────┬───────────────────────────────────────────────────┐
│  SIDEBAR   │  ContentArea                                       │
│  (scroll)  │  ┌─────────────────────────────────────────────┐   │
│            │  │ Toolbar: [Buscar Supabase] [Exportar Excel]  │   │
│ Sistema    │  │          [Seleccionar todo] [contador]       │   │
│ RRHH       │  ├─────────────────────────────────────────────┤   │
│            │  │ Treeview (columnas según categoría)          │   │
│ CATEGORÍAS │  │  ☐ │ Cód │ Cédula │ Nombre │ Tipo │ Fecha │…  │   │
│  · F&P     │  │  ☑ │ 123 │ 09..  │ ARZUBE…│ FALTA│ 05/09 │…  │   │
│  · H&F     │  │  … (cientos de filas, nativo)                │   │
│  · Sanc.   │  ├─────────────────────────────────────────────┤   │
│ PROCESOS HR│  │ Acciones: [Aprobar] [Rechazar] [Procesar]    │   │
│  · Cambios │  │           [Ver Detalle]                      │   │
│  · Suspen. │  └─────────────────────────────────────────────┘   │
│  …         │                                                   │
│ HERRAMIEN. │   ← doble clic en fila = ficha de detalle          │
│  · Maniob. │                                                   │
│  · Faltas  │                                                   │
│ HISTORIAL  │                                                   │
│  · Compl.  │                                                   │
└────────────┴───────────────────────────────────────────────────┘
```

## Navegación (Mermaid)

```mermaid
graph TD
    L[Login] --> M[Ventana principal]
    M --> SB[Sidebar: elegir categoría]
    SB --> CT[ContentArea: Treeview de esa categoría]
    CT -->|doble clic / Ver Detalle| FD[Ficha de detalle ModernSancionViewer]
    CT -->|Buscar Supabase| BD[Diálogo búsqueda server-side]
    BD -->|doble clic / Ver| FD
    CT -->|Aprobar/Rechazar/Procesar| CF[Confirmación + observaciones]
    FD -->|Exportar PDF| PDF[filedialog → .pdf]
    CT -->|Exportar Excel| XLS[filedialog → .xlsx]
    M --> AP[Panel Admin usuarios (solo admin)]
```

---

## Sidebar (`SidebarNavigator`)  n/a

Secciones y sus `category_key`:

| Sección | Botones (key) |
|---|---|
| CATEGORÍAS DE SANCIONES | `FALTA_PERMISO`, `HORAS_FRANCO`, `RESTO` |
| PROCESOS HR | `CAMBIOS_DE_PUESTOS`, `SUSPENSIONES`, `LEVANTAMIENTO_SUSPENSIONES`, `REP_GOCE_VACACIONES`, `DESCUENTOS`, `PERMISOS_MEDICOS`, `OTROS_PROCESOS` |
| (aprobaciones) | `APROBACIONES` (`status=enviado`) |
| HERRAMIENTAS DE REGISTRO | módulos de `modulos/` (maniobras, faltas) — ver sus specs |
| HISTORIAL PROCESADAS | `HISTORIAL`, `HISTORIAL_RESTO`, `HISTORIAL_HORAS_FRANCO`, `HISTORIAL_FALTAS_PERMISOS` |

El sidebar es responsive (colapsable), 3 breakpoints (Small <1024, Medium
<1366, Large). Ahora los botones de "HERRAMIENTAS DE REGISTRO" se generan desde
el paquete `modulos/` (`modulos.listar(rol)`), no cableados.

## ContentArea — tabla (`ContentArea`, `ttk.Treeview` `Sanciones.Treeview`)  n/a

- `selectmode='extended'`, `show='headings'`. Columnas **según categoría**
  (`_configurar_columnas_treeview` / `UI_CONFIG['anchos_columnas_responsive']`).
- Carga instantánea (cientos de filas nativas). Sin paginación salvo historial
  (`obtener_procesadas_completas`, page_size 50).
- Contador de selección O(1); "Seleccionar todo" / "Deseleccionar".
- Doble clic (`_on_tree_double_click`) → parte de la sanción **cacheada y
  enriquecida**, la fusiona con `obtener_sancion(id)` fresco, abre la ficha.

## Diálogo "Buscar en Supabase" (`_abrir_busqueda_historial`)  n/a

- `ttk.LabelFrame` "Criterios de Búsqueda": Entry texto libre + Combobox tipo +
  Checkbutton "solo historial".
- `get_procesador().buscar_sanciones(texto, limite=500, tipo_sancion, solo_historial)`
  → server-side `ilike` sobre nombre/agente/tipo/observaciones/puesto (+
  `empleado_cod` exacto si el texto es numérico).
- `ttk.LabelFrame` "Resultados": Treeview cols `Emp.Cod, Cédula, Nombre, Tipo,
  Fecha, Observaciones, Estado`. Doble clic / botón "Ver Detalle" → fusiona con
  `obtener_sancion` fresco → ficha.

## Ficha de detalle (`modern_viewer.ModernSancionViewer`)  n/a (Flutter la tiene)

Tarjeta oscura (`#1a1f26`) con secciones:
1. **Header**: nombre, tipo, estado (badge de color), botón copiar ID.
2. **Empleado**: código, cédula, cargo, departamento (auto-completa vía
   `obtener_empleado_por_codigo` si faltan).
3. **Detalles**: fecha, hora, supervisor (resuelto vía `profiles`), agente,
   observaciones, observaciones adicionales.
4. **Evidencias**: firma + foto. `_buscar_campo_imagen` resuelve la URL
   (http directa o ruta relativa de Supabase Storage → URL pública). Carga
   async, clic = ver a tamaño completo.
5. **Comentarios**: gerencia, RRHH.
6. **Técnico**: IDs, timestamps, procesado_por / fecha_procesamiento.
7. **Botones**: Exportar PDF (`_exportar_pdf` → `generar_pdf_sancion`), cerrar.

## Acciones sobre selección  n/a (Flutter/gerencia las hace)

| Botón | Rol | Efecto |
|---|---|---|
| Aprobar | gerencia/admin/supervisor | `aprobar_sancion_individual` / `aprobar_multiples_sanciones` — PATCH `status=aprobado` + `comentarios_gerencia` + `fecha_revision`, respaldo local |
| Rechazar | gerencia/admin/supervisor | pide motivo (min 15 chars) → PATCH `status=rechazado` |
| Procesar | rrhh/admin/supervisor | valida disponibilidad → PATCH `comentarios_rrhh` = "Procesado para nomina - fecha - usuario" |

Masivo: lotes (`BATCH_SIZE` 50 / `BATCH_SIZE_APROBACIONES` 30) con barra de
progreso. En `nucleo_modular` la paralelización interna (ThreadPoolExecutor) se
simplificó a secuencial (mismo resultado).

## Exportar a Excel (`exportar_a_excel`)  → `core/excel/sanciones_*`

`filedialog` → `.xlsx` con: 1 hoja por categoría (27 columnas), hoja **"Detalle
Resumen"** (valor monetario calculado: FALTA/PERMISO = tabla; HORAS EXTRAS =
fijo 12h o `horas × factor`; FRANCO = fijo 8h/12h; resto = tabla
`valores_sanciones` de SQLite), hoja **"Resumen"**. Nombres de supervisor vía
`profiles` (SERVICE key).

## Panel Admin (`admin_panel.AdminPanel`)  → módulo aparte

Vista in-container (solo `rol=admin`): tabla de `usuarios_rrhh`, crear usuario,
resetear contraseña, cambiar rol, eliminar. Todo vía `usuarios.py`.

## Paleta (de `config.py`)

| Token | Valor | Uso |
|-------|-------|-----|
| fondo_principal | `#0f1419` | fondo app |
| fondo_secundario | `#1a1f26` | paneles, ficha |
| acento | `#1976d2` | acciones |
| éxito | `#2e7d32` | aprobado |
| error | `#c62828` | rechazado |
| pendiente | `#f57c00` | enviado |

## Estados (`status` → color / texto legible)

`borrador` (gris "Borrador") · `enviado` (naranja "Pendiente de Aprobacion") ·
`aprobado` (verde "Aprobado por Gerencia") · `rechazado` (rojo "Rechazado por
Gerencia"). "Procesado" no es un `status`: es tener `comentarios_rrhh` no nulo.
