# Préstamos — especificación de la interfaz Tkinter (`prestamos/HISTORIAL_PRESTAMOS_10.pyw`)

Spec "prompt maestro" de la pantalla legada, para replicarla fiel en
`insevig_web/pages/prestamos/` + `insevig_web/states/prestamos_state.py`.
La app legada es **"CONSULTOR DE PRESTAMOS" — PEREIRA SYSTEMS**, una sola ventana
maximizada (`state('zoomed')`), sin pestañas.

Leyenda de estado web: ✅ hecho · 🟡 parcial · ❌ falta.

---

## 0. Layout general (de arriba a abajo)

```
┌─ BANDA SUPERIOR ────────────────────────────────────────────────────────────┐
│ [logo PEREIRA/SYSTEMS] · ··· · [ Filtros ] · [ Búsqueda y Acciones ]        │
├─ Información del Empleado (una línea) ──────────────────────────────────────┤
│ EMPLEADO · NOMBRE · CÉDULA · CARGO · DEPTO ·  SALDO TOTAL: $x                │
├─ PanedWindow horizontal ───────────────────────────────────────────────────┤
│ ┌ Historial de Movimientos (weight 4) ──┐ ┌ Empleados con Saldo (w 2) ──┐ │
│ │ tabla 8 columnas, doble-clic = detalle │ │ buscador + Act. + tabla     │ │
│ └───────────────────────────────────────┘ └────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

Título de ventana: `CONSULTOR DE PRESTAMOS`; subtítulo:
`Sistema Integrado de Prestamos  •  F5: buscar por nombre  •  DD/MM/AAAA`.

---

## 1. Banda superior

### 1.1 Logo (izquierda)  ✅ (equivalente: encabezado de página)
`🔷🔹` + "PEREIRA" (azul #4472C4, bold 13) + "SYSTEMS" (gris #7F8C8D, 9).

### 1.2 Panel "Filtros" (derecha, a la izquierda de Búsqueda)  🟡

**Fila 1:**
| Control | Tipo | Valores | Estado web |
|---|---|---|---|
| Fuente | combo readonly | SQLite · Supabase | ❌ (la web usa el selector global de fuente; el `.pyw` lo tiene inline con SQLite por defecto) |
| Tipo | combo readonly | Todos · Ingresos · Egresos | 🟡 (web: tipo pago/pendiente/desembolso) |
| Origen | combo readonly | Todos · Sistema Actual · Historico SQLite | ✅ (web: RPINGDES/RPHISTOR/MIGRADO) |
| Obs | entry (filtra al teclear, debounce 500 ms) | texto libre | ✅ |
| **X** | botón "Warning" | limpia todos los filtros | ✅ |

**Fila 2:**
| Control | Tipo | Estado web |
|---|---|---|
| Num | entry (debounce 500 ms) | ✅ |
| Desde / Hasta | entry `DD/MM/AAAA` (debounce 1000 ms) | ✅ (web usa `YYYY-MM-DD`) |
| Min / Max | entry monto (debounce 1000 ms) | ✅ |
| lbl_filtros | label itálica: resumen de filtros activos | 🟡 (web: "Mostrando N") |

Todos los filtros se aplican **en vivo** sobre la tabla ya cargada (no re-consulta la BD).

### 1.3 Panel "Busqueda y Acciones" (extremo derecho)  🟡

**Primera línea:** `Empleado:` [entry ancho 12, bold] · **NOMBRES** (abre buscador por nombre) · **BUSCAR** (Enter en el entry también).

**Segunda línea (botones):**
| Botón | Acción | Estado web |
|---|---|---|
| **SALDOS** (verde) | `exportar_saldos_prestamos_excel` — Excel de todos los empleados con saldo | ✅ (`/prestamos/saldos`) |
| **EXCEL** | `exportar_excel` — Excel del historial del empleado actual, **respetando los filtros activos** | ✅ (Exportar a Excel) |
| **IA** (azul) | `analizar_prestamos_ia` — diálogo de análisis con IA (§4) | 🟡 (web: botón "Analizar con IA", sin selector de rango) |
| **CFG** | `_configurar_ia` — diálogo de config del proveedor de IA (§5) | ❌ |

### 1.4 Buscador por nombre (diálogo modal, botón NOMBRES / F5 / Ctrl+F)  🟡
`LabelFrame "📝 Criterios de Búsqueda"` con `Apellidos:` y `Nombres:` (bold 11),
botones **🔍 BUSCAR** y **🧹 LIMPIAR**. Resultados en tabla (`LabelFrame
"📋 Resultados de la Búsqueda"`), label de estado ("Ingrese criterios de búsqueda"),
botones **✅ SELECCIONAR EMPLEADO** / **❌ CANCELAR**.
Web: `employee_search` cumple la función pero es un solo campo, no apellidos+nombres separados.

---

## 2. "Información del Empleado" (`LabelFrame`, una línea)  ✅
`self.lbl_info` con: código, nombre, cédula, cargo, departamento y **SALDO TOTAL: $x**.
Web: encabezado del empleado + badge "Saldo pendiente".

---

## 3. Panel izquierdo — "Historial de Movimientos"  ✅ (tabla) / 🟡 (columnas)

`LabelFrame " 📋 Historial de Movimientos (💡 Doble clic para ver detalles) "`, `weight=4`.

Tabla `Treeview` (`height=25`, `cursor=hand2`), **8 columnas**:
| Col | Encabezado | Ancho | Align | Web |
|---|---|---|---|---|
| # | # | 45 | center | ✅ (índice) |
| FECHA | FECHA | 100 | center | ✅ |
| INGRESO | INGRESO ($) | 100 | der | 🟡 (web: una col "Valor" + col "Tipo") |
| EGRESO | EGRESO ($) | 100 | der | 🟡 |
| NUMERO | NÚMERO | 100 | center | ✅ |
| OBSERV | OBSERVACIONES | 420 (stretch) | izq | ✅ |
| TIPO | TIPO | 80 | center | ✅ |
| SALDO MENSUAL | SALDO ($) | 110 | der | 🟡 (web: no muestra saldo corriente por fila) |

**Tags de color de fila** (`configurar_tags_tree`):
- `ingreso`: fondo blanco, texto #2c3e50, **bold** 11
- `egreso`: fondo **#ffeaea**, texto **#c0392b**, 11
- (falta ver: tag `cuadre` / `historico`)

Doble-clic → **diálogo de detalle de la fila** (§3.1).
Auto-ajuste de ancho de columnas al contenido (`self.tree.column(col, width=…)` calculado).
Scroll vertical y **horizontal**.

### 3.1 Diálogo "Detalle del movimiento" (doble-clic, modal 700×600)  ❌ (web: solo "Resumen por préstamo")

- Título: `💰 DETALLE DEL {INGRESO|EGRESO}` + ` 📁 [HISTÓRICO]` si viene de SQLite.
- `LabelFrame " ℹ️ Información General "` — grid de 8 filas etiqueta/valor:
  `📅 FECHA` · `🔢 NÚMERO` · `📊 POSICIÓN #n` · `💰 VALOR` · `📈 SALDO RESULTANTE` ·
  `🏷️ TIPO` · `📍 ORIGEN` (Histórico (SQLite) / Sistema Actual (SQL Server)) ·
  `📝 OBSERVACIÓN` (resumida a 80 chars, en azul #2980B9 si hay texto).
- `LabelFrame " 📝 Observación Completa "` — `Text` read-only, wrap word, 12 líneas,
  "Sin observaciones registradas" si vacío.
- Botones: **📋 COPIAR OBSERVACIÓN** (feedback "✅ COPIADO" 2 s) · **❌ CERRAR**.
- Atajos: Escape / Return cierran.

> Nota web: hoy el detalle es por **préstamo agrupado** (N° → cuotas). El `.pyw` tiene
> detalle **por movimiento individual**. Conviene agregar el segundo (doble-clic en la fila).

---

## 4. Panel derecho — "Empleados con Saldo"  ✅ (recién agregado, commit 1a19395)

`LabelFrame " 👥 Empleados con Saldo "`, `weight=2`.
- Buscador (`Buscar:` + entry, filtra al teclear con `after(300)`).
- Checkbox **Act.** (`var_solo_activos`, default True) — solo empleados activos.
- Tabla 3 columnas: `CÓD.` (52, center) · `NOMBRE` (210, izq, stretch) · `SALDO ($)` (110, der).
- Doble-clic / Return → carga el historial de ese empleado.
- `cargar_panel_saldos()` al abrir.

Web: ✅ panel con filtro + click → carga historial. ❌ falta el checkbox "solo activos"
(el repo `prestamos.saldos` no distingue activo/liquidado todavía).

---

## 5. Diálogo "Analizar Préstamos con IA" (botón IA)  🟡

- Selector de **rango de análisis** con 4 presets (botones):
  **Todo el historial** · **Año {actual}** · **Último año** · **Último semestre**.
- Botones **🤖 Analizar** · **Cancelar**.
- Al analizar: llama al LLM (`core/narrativa`) con el historial filtrado por el rango.
- Resultado: texto narrativo + **Leer en voz alta** / **Parar** (TTS; web usa Web Speech API).

Web: ✅ narrativa + leer/detener. ❌ falta el selector de rango (hoy analiza todo).

---

## 6. Diálogo "Configurar IA" (botón CFG)  ❌

- Selector de **proveedor** (`prov_var`) con hint dinámico por proveedor (`hint_texts`).
- Campos de API key / base URL / modelo (según proveedor).
- Label de error en rojo.
- Botones **💾 Guardar** · **Cancelar**.
- (Origen: `config/ia_config.json` en el `.pyw` → en la web iría por `core.config` / `AppConfig`.)

---

## 7. Diálogo "Estado de las Conexiones"  ❌ (baja prioridad)

`Label "Estado de las Conexiones"` + estado de: SQL Server (Sistema Principal) ·
SQLite (Historial) · Números Excluidos. Botón **Cerrar**.
Web: el estado de fuentes lo maneja el selector global; los "números excluidos"
(`_NUMEROS_MIGRADOS` / dedupe) no se exponen en UI.

---

## 8. Atajos de teclado

| Tecla | Acción |
|---|---|
| Enter (en entry Empleado) | BUSCAR |
| F5 / Ctrl+F | abrir buscador por nombre |
| Doble-clic fila | detalle del movimiento |
| Escape / Return (en diálogos) | cerrar |

---

## 9. Resumen de lo que falta en la web (orden sugerido)

1. **Diálogo de detalle por movimiento** (doble-clic en la fila del historial) — §3.1.
2. **Columnas INGRESO/EGRESO/SALDO por fila** en la tabla de movimientos (hoy: Valor+Tipo) — §3.
3. **Selector de rango en el análisis IA** (Todo / Año / Último año / Último semestre) — §5.
4. **Checkbox "solo activos"** en el panel Empleados con Saldo — §4 (necesita que `prestamos.saldos` marque estado).
5. **Diálogo de configuración de IA** (CFG) — §6.
6. Buscador por nombre con campos Apellidos/Nombres separados — §1.4.
7. (baja) Diálogo "Estado de las Conexiones" — §7.
